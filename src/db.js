const { Pool } = require('pg');
require('dotenv').config();

class Database {
  constructor() {
    this.pool = null;
    this.isConnected = false;
    this.init();
  }

  async init() {
    const connectionString = process.env.DATABASE_URL;
    const dbHost = process.env.DB_HOST;

    if (!connectionString && !dbHost) {
      console.log('[Database] ℹ️ No se detectó DATABASE_URL ni DB_HOST. Modo archivo JSON activo.');
      return;
    }

    try {
      if (connectionString) {
        this.pool = new Pool({
          connectionString,
          ssl: process.env.DB_SSL === 'true' ? { rejectUnauthorized: false } : false
        });
      } else {
        this.pool = new Pool({
          host: process.env.DB_HOST || 'localhost',
          port: parseInt(process.env.DB_PORT || '5432'),
          user: process.env.DB_USER || 'postgres',
          password: process.env.DB_PASSWORD || '',
          database: process.env.DB_NAME || 'wally_bot',
          ssl: process.env.DB_SSL === 'true' ? { rejectUnauthorized: false } : false
        });
      }

      // Test connection
      const client = await this.pool.connect();
      console.log('[Database] 🐘 ¡Conexión exitosa a PostgreSQL!');
      this.isConnected = true;
      client.release();

      await this.runMigrations();
    } catch (err) {
      console.error('[Database] ⚠️ Error conectando a PostgreSQL:', err.message);
      console.log('[Database] ℹ️ Continuando con persistencia local JSON.');
      this.isConnected = false;
    }
  }

  async runMigrations() {
    if (!this.pool) return;

    const schemaQuery = `
      -- 1. Tabla de Prospectos de Campañas
      CREATE TABLE IF NOT EXISTS prospects (
        id VARCHAR(64) PRIMARY KEY,
        business VARCHAR(255) NOT NULL,
        name VARCHAR(255),
        niche VARCHAR(100),
        location VARCHAR(100),
        phone VARCHAR(50) NOT NULL,
        custom_message TEXT NOT NULL,
        status VARCHAR(20) DEFAULT 'PENDING',
        sent_at TIMESTAMPTZ,
        failed_at TIMESTAMPTZ,
        error TEXT,
        message_id VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );

      -- 2. Tabla de Logs de Auditoría y Estado de Campañas
      CREATE TABLE IF NOT EXISTS campaign_logs (
        id BIGSERIAL PRIMARY KEY,
        log_type VARCHAR(20),
        message TEXT,
        details JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );

      -- 3. Tabla de Mensajes Enviados y Recibidos (Historial Completo de Chats)
      CREATE TABLE IF NOT EXISTS messages (
        id VARCHAR(128) PRIMARY KEY,
        remote_jid VARCHAR(100) NOT NULL,
        phone VARCHAR(50),
        from_me BOOLEAN NOT NULL DEFAULT FALSE,
        sender_name VARCHAR(255),
        message_text TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );
    `;

    try {
      await this.pool.query(schemaQuery);
      console.log('[Database] ✅ Tablas "prospects", "campaign_logs" y "messages" listas en PostgreSQL.');
    } catch (err) {
      console.error('[Database] Error ejecutando migraciones:', err.message);
    }
  }

  // === PROSPECTS ===
  async getAllProspects() {
    if (!this.isConnected || !this.pool) return null;
    try {
      const res = await this.pool.query('SELECT * FROM prospects ORDER BY created_at ASC');
      return res.rows.map(r => ({
        id: r.id,
        business: r.business,
        name: r.name,
        niche: r.niche,
        location: r.location,
        phone: r.phone,
        customMessage: r.custom_message,
        status: r.status,
        sentAt: r.sent_at,
        failedAt: r.failed_at,
        error: r.error,
        messageId: r.message_id
      }));
    } catch (err) {
      console.error('[Database] Error en getAllProspects:', err.message);
      return null;
    }
  }

  async upsertProspect(p) {
    if (!this.isConnected || !this.pool) return false;
    const query = `
      INSERT INTO prospects (id, business, name, niche, location, phone, custom_message, status, sent_at, failed_at, error, message_id, updated_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
      ON CONFLICT (id) DO UPDATE SET
        business = EXCLUDED.business,
        name = EXCLUDED.name,
        niche = EXCLUDED.niche,
        location = EXCLUDED.location,
        phone = EXCLUDED.phone,
        custom_message = EXCLUDED.custom_message,
        status = EXCLUDED.status,
        sent_at = EXCLUDED.sent_at,
        failed_at = EXCLUDED.failed_at,
        error = EXCLUDED.error,
        message_id = EXCLUDED.message_id,
        updated_at = NOW();
    `;
    const values = [
      p.id,
      p.business,
      p.name || null,
      p.niche || null,
      p.location || null,
      p.phone,
      p.customMessage || p.message,
      p.status || 'PENDING',
      p.sentAt || null,
      p.failedAt || null,
      p.error || null,
      p.messageId || null
    ];
    try {
      await this.pool.query(query, values);
      return true;
    } catch (err) {
      console.error('[Database] Error en upsertProspect:', err.message);
      return false;
    }
  }

  async saveAllProspects(prospectsList) {
    if (!this.isConnected || !this.pool) return false;
    try {
      for (const p of prospectsList) {
        await this.upsertProspect(p);
      }
      return true;
    } catch (err) {
      console.error('[Database] Error en saveAllProspects:', err.message);
      return false;
    }
  }

  // === MESSAGES (ENVIADOS Y RECIBIDOS) ===
  async saveMessage(msg) {
    if (!this.isConnected || !this.pool) return false;
    const query = `
      INSERT INTO messages (id, remote_jid, phone, from_me, sender_name, message_text, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      ON CONFLICT (id) DO NOTHING;
    `;
    const cleanPhone = msg.remoteJid ? msg.remoteJid.split('@')[0].replace(/[^\d]/g, '') : msg.phone;
    const values = [
      msg.id || 'msg_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6),
      msg.remoteJid || `${cleanPhone}@s.whatsapp.net`,
      cleanPhone,
      Boolean(msg.fromMe),
      msg.senderName || (msg.fromMe ? 'Aura Web' : 'Cliente'),
      msg.messageText || msg.text || '',
      msg.timestamp ? new Date(msg.timestamp) : new Date()
    ];
    try {
      await this.pool.query(query, values);
      return true;
    } catch (err) {
      console.error('[Database] Error guardando mensaje en DB:', err.message);
      return false;
    }
  }

  async getRecentMessages(limit = 50) {
    if (!this.isConnected || !this.pool) return [];
    try {
      const res = await this.pool.query('SELECT * FROM messages ORDER BY created_at DESC LIMIT $1', [limit]);
      return res.rows;
    } catch (err) {
      console.error('[Database] Error obteniendo mensajes:', err.message);
      return [];
    }
  }

  // === LOGS ===
  async insertLog(type, message, details = {}) {
    if (!this.isConnected || !this.pool) return;
    try {
      await this.pool.query(
        'INSERT INTO campaign_logs (log_type, message, details) VALUES ($1, $2, $3)',
        [type, message, JSON.stringify(details)]
      );
    } catch (err) {
      // Silencioso para no interferir
    }
  }
}

module.exports = new Database();
