const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  Browsers,
  delay
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');
const db = require('./db');
const { usePostgresAuthState } = require('./pgAuthState');

class WhatsAppManager {
  constructor() {
    this.authFolder = path.join(__dirname, '..', 'auth_info_baileys');
    this.sock = null;
    this.clearDbSession = null;
    this.state = {
      status: 'INITIALIZING', // INITIALIZING | QR_READY | CONNECTING | CONNECTED | DISCONNECTED | LOGGED_OUT
      qrCodeRaw: null,
      qrDataUrl: null,
      user: null,
      lastError: null,
      connectedAt: null,
      updatedAt: new Date().toISOString()
    };
    this.isReconnecting = false;
    this.eventListeners = [];
  }

  onStateChange(callback) {
    this.eventListeners.push(callback);
  }

  notifyStateChange() {
    this.state.updatedAt = new Date().toISOString();
    for (const listener of this.eventListeners) {
      try {
        listener(this.getStatus());
      } catch (err) {
        console.error('[WhatsApp] Error in state listener:', err);
      }
    }
  }

  getStatus() {
    return {
      status: this.state.status,
      qrDataUrl: this.state.qrDataUrl,
      user: this.state.user,
      lastError: this.state.lastError,
      connectedAt: this.state.connectedAt,
      updatedAt: this.state.updatedAt
    };
  }

  async init() {
    try {
      console.log('[WhatsApp] Inicializando sesión de Baileys...');
      await db.init();
      this.state.status = 'CONNECTING';
      this.state.lastError = null;
      this.notifyStateChange();

      let authState, saveCreds;

      // 🐘 Si PostgreSQL está conectado, persistir sesión directamente en la Base de Datos
      if (db.isConnected && db.pool) {
        console.log('[WhatsApp] 🐘 Usando PostgreSQL para persistencia de sesión (sin necesidad de volúmenes Docker).');
        const pgAuth = await usePostgresAuthState(db.pool, 'default');
        authState = pgAuth.state;
        saveCreds = pgAuth.saveCreds;
        this.clearDbSession = pgAuth.clearSession;
      } else {
        console.log('[WhatsApp] 📁 Usando almacenamiento local en disco (auth_info_baileys).');
        const fileAuth = await useMultiFileAuthState(this.authFolder);
        authState = fileAuth.state;
        saveCreds = fileAuth.saveCreds;
        this.clearDbSession = null;
      }

      const { version } = await fetchLatestBaileysVersion().catch(() => ({
        version: [2, 3000, 1015901307],
        isLatest: true
      }));

      console.log(`[WhatsApp] Usando versión de WhatsApp Web: v${version.join('.')}`);

      this.sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: true,
        auth: authState,
        browser: Browsers.macOS('Desktop'),
        syncFullHistory: false,
        markOnlineOnConnect: true,
        connectTimeoutMs: 60000,
        keepAliveIntervalMs: 30000
      });

      this.sock.ev.on('creds.update', saveCreds);

      // Guardar mensajes entrantes de clientes en la base de datos
      this.sock.ev.on('messages.upsert', async (m) => {
        try {
          if (m.type === 'notify') {
            for (const msg of m.messages) {
              if (!msg.key.fromMe) {
                const text = msg.message?.conversation ||
                             msg.message?.extendedTextMessage?.text ||
                             msg.message?.imageMessage?.caption || '';
                const remoteJid = msg.key.remoteJid;
                const senderName = msg.pushName || 'Cliente';

                if (text && remoteJid && !remoteJid.includes('@g.us')) {
                  console.log(`[WhatsApp] 💬 Nuevo mensaje recibido de ${senderName} (${remoteJid}): "${text}"`);
                  await db.saveMessage({
                    id: msg.key.id,
                    remoteJid,
                    fromMe: false,
                    senderName,
                    messageText: text,
                    timestamp: msg.messageTimestamp ? new Date(Number(msg.messageTimestamp) * 1000) : new Date()
                  });
                }
              }
            }
          }
        } catch (msgErr) {
          console.error('[WhatsApp] Error procesando mensaje entrante:', msgErr);
        }
      });

