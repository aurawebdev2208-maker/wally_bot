require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const crypto = require('crypto');
const whatsapp = require('./whatsapp');
const campaign = require('./campaign');

const app = express();
const PORT = process.env.PORT || 3000;

const AUTH_USER = process.env.AUTH_USER || 'dorquera';
const AUTH_PASSWORD = process.env.AUTH_PASSWORD || 'tuxx6393';
const AUTH_SECRET = process.env.AUTH_SECRET || 'wally_bot_secret_aura_2026';

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
app.use(express.static(path.join(__dirname, '..', 'public')));

// === API AUTH ===
app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body || {};
  if (username === AUTH_USER && password === AUTH_PASSWORD) {
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

app.get('/api/campaign/status', (req, res) => {
  res.json({
    success: true,
    data: campaign.getStatus()
  });
});

app.post('/api/campaign/start', async (req, res) => {
  try {
    const { delaySeconds, campaignName } = req.body;
    const result = await campaign.start({ delaySeconds, campaignName });
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
});
