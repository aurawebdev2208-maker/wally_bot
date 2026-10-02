const fs = require('fs');
const path = require('path');
const whatsapp = require('./whatsapp');
const db = require('./db');

function parseSpintax(text) {
  if (!text) return '';
  const spintaxRegex = /\{([^{}]+)\}/g;
  let matches;
  while ((matches = spintaxRegex.exec(text)) !== null) {
    const choices = matches[1].split('|');
    const randomChoice = choices[Math.floor(Math.random() * choices.length)].trim();
    text = text.replace(matches[0], randomChoice);
  }
  return text;
}

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
      delaySeconds: parseInt(process.env.DEFAULT_DELAY_SECONDS || '60'),
      maxBatchSize: 15,
      batchSentCount: 0,
      startedAt: null,
      finishedAt: null,
      logs: []
    };
    this.activeTimeout = null;
    this.prospectsQueue = [];
    this.initData();
  }

  async initData() {
    setTimeout(async () => {
      const dbProspects = await db.getAllProspects();
      if (dbProspects && dbProspects.length > 0) {
        this.prospectsQueue = dbProspects;
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

  normalizeMacroNiche(nicheStr) {
    if (!nicheStr) return 'General';
    const n = nicheStr.toLowerCase();
    if (n.includes('dent') || n.includes('odont') || n.includes('ortodon') || n.includes('dient') || n.includes('implante') || n.includes('dental')) {
      return 'Odontología';
    }
    if (n.includes('estet') || n.includes('spa') || n.includes('facial') || n.includes('corporal') || n.includes('cosmet') || n.includes('depil') || n.includes('belleza')) {
      return 'Estética & Spa';
    }
    if (n.includes('inmob') || n.includes('alquiler') || n.includes('propiedad') || n.includes('lote') || n.includes('bienes')) {
      return 'Inmobiliaria';
    }
    if (n.includes('caban') || n.includes('turism') || n.includes('hotel') || n.includes('hospedaje') || n.includes('suite')) {
      return 'Turismo & Cabañas';
    }
    return nicheStr.trim();
  }

  async saveProspects(prospects) {
    this.prospectsQueue = prospects.map(p => ({
      ...p,
      niche: this.normalizeMacroNiche(p.niche || p.group)
    }));
    
    try {
      fs.writeFileSync(this.dataFile, JSON.stringify(this.prospectsQueue, null, 2), 'utf8');
    } catch (err) {
      console.error('[Campaign] Error guardando prospects.json local:', err.message);
    }

    if (db.isConnected) {
      await db.saveAllProspects(this.prospectsQueue);
    }
    return true;
  }

  getProspects() {
    return this.prospectsQueue;
  }

  getGroups() {
    const groups = {};
    for (const p of this.prospectsQueue) {
      const g = p.niche || p.group || 'General';
      if (!groups[g]) {
        groups[g] = { total: 0, pending: 0, sent: 0, failed: 0 };
      }
      groups[g].total++;
      if (p.status === 'SENT') groups[g].sent++;
      else if (p.status === 'FAILED') groups[g].failed++;
      else groups[g].pending++;
    }
    return Object.entries(groups).map(([name, stats]) => ({
      name,
      ...stats
    }));
  }

  getStatus() {
    const activeWs = whatsapp.getStatus();
    return {
      ...this.state,
      isWhatsAppConnected: activeWs.status === 'CONNECTED',
      prospectsCount: this.prospectsQueue.length,
      groups: this.getGroups(),
      isDbConnected: db.isConnected
    };
  }

  addLog(type, message, details = {}) {
    const logItem = {
      id: Date.now().toString() + Math.random().toString(36).substring(2, 6),
      timestamp: new Date().toLocaleTimeString('es-AR', { hour12: false }),
      type, // 'info' | 'success' | 'warning' | 'error'
      message,
      details
    };

    this.state.logs.unshift(logItem);
    if (this.state.logs.length > 200) {
      this.state.logs.pop();
    }

    if (db.isConnected) {
      db.insertLog(type, message, details);
    }

    try {
      fs.writeFileSync(this.logsFile, JSON.stringify(this.state.logs, null, 2), 'utf8');
    } catch (err) {}
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

    const delaySec = Math.max(Number(options.delaySeconds) || this.state.delaySeconds, 30);
    const maxBatch = Math.min(Number(options.maxBatchSize) || 15, 20); // Máximo 15-20 por tanda para evitar bloqueos
    const campaignName = options.campaignName || 'Aura Web Outreach';
    const targetGroup = options.targetGroup && options.targetGroup !== 'ALL' ? options.targetGroup : null;

    const pendingList = this.prospectsQueue.filter(p => {
      const isPending = !p.status || p.status === 'PENDING';
      if (!isPending) return false;
      if (!targetGroup) return true;
      const groupName = p.niche || p.group || 'General';
      return groupName.toLowerCase() === targetGroup.toLowerCase();
    });

    if (pendingList.length === 0) {
      throw new Error(targetGroup 
        ? `No hay prospectos pendientes en el grupo "${targetGroup}".`
        : 'Todos los prospectos en la lista ya fueron procesados.');
    }

    const groupProspects = targetGroup 
      ? this.prospectsQueue.filter(p => (p.niche || p.group || 'General').toLowerCase() === targetGroup.toLowerCase())
      : this.prospectsQueue;

    this.state = {
      isRunning: true,
      isPaused: false,
      campaignName: targetGroup ? `${campaignName} [${targetGroup}]` : campaignName,
      targetGroup: targetGroup || 'ALL',
      total: groupProspects.length,
      sent: groupProspects.filter(p => p.status === 'SENT').length,
      failed: groupProspects.filter(p => p.status === 'FAILED').length,
      pending: pendingList.length,
      currentIndex: 0,
      currentProspect: null,
      delaySeconds: delaySec,
      maxBatchSize: maxBatch,
      batchSentCount: 0,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      logs: this.state.logs
    };

    const targetLabel = targetGroup ? `Grupo "${targetGroup}"` : 'Todos los grupos';
    this.addLog('info', `Iniciando campaña anti-bloqueo para ${targetLabel}. Lote máximo: ${maxBatch} envíos. Delay: ${delaySec}s.`);

    this.processNext();
    return this.getStatus();
  }

  async processNext() {
    if (!this.state.isRunning || this.state.isPaused) return;

    // Verificar si se alcanzó el límite del lote de seguridad
    if (this.state.batchSentCount >= this.state.maxBatchSize) {
      this.state.isRunning = false;
      this.state.finishedAt = new Date().toISOString();
      this.state.currentProspect = null;
      this.addLog('warning', `🛑 Lote de seguridad completado (${this.state.batchSentCount} envíos). La campaña se pausó automáticamente para proteger tu número de WhatsApp.`);
      await this.saveProspects(this.prospectsQueue);
      return;
    }

    // Buscar el siguiente prospecto pendiente del grupo objetivo
    const prospect = this.prospectsQueue.find(p => {
      const isPending = !p.status || p.status === 'PENDING';
      if (!isPending) return false;
      if (!this.state.targetGroup || this.state.targetGroup === 'ALL') return true;
      const groupName = p.niche || p.group || 'General';
      return groupName.toLowerCase() === this.state.targetGroup.toLowerCase();
    });

    if (!prospect) {
      this.state.isRunning = false;
      this.state.finishedAt = new Date().toISOString();
      this.state.currentProspect = null;
      this.addLog('success', `¡Campaña finalizada! Total enviados: ${this.state.sent}, Fallidos: ${this.state.failed}.`);
      await this.saveProspects(this.prospectsQueue);
      return;
    }

    this.state.currentProspect = prospect;
    const groupName = prospect.niche || prospect.group || 'General';
    this.addLog('info', `Preparando envío (${this.state.batchSentCount + 1}/${this.state.maxBatchSize}) a [${groupName}]: ${prospect.name || prospect.business} (${prospect.phone})...`);

    try {
      let rawText = prospect.customMessage || prospect.message;
      if (!rawText) {
        throw new Error('El prospecto no tiene mensaje configurado.');
      }

      // Aplicar spintax dinámico para variar sutilmente el mensaje y evitar hash idéntico
      const messageText = parseSpintax(rawText);

      const result = await whatsapp.sendTextMessage(prospect.phone, messageText, { simulateTyping: true });

      prospect.status = 'SENT';
      prospect.sentAt = new Date().toISOString();
      prospect.messageId = result.messageId;

      this.state.sent++;
      this.state.batchSentCount++;
      const targetGroup = this.state.targetGroup && this.state.targetGroup !== 'ALL' ? this.state.targetGroup.toLowerCase() : null;
      this.state.pending = this.prospectsQueue.filter(p => {
        const isPending = !p.status || p.status === 'PENDING';
        if (!isPending) return false;
        if (!targetGroup) return true;
        const g = (p.niche || p.group || 'General').toLowerCase();
        return g === targetGroup;
      }).length;
      await this.saveProspects(this.prospectsQueue);

      this.addLog('success', `Mensaje enviado con éxito a ${prospect.name || prospect.business} [${groupName}]`, { phone: prospect.phone });
    } catch (err) {
      console.error(`[Campaign] Error enviando a ${prospect.phone}:`, err);
      prospect.status = 'FAILED';
      prospect.error = err.message;
      prospect.failedAt = new Date().toISOString();

      this.state.failed++;
      const targetGroup = this.state.targetGroup && this.state.targetGroup !== 'ALL' ? this.state.targetGroup.toLowerCase() : null;
      this.state.pending = this.prospectsQueue.filter(p => {
        const isPending = !p.status || p.status === 'PENDING';
        if (!isPending) return false;
        if (!targetGroup) return true;
        const g = (p.niche || p.group || 'General').toLowerCase();
        return g === targetGroup;
      }).length;
      await this.saveProspects(this.prospectsQueue);

      this.addLog('error', `Error al enviar a ${prospect.name || prospect.business}: ${err.message}`, { phone: prospect.phone });
    }

    // Calcular delay aleatorio humano (ej: 45s +/- 15s)
    const randomJitter = Math.floor(Math.random() * 20) - 10;
    const waitTimeSeconds = Math.max(this.state.delaySeconds + randomJitter, 30);

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
    if (this.activeTimeout) {
      clearTimeout(this.activeTimeout);
      this.activeTimeout = null;
    }
    this.state.isRunning = false;
    this.state.isPaused = false;
    this.state.currentProspect = null;
    this.state.finishedAt = new Date().toISOString();
    this.addLog('warning', 'Campaña detenida por el usuario.');
    return this.getStatus();
  }
}

module.exports = new CampaignManager();