      this.sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
          console.log('[WhatsApp] Nuevo código QR recibido.');
          this.state.qrCodeRaw = qr;
          try {
            this.state.qrDataUrl = await QRCode.toDataURL(qr, {
              margin: 2,
              scale: 8,
              color: {
                dark: '#0f172a',
                light: '#ffffff'
              }
            });
            this.state.status = 'QR_READY';
            this.notifyStateChange();
          } catch (qrErr) {
            console.error('[WhatsApp] Error al convertir QR a DataURL:', qrErr);
          }
        }

        if (connection === 'connecting') {
          console.log('[WhatsApp] Conectando a WhatsApp Web...');
          if (this.state.status !== 'QR_READY') {
            this.state.status = 'CONNECTING';
            this.notifyStateChange();
          }
        }

        if (connection === 'open') {
          console.log('[WhatsApp] ¡Conexión establecida con éxito!');
          this.state.status = 'CONNECTED';
          this.state.qrCodeRaw = null;
          this.state.qrDataUrl = null;
          this.state.connectedAt = new Date().toISOString();

          const userJid = this.sock.user?.id || '';
          const cleanPhone = userJid.split(':')[0].split('@')[0];
          this.state.user = {
            id: userJid,
            phone: cleanPhone,
            name: this.sock.user?.name || 'Aura Web Bot'
          };
          this.notifyStateChange();
        }

        if (connection === 'close') {
          const statusCode = lastDisconnect?.error?.output?.statusCode;
          const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
          const errorMsg = lastDisconnect?.error?.message || 'Conexión cerrada';

          console.log(`[WhatsApp] Conexión cerrada. Motivo: ${errorMsg} (Status Code: ${statusCode}). Reconnect: ${shouldReconnect}`);

          this.state.lastError = errorMsg;

          if (statusCode === DisconnectReason.loggedOut) {
            this.state.status = 'LOGGED_OUT';
            this.state.user = null;
            this.state.qrCodeRaw = null;
            this.state.qrDataUrl = null;
            this.notifyStateChange();
            await this.clearCredentials();
            // Reiniciar automáticamente para generar un nuevo QR
            setTimeout(() => this.init(), 2000);
          } else {
            this.state.status = 'DISCONNECTED';
            this.notifyStateChange();
            if (shouldReconnect && !this.isReconnecting) {
              this.isReconnecting = true;
              console.log('[WhatsApp] Intentando reconectar en 4 segundos...');
              setTimeout(async () => {
                this.isReconnecting = false;
                await this.init();
              }, 4000);
            }
          }
        }
      });

      return true;
    } catch (err) {
      console.error('[WhatsApp] Error inicializando Baileys:', err);
      this.state.status = 'DISCONNECTED';
      this.state.lastError = err.message;
      this.notifyStateChange();
      return false;
    }
  }

  formatJid(rawPhone) {
    if (!rawPhone) return null;
    let clean = String(rawPhone).replace(/[^\d]/g, '');

    // Si empieza con 0 en Argentina, quitar el 0
    if (clean.startsWith('0')) {
      clean = clean.substring(1);
    }

    // Si es número de Argentina (longitud de 10 dígitos ej: 3884567890), anteponer 549
    if (clean.length === 10 && !clean.startsWith('54')) {
      clean = '549' + clean;
    } else if (clean.startsWith('54') && !clean.startsWith('549') && clean.length === 12) {
      // Si tiene 54388... agregar el 9 móvil de WhatsApp
      clean = '549' + clean.substring(2);
    }

    return `${clean}@s.whatsapp.net`;
  }

  async sendTextMessage(to, text, options = {}) {
    if (this.state.status !== 'CONNECTED' || !this.sock) {
      throw new Error('WhatsApp no está conectado. Por favor escaneá el código QR primero.');
    }

    if (!to || !text) {
      throw new Error('Número de teléfono y mensaje son obligatorios.');
    }

    const jid = this.formatJid(to);
    if (!jid) {
      throw new Error(`Número de teléfono inválido: ${to}`);
    }

    try {
      // Simular presencia humana (typing / escribiendo...)
      const simulateTyping = options.simulateTyping !== false;
      if (simulateTyping) {
        await this.sock.sendPresenceUpdate('composing', jid);
        const typingDelay = Math.min(Math.max(text.length * 20, 1500), 4000);
        await delay(typingDelay);
        await this.sock.sendPresenceUpdate('paused', jid);
      }

      const result = await this.sock.sendMessage(jid, { text });
      const messageId = result?.key?.id;

      // Guardar el mensaje saliente en PostgreSQL
      await db.saveMessage({
        id: messageId,
        remoteJid: jid,
        phone: to,
        fromMe: true,
        senderName: 'Aura Web',
        messageText: text,
        timestamp: new Date()
      });

      return {
        success: true,
        jid,
        messageId,
        timestamp: new Date().toISOString()
      };
    } catch (err) {
      console.error(`[WhatsApp] Error enviando mensaje a ${jid}:`, err);
      throw err;
    }
  }

  async clearCredentials() {
    try {
      // Borrar de DB si está conectado
      if (this.clearDbSession) {
        await this.clearDbSession();
      }
      // Borrar de disco local
      if (fs.existsSync(this.authFolder)) {
        fs.rmSync(this.authFolder, { recursive: true, force: true });
        console.log('[WhatsApp] Carpeta de autenticación eliminada con éxito.');
      }
    } catch (err) {
      console.error('[WhatsApp] Error borrando credenciales:', err);
    }
  }

  async logout() {
    console.log('[WhatsApp] Cerrando sesión y desvinculando cuenta...');
    try {
      if (this.sock) {
        try {
          await this.sock.logout();
        } catch (e) {
          // Ignorar si ya estaba desconectado
        }
        this.sock.end(undefined);
        this.sock = null;
      }
      await this.clearCredentials();
      this.state = {
        status: 'LOGGED_OUT',
        qrCodeRaw: null,
        qrDataUrl: null,
        user: null,
        lastError: null,
        connectedAt: null,
        updatedAt: new Date().toISOString()
      };
      this.notifyStateChange();

      // Iniciar de nuevo inmediatamente para generar nuevo QR
      setTimeout(() => this.init(), 1500);

      return { success: true, message: 'Sesión cerrada correctamente.' };
    } catch (err) {
      console.error('[WhatsApp] Error en logout:', err);
      return { success: false, error: err.message };
    }
  }
}

module.exports = new WhatsAppManager();
