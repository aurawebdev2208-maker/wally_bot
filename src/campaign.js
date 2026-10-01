const fs = require('fs');
const path = require('path');
const whatsapp = require('./whatsapp');
const db = require('./db');

class CampaignManager {
  constructor() {
    this.dataFile = path.join(__dirname, '..', 'prospects.json');
    this.logsFile = path.join(__dirname, '..', 'campaign_logs.json');
    this.state = {
      isRunning: false,
      isPaused: false,
      campaignName: 'Aura Web Outreach',
      total: 0,
      sent: 0,
      failed: 0,
      pending: 0,
      currentIndex: 0,
      currentProspect: null,
      delaySeconds: parseInt(process.env.DEFAULT_DELAY_SECONDS || '30'),
      startedAt: null,
      finishedAt: null,
      logs: []
    };
    this.activeTimeout = null;
    this.prospectsQueue = [];
    this.initData();
  }

  async initData() {
    // Intentar cargar de la base de datos si está conectada
    setTimeout(async () => {
      const dbProspects = await db.getAllProspects();
      if (dbProspects && dbProspects.length > 0) {
        // Verificar si contiene caracteres corruptos (diamantes de reemplazo UTF-8)
        const hasCorruptedChars = dbProspects.some(p => 
          (p.business && (p.business.includes('') || p.business.includes('\uFFFD'))) ||
          (p.niche && (p.niche.includes('') || p.niche.includes('\uFFFD'))) ||
          (p.customMessage && (p.customMessage.includes('') || p.customMessage.includes('\uFFFD')))
        );

        if (hasCorruptedChars) {
          console.log('[Campaign] ⚠️ Se detectaron caracteres corruptos en BD. Restaurando desde prospects.json con UTF-8 limpio...');
          this.loadProspectsFromFile();
          await db.saveAllProspects(this.prospectsQueue);
        } else {
          this.prospectsQueue = dbProspects;
        }
        console.log(`[Campaign] 🐘 ${this.prospectsQueue.length} prospectos sincronizados correctamente.`);
      } else {
        this.loadProspectsFromFile();
        if (db.isConnected && this.prospectsQueue.length > 0) {
          await db.saveAllProspects(this.prospectsQueue);
        }
      }
    }, 1000);
  }

  loadProspectsFromFile() {
    try {
      if (fs.existsSync(this.dataFile)) {
        const raw = fs.readFileSync(this.dataFile, 'utf8');
        this.prospectsQueue = JSON.parse(raw);
      } else {
        this.prospectsQueue = [];
      }
    } catch (err) {
      console.error('[Campaign] Error loading prospects from file:', err);
      this.prospectsQueue = [];
    }
  }

  async saveProspects(prospects) {
    this.prospectsQueue = prospects;
    
    // Guardar en archivo local
    try {
      fs.writeFileSync(this.dataFile, JSON.stringify(prospects, null, 2), 'utf8');
    } catch (err) {
      console.error('[Campaign] Error saving prospects to file:', err);
    }

    // Guardar en DB si está conectada
    if (db.isConnected) {
      await db.saveAllProspects(prospects);
    }

    return true;
  }

  getProspects() {
    return this.prospectsQueue;
  }

  getStatus() {
    return {
      ...this.state,
      prospectsCount: this.prospectsQueue.length,
      isDbConnected: db.isConnected
    };
  }

  addLog(type, message, details = {}) {
    const logEntry = {
      id: Date.now() + Math.random().toString(36).substring(2, 6),
      timestamp: new Date().toLocaleTimeString('es-AR'),
      type, // 'info' | 'success' | 'warning' | 'error'
      message,
      details
    };
    this.state.logs.unshift(logEntry);
    if (this.state.logs.length > 100) {
      this.state.logs.pop();
    }

    // Persistir log en DB
    if (db.isConnected) {
      db.insertLog(type, message, details);
    }
  }

