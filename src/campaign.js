const fs = require('fs');
const path = require('path');
const whatsapp = require('./whatsapp');
const db = require('./db');

/**
 * Resuelve bloques Spintax del tipo {opcion1|opcion2|opcion3}
 */
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

/**
 * Enriquecedor de mensajes con variaciones dinámicas automáticas
 * para que cada mensaje tenga un hash de texto y estructura diferente.
 */
function enrichWithDynamicVariations(text, prospectName, businessName) {
  if (!text) return '';
  let varied = text;

  // Si no tiene spintax manual {a|b}, aplicar variaciones dinámicas profesionales
  if (!varied.includes('{')) {
    // 1. Variar saludos
    varied = varied.replace(/¡Hola([^!]+)!/i, (match, p1) => {
      const trimmed = p1.trim();
      const targetName = trimmed || businessName || '';
      const greetings = [
        `¡Hola ${targetName}!`,
        `Hola ${targetName}, ¿cómo está?`,
        `¡Buenas ${targetName}!`,
        `Hola ${targetName}, un gusto saludarle.`
      ];
      return greetings[Math.floor(Math.random() * greetings.length)];
    });

    // 2. Variar intro de Aura Web
    varied = varied.replace(/Le escribo de Aura Web/i, () => {
      const intros = [
        'Le escribo de Aura Web',
        'Nos comunicamos desde Aura Web',
        'Le contacto desde Aura Web',
        'Le escribo de parte del equipo de Aura Web'
      ];
      return intros[Math.floor(Math.random() * intros.length)];
    });

    // 3. Variar enlace a la demo
    varied = varied.replace(/Le comparto una demo en vivo:/i, () => {
      const demos = [
        'Le comparto una demo en vivo:',
        'Le dejo una muestra interactiva:',
        'Puede ver un ejemplo en vivo aquí:',
        'Le adjunto una demo de muestra:'
      ];
      return demos[Math.floor(Math.random() * demos.length)];
    });

    // 4. Variar despedidas
    varied = varied.replace(/¡Que tenga un gran día!/i, () => {
      const closings = [
        '¡Que tenga un gran día!',
        '¡Que tenga una excelente jornada!',
        '¡Saludos y buen día!',
        '¡Quedo a su disposición!'
      ];
      return closings[Math.floor(Math.random() * closings.length)];
    });
  }

  // Parsear cualquier spintax restante
  return parseSpintax(varied);
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
      delaySeconds: parseInt(process.env.DEFAULT_DELAY_SECONDS || '75'), // 75s promedio
      maxBatchSize: 10, // Límite estricto por tanda (10 envíos)
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
    if (!nicheStr) return 'Estética & Spa';
    const n = nicheStr.toLowerCase();
    if (n.includes('dent') || n.includes('odont') || n.includes('ortodon') || n.includes('dient') || n.includes('implante') || n.includes('dental')) {
      return 'Odontología';
    }
    if (n.includes('inmob') || n.includes('alquiler') || n.includes('propiedad') || n.includes('lote') || n.includes('bienes')) {
      return 'Inmobiliaria';
    }
    if (n.includes('caban') || n.includes('turism') || n.includes('hotel') || n.includes('hospedaje') || n.includes('suite')) {
      return 'Turismo & Cabañas';
    }
    return 'Estética & Spa';
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

    // Intervalo de seguridad: Mínimo 60 segundos base (promedio 75s a 110s)
    const delaySec = Math.max(Number(options.delaySeconds) || 75, 50);
    
    // Límite estricto por tanda: Default 10, Máximo infranqueable 15
    const requestedBatch = Number(options.maxBatchSize);
    const maxBatch = (requestedBatch > 0 && requestedBatch <= 15) ? requestedBatch : 10;
    
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
    this.addLog('info', `🛡️ [Modo Anti-Baneo] Iniciando lote para ${targetLabel}. Límite seguro: ${maxBatch} envíos. Intervalo promedio: ${delaySec}s.`);

    this.processNext();
    return this.getStatus();
  }

  async processNext() {
    if (!this.state.isRunning || this.state.isPaused) return;

    // 1. HARD-CAP: Verificar si se alcanzó el límite seguro del lote
    if (this.state.batchSentCount >= this.state.maxBatchSize) {
      this.state.isRunning = false;
      this.state.finishedAt = new Date().toISOString();
      this.state.currentProspect = null;
      this.addLog('warning', `🛑 Lote de seguridad completado (${this.state.batchSentCount}/${this.state.maxBatchSize} envíos). La campaña se pausó automáticamente para proteger la salud de tu número de WhatsApp.`);
      await this.saveProspects(this.prospectsQueue);
      return;
    }

    // 2. Buscar el siguiente prospecto pendiente
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
      this.addLog('success', `¡Todos los prospectos del grupo han sido completados! Enviados: ${this.state.sent}, Fallidos: ${this.state.failed}.`);
      await this.saveProspects(this.prospectsQueue);
      return;
    }

    this.state.currentProspect = prospect;
    const groupName = prospect.niche || prospect.group || 'General';
    this.addLog('info', `Preparando envío seguro (${this.state.batchSentCount + 1}/${this.state.maxBatchSize}) a [${groupName}]: ${prospect.name || prospect.business} (${prospect.phone})...`);

    try {
      let rawText = prospect.customMessage || prospect.message;
      if (!rawText) {
        throw new Error('El prospecto no tiene mensaje configurado.');
      }

      // Enriquecer con Spintax y variaciones dinámicas para que cada mensaje sea único
      const messageText = enrichWithDynamicVariations(rawText, prospect.name, prospect.business);

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

      this.addLog('success', `Mensaje entregado con éxito a ${prospect.name || prospect.business} [${groupName}] (${this.state.batchSentCount}/${this.state.maxBatchSize})`, { phone: prospect.phone });
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

    // 3. Pausa aleatoria humana anti-detección (ej: 75s base con variación de ±25s -> entre 60s y 115s)
    const randomJitter = Math.floor(Math.random() * 50) - 25; // -25s a +25s
    const waitTimeSeconds = Math.max(this.state.delaySeconds + randomJitter, 55);

    this.addLog('info', `⏳ Pausa anti-detección: esperando ${waitTimeSeconds} segundos antes del próximo envío...`);

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
