const https = require('https');

/**
 * Transcribe un buffer de audio de WhatsApp a texto utilizando IA (Gemini, Groq Whisper u OpenAI Whisper).
 * @param {Buffer} audioBuffer - Buffer binario del archivo de audio descargado por Baileys.
 * @param {string} mimeType - Tipo MIME del audio (ej. 'audio/ogg; codecs=opus' o 'audio/mp4').
 * @returns {Promise<string|null>} - Texto transcrito o null si falló.
 */
async function transcribeAudio(audioBuffer, mimeType = 'audio/ogg; codecs=opus') {
  if (!audioBuffer || audioBuffer.length === 0) return null;

  const geminiKey = process.env.GEMINI_API_KEY;
  const groqKey = process.env.GROQ_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;

  // 1. Intentar con Google Gemini (Recomendado: modelo multimodal nativo en español)
  if (geminiKey) {
    try {
      const cleanMime = mimeType.split(';')[0].trim() || 'audio/ogg';
      const base64Audio = audioBuffer.toString('base64');
      
      const payload = JSON.stringify({
        contents: [
          {
            parts: [
              {
                text: "Transcribe exactamente el siguiente audio hablado en español. Devuelve ÚNICAMENTE la transcripción literal del mensaje, sin introducciones, sin comillas, sin explicaciones ni formato adicional."
              },
              {
                inline_data: {
                  mime_type: cleanMime,
                  data: base64Audio
                }
              }
            ]
          }
        ],
        generationConfig: {
          temperature: 0.1
        }
      });

      const result = await makeHttpsRequest({
        hostname: 'generativelanguage.googleapis.com',
        path: `/v1beta/models/gemini-2.5-flash:generateContent?key=${geminiKey}`,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      }, payload);

      const parsed = JSON.parse(result);
      const text = parsed.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
      if (text) {
        console.log(`[Transcriber] ✨ Transcripción Gemini exitosa: "${text}"`);
        return text;
      }
    } catch (err) {
      console.error('[Transcriber] Error con Gemini API:', err.message);
    }
  }

  // 2. Intentar con Groq Whisper API (Ultra rápido)
  if (groqKey) {
    try {
      const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);
      const parts = [
        `--${boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-large-v3\r\n`,
        `--${boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nes\r\n`,
        `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.ogg"\r\nContent-Type: audio/ogg\r\n\r\n`
      ];

      const preBuffer = Buffer.from(parts.join(''), 'utf-8');
      const postBuffer = Buffer.from(`\r\n--${boundary}--\r\n`, 'utf-8');
      const fullBody = Buffer.concat([preBuffer, audioBuffer, postBuffer]);

      const result = await makeHttpsRequest({
        hostname: 'api.groq.com',
        path: '/openai/v1/audio/transcriptions',
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${groqKey}`,
          'Content-Type': `multipart/form-data; boundary=${boundary}`,
          'Content-Length': fullBody.length
        }
      }, fullBody);

      const parsed = JSON.parse(result);
      if (parsed.text) {
        console.log(`[Transcriber] ✨ Transcripción Groq Whisper exitosa: "${parsed.text.trim()}"`);
        return parsed.text.trim();
      }
    } catch (err) {
      console.error('[Transcriber] Error con Groq Whisper:', err.message);
    }
  }

  // 3. Intentar con OpenAI Whisper
  if (openaiKey) {
    try {
      const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);
      const parts = [
        `--${boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n`,
        `--${boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nes\r\n`,
        `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.ogg"\r\nContent-Type: audio/ogg\r\n\r\n`
      ];

      const preBuffer = Buffer.from(parts.join(''), 'utf-8');
      const postBuffer = Buffer.from(`\r\n--${boundary}--\r\n`, 'utf-8');
      const fullBody = Buffer.concat([preBuffer, audioBuffer, postBuffer]);

      const result = await makeHttpsRequest({
        hostname: 'api.openai.com',
        path: '/v1/audio/transcriptions',
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${openaiKey}`,
          'Content-Type': `multipart/form-data; boundary=${boundary}`,
          'Content-Length': fullBody.length
        }
      }, fullBody);

      const parsed = JSON.parse(result);
      if (parsed.text) {
        console.log(`[Transcriber] ✨ Transcripción OpenAI exitosa: "${parsed.text.trim()}"`);
        return parsed.text.trim();
      }
    } catch (err) {
      console.error('[Transcriber] Error con OpenAI Whisper:', err.message);
    }
  }

  return null;
}

function makeHttpsRequest(options, body) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(data);
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', (e) => reject(e));
    if (body) {
      req.write(body);
    }
    req.end();
  });
}

module.exports = {
  transcribeAudio
};