  async start(options = {}) {
    if (this.state.isRunning) {
      throw new Error('Ya hay una campaña en ejecución.');
    }

    const wsStatus = whatsapp.getStatus();
    if (wsStatus.status !== 'CONNECTED') {
      throw new Error('WhatsApp no está conectado. Escaneá el QR primero.');
    }

    if (!this.prospectsQueue || this.prospectsQueue.length === 0) {
      throw new Error('No hay prospectos cargados en la lista.');
    }

    const delaySec = Math.max(Number(options.delaySeconds) || this.state.delaySeconds, 15);
    const campaignName = options.campaignName || 'Aura Web Outreach';

    // Filtrar prospectos pendientes o nuevos
    const pendingList = this.prospectsQueue.filter(p => !p.status || p.status === 'PENDING' || p.status === 'FAILED');

    if (pendingList.length === 0) {
      throw new Error('Todos los prospectos en la lista ya fueron marcados como enviados.');
    }

    this.state = {
      isRunning: true,
      isPaused: false,
      campaignName,
      total: this.prospectsQueue.length,
      sent: this.prospectsQueue.filter(p => p.status === 'SENT').length,
      failed: this.prospectsQueue.filter(p => p.status === 'FAILED').length,
      pending: pendingList.length,
      currentIndex: 0,
      currentProspect: null,
      delaySeconds: delaySec,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      logs: this.state.logs
    };

    this.addLog('info', `Iniciando campaña "${campaignName}" con ${pendingList.length} prospectos pendientes. Delay de seguridad: ${delaySec}s.`);

    this.processNext();
    return this.getStatus();
  }

  async processNext() {
    if (!this.state.isRunning || this.state.isPaused) return;

    // Buscar el siguiente prospecto pendiente
    const prospect = this.prospectsQueue.find(p => !p.status || p.status === 'PENDING');

    if (!prospect) {
      this.state.isRunning = false;
      this.state.finishedAt = new Date().toISOString();
      this.state.currentProspect = null;
      this.addLog('success', `¡Campaña finalizada! Total enviados: ${this.state.sent}, Fallidos: ${this.state.failed}.`);
      await this.saveProspects(this.prospectsQueue);
      return;
    }

    this.state.currentProspect = prospect;
    this.addLog('info', `Preparando envío a: ${prospect.name || prospect.business} (${prospect.phone})...`);

    try {
      const messageText = prospect.customMessage || prospect.message;
      if (!messageText) {
        throw new Error('El prospecto no tiene mensaje configurado.');
      }

      const result = await whatsapp.sendTextMessage(prospect.phone, messageText, { simulateTyping: true });

      prospect.status = 'SENT';
      prospect.sentAt = new Date().toISOString();
      prospect.messageId = result.messageId;

      this.state.sent++;
      this.state.pending = this.prospectsQueue.filter(p => !p.status || p.status === 'PENDING').length;
      await this.saveProspects(this.prospectsQueue);

      this.addLog('success', `Mensaje enviado con éxito a ${prospect.name || prospect.business}`, { phone: prospect.phone });
    } catch (err) {
      console.error(`[Campaign] Error enviando a ${prospect.phone}:`, err);
      prospect.status = 'FAILED';
      prospect.error = err.message;
      prospect.failedAt = new Date().toISOString();

      this.state.failed++;
      this.state.pending = this.prospectsQueue.filter(p => !p.status || p.status === 'PENDING').length;
      await this.saveProspects(this.prospectsQueue);

      this.addLog('error', `Error al enviar a ${prospect.name || prospect.business}: ${err.message}`, { phone: prospect.phone });
    }

    // Calcular delay aleatorio humano (ej: 30s +/- 5s)
    const randomJitter = Math.floor(Math.random() * 10) - 5;
    const waitTimeSeconds = Math.max(this.state.delaySeconds + randomJitter, 15);

    this.addLog('info', `Pausa de seguridad anti-bloqueo: esperando ${waitTimeSeconds} segundos antes del próximo envío...`);

    this.activeTimeout = setTimeout(() => {
      this.processNext();
    }, waitTimeSeconds * 1000);
  }

  pause() {
    if (!this.state.isRunning) return this.getStatus();
    this.state.isPaused = true;
    if (this.activeTimeout) {
      clearTimeout(this.activeTimeout);
      this.activeTimeout = null;
    }
    this.addLog('warning', 'Campaña pausada por el usuario.');
    return this.getStatus();
  }

  resume() {
    if (!this.state.isRunning || !this.state.isPaused) return this.getStatus();
    this.state.isPaused = false;
    this.addLog('info', 'Campaña reanudada.');
    this.processNext();
    return this.getStatus();
  }

  stop() {
    this.state.isRunning = false;
    this.state.isPaused = false;
    this.state.currentProspect = null;
    if (this.activeTimeout) {
      clearTimeout(this.activeTimeout);
      this.activeTimeout = null;
    }
    this.addLog('warning', 'Campaña detenida por el usuario.');
    this.saveProspects(this.prospectsQueue);
    return this.getStatus();
  }
}

module.exports = new CampaignManager();
