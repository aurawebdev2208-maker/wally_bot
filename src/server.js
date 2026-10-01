const express = require('express');
const cors = require('cors');
const path = require('path');
const whatsapp = require('./whatsapp');
const campaign = require('./campaign');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, '..', 'public')));

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
