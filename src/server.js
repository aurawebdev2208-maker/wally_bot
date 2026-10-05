require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const crypto = require('crypto');
const whatsapp = require('./whatsapp');
const campaign = require('./campaign');
const db = require('./db');

const app = express();
const PORT = process.env.PORT || 3000;

const AUTH_SECRET = process.env.AUTH_SECRET || 'wally_bot_secret_aura_2026';

function validateCredentials(username, password) {
  if (!username || !password) return false;

  const users = {
    [process.env.AUTH_USER || 'dorquera']: process.env.AUTH_PASSWORD || 'tuxx6393',
    [process.env.AUTH_ANTIG_USER || 'antig']: process.env.AUTH_ANTIG_PASSWORD || 'antig6393'
  };

  // Support additional comma-separated users if defined (user:pass,user2:pass2)
  if (process.env.AUTH_USERS) {
    const pairs = process.env.AUTH_USERS.split(',');
    for (const pair of pairs) {
      const [u, p] = pair.split(':');
      if (u && p) {
        users[u.trim()] = p.trim();
      }
    }
  }

  return users[username] && users[username] === password;
}

function generateToken(username) {
  const expiresAt = Date.now() + 1000 * 60 * 60 * 24 * 30; // 30 días
  const payload = Buffer.from(JSON.stringify({ username, expiresAt })).toString('base64url');
  const signature = crypto.createHmac('sha256', AUTH_SECRET).update(payload).digest('base64url');
  return `${payload}.${signature}`;
}

function verifyToken(token) {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [payload, signature] = parts;
  const expectedSig = crypto.createHmac('sha256', AUTH_SECRET).update(payload).digest('base64url');
  if (signature !== expectedSig) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    if (data.expiresAt && data.expiresAt < Date.now()) return null;
    return data;
  } catch (e) {
    return null;
  }
}

function authMiddleware(req, res, next) {
  if (req.path === '/api/auth/login') {
    return next();
  }

  const authHeader = req.headers.authorization || req.headers['x-auth-token'];
  let token = null;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    token = authHeader.slice(7).trim();
  } else if (authHeader) {
    token = authHeader.trim();
  }

  const user = verifyToken(token);
  if (!user) {
    return res.status(401).json({ success: false, error: 'No autorizado. Debe iniciar sesión.' });
  }

  req.user = user;
  next();
}

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, '..', 'public'), {
  setHeaders: (res, filePath) => {
    if (filePath && filePath.endsWith('.html')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
      res.setHeader('Pragma', 'no-cache');
      res.setHeader('Expires', '0');
    }
  }
}));

// === API AUTH ===
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body || {};
  if (validateCredentials(username, password)) {
    const token = generateToken(username);
    return res.json({
      success: true,
      token,
      user: { username }
    });
  }
  return res.status(401).json({
    success: false,
    error: 'Usuario o contraseña incorrectos'
  });
});

// Public Healthcheck Endpoints for Coolify / Docker (No auth required)
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', uptime: process.uptime(), timestamp: new Date().toISOString() });
});

app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'ok', uptime: process.uptime(), timestamp: new Date().toISOString() });
});

// Protect all other /api routes
app.use('/api', authMiddleware);

app.get('/api/auth/verify', (req, res) => {
  res.json({
    success: true,
    user: req.user
  });
});

// === API WHATSAPP SESSION ===

app.get('/api/status', (req, res) => {
  res.json({
    success: true,
    data: whatsapp.getStatus()
  });
});

app.post('/api/logout', async (req, res) => {
  try {
    campaign.stop();
    const result = await whatsapp.logout();
    res.json(result);
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post('/api/reconnect', async (req, res) => {
  try {
    await whatsapp.init();
    res.json({ success: true, message: 'Reconexión iniciada' });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// === API MENSAJE INDIVIDUAL ===

app.post('/api/send', async (req, res) => {
  const { phone, message } = req.body;
  if (!phone || !message) {
    return res.status(400).json({ success: false, error: 'Faltan parámetros: phone y message son requeridos.' });
  }

  try {
    const result = await whatsapp.sendTextMessage(phone, message, { simulateTyping: true });
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// === API INBOX (WHATSAPP -> ANTIGRAVITY BRIDGE) ===

app.get('/api/inbox/unread', async (req, res) => {
  try {
    const unread = await db.getUnreadInboxMessages();
    res.json({
      success: true,
      count: unread.length,
      messages: unread
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.post('/api/inbox/ack', async (req, res) => {
  const { ids } = req.body;
  if (!Array.isArray(ids)) {
    return res.status(400).json({ success: false, error: 'ids debe ser un arreglo de IDs.' });
  }
  try {
    await db.markInboxMessagesProcessed(ids);
    res.json({ success: true, message: 'Mensajes marcados como procesados.' });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get('/api/inbox/history', async (req, res) => {
  try {
    const history = await db.getInboxHistory(30);
    res.json({ success: true, data: history });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// === API PROSPECTOS Y CAMPAÑAS ===

app.get('/api/prospects', (req, res) => {
  res.json({
    success: true,
    data: campaign.getProspects()
  });
});

app.post('/api/prospects', (req, res) => {
  const { prospects } = req.body;
  if (!Array.isArray(prospects)) {
    return res.status(400).json({ success: false, error: 'El cuerpo debe contener un arreglo de prospectos.' });
  }

  const success = campaign.saveProspects(prospects);
  if (success) {
    res.json({ success: true, message: 'Prospectos actualizados correctamente.', count: prospects.length });
  } else {
    res.status(500).json({ success: false, error: 'Error guardando prospectos.' });
  }
});

app.get('/api/groups', (req, res) => {
  res.json({
    success: true,
    data: campaign.getGroups()
  });
});

app.post('/api/prospects/batch-group', async (req, res) => {
  const { ids, group } = req.body;
  if (!Array.isArray(ids) || !group) {
    return res.status(400).json({ success: false, error: 'Parámetros inválidos. Se requiere ids (array) y group (string).' });
  }
  try {
    await campaign.batchAssignGroup(ids, group);
    res.json({ success: true, message: `Grupo "${group}" asignado a ${ids.length} prospectos.` });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

app.get('/api/campaign/status', (req, res) => {
  res.json({
    success: true,
    data: campaign.getStatus()
  });
});

app.post('/api/campaign/start', async (req, res) => {
  try {
    const { delaySeconds, maxBatchSize, campaignName, targetGroup } = req.body;
    const result = await campaign.start({ delaySeconds, maxBatchSize, campaignName, targetGroup });
    res.json({ success: true, data: result });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

app.post('/api/campaign/pause', (req, res) => {
  const status = campaign.pause();
  res.json({ success: true, data: status });
});

app.post('/api/campaign/resume', (req, res) => {
  const status = campaign.resume();
  res.json({ success: true, data: status });
});

app.post('/api/campaign/stop', (req, res) => {
  const status = campaign.stop();
  res.json({ success: true, data: status });
});

// Iniciar servidor y cliente de WhatsApp
app.listen(PORT, async () => {
  console.log(`====================================================`);
  console.log(`🚀 Wally Bot Backend & Dashboard activo en:`);
  console.log(`👉 http://localhost:${PORT}`);
  console.log(`====================================================`);
  await whatsapp.init();
  try {
    const { getLocalWhisperPipeline } = require('./transcriber');
    getLocalWhisperPipeline().catch(err => {
      console.error('[Server] ⚠️ Aviso: Whisper Local no pudo precargarse:', err.message);
    });
  } catch (e) {}
});
