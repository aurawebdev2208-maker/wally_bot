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
    
    // Guardar en archivo local
    try {
      fs.writeFileSync(this.dataFile, JSON.stringify(this.prospectsQueue, null, 2), 'utf8');
    } catch (err) {
      console.error('[Campaign] Error saving prospects to file:', err);
    }

    // Guardar en DB si está conectada
    if (db.isConnected) {
      await db.saveAllProspects(this.prospectsQueue);
    }

    return true;
  }

  getProspects() {
    return this.prospectsQueue;
  }

  getGroups() {
    const groupMap = {};
    for (const p of this.prospectsQueue) {
      const groupName = this.normalizeMacroNiche(p.niche || p.group);
      if (!groupMap[groupName]) {
        groupMap[groupName] = {
          name: groupName,
          total: 0,
          pending: 0,
          sent: 0,
          failed: 0
        };
      }
      groupMap[groupName].total++;
      if (p.status === 'SENT') groupMap[groupName].sent++;
      else if (p.status === 'FAILED') groupMap[groupName].failed++;
      else groupMap[groupName].pending++;
    }
    return Object.values(groupMap);
  }

  async batchAssignGroup(prospectIds, newGroupName) {
    if (!Array.isArray(prospectIds) || !newGroupName) return false;
    let modified = false;
    const cleanGroup = this.normalizeMacroNiche(newGroupName);
    for (const p of this.prospectsQueue) {
      if (prospectIds.includes(p.id)) {
        p.niche = cleanGroup;
        modified = true;
      }
    }
    if (modified) {
      await this.saveProspects(this.prospectsQueue);
    }
    return true;
  }

  getStatus() {
    return {
      ...this.state,
      prospectsCount: this.prospectsQueue.length,
      groups: this.getGroups(),
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
    const targetGroup = options.targetGroup && options.targetGroup !== 'ALL' ? options.targetGroup : null;

    // Filtrar prospectos pendientes que pertenezcan al grupo objetivo (si se eligió uno)
    const pendingList = this.prospectsQueue.filter(p => {
      const isPending = !p.status || p.status === 'PENDING' || p.status === 'FAILED';
      if (!isPending) return false;
      if (!targetGroup) return true;
      const groupName = p.niche || p.group || 'General';
      return groupName.toLowerCase() === targetGroup.toLowerCase();
    });

    if (pendingList.length === 0) {
      throw new Error(targetGroup 
        ? `No hay prospectos pendientes en el grupo "${targetGroup}".`
        : 'Todos los prospectos en la lista ya fueron marcados como enviados.');
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
      startedAt: new Date().toISOString(),
      finishedAt: null,
      logs: this.state.logs
    };

    const targetLabel = targetGroup ? `Grupo "${targetGroup}"` : 'Todos los grupos';
    this.addLog('info', `Iniciando campaña para ${targetLabel} con ${pendingList.length} prospectos pendientes. Delay de seguridad: ${delaySec}s.`);

    this.processNext();
    return this.getStatus();
  }

  async processNext() {
    if (!this.state.isRunning || this.state.isPaused) return;

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
    this.addLog('info', `Preparando envío a [${groupName}]: ${prospect.name || prospect.business} (${prospect.phone})...`);

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
