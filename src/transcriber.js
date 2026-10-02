const https = require('https');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let transcriberPipeline = null;
let ffmpegPath = null;

try {
  ffmpegPath = require('ffmpeg-static');
} catch (e) {
  ffmpegPath = 'ffmpeg';
}

/**
 * Convierte un buffer de audio (ej: OGG/Opus de WhatsApp) a WAV PCM 16kHz mono.
 */
function convertAudioToWav16k(audioBuffer) {
  return new Promise((resolve, reject) => {
    const ffmpeg = spawn(ffmpegPath, [
      '-i', 'pipe:0',
      '-ar', '16000',
      '-ac', '1',
      '-f', 'wav',
      'pipe:1'
    ]);

    const chunks = [];
    ffmpeg.stdout.on('data', (chunk) => chunks.push(chunk));
    ffmpeg.stderr.on('data', () => {}); // Silenciar logs de ffmpeg

    ffmpeg.on('close', (code) => {
      if (code === 0) {
        resolve(Buffer.concat(chunks));
      } else {
        reject(new Error(`ffmpeg salió con código ${code}`));
      }
    });

    ffmpeg.on('error', (err) => reject(err));

    ffmpeg.stdin.write(audioBuffer);
    ffmpeg.stdin.end();
  });
}

/**
 * Carga e inicializa el modelo Whisper Local (@xenova/transformers).
 */
async function getLocalWhisperPipeline() {
  if (!transcriberPipeline) {
    console.log('[Transcriber] ⏳ Inicializando modelo Whisper Local (Xenova/whisper-tiny) en memoria...');
    const { pipeline, env } = await import('@xenova/transformers');
    
    // Configurar cache local de modelos
    env.cacheDir = path.join(__dirname, '..', '.cache_models');
    env.allowLocalModels = true;

    transcriberPipeline = await pipeline('automatic-speech-recognition', 'Xenova/whisper-tiny', {
      quantized: true
    });
    console.log('[Transcriber] ✅ Modelo Whisper Local cargado y listo para transcribir sin API Key.');
  }
  return transcriberPipeline;
}

/**
 * Transcribe un buffer de audio localmente con Whisper (100% Offline, sin API Key).
 */
async function transcribeWithLocalWhisper(audioBuffer) {
  try {
    console.log('[Transcriber] 🎙️ Decodificando audio para Whisper Local...');
    const wavBuffer = await convertAudioToWav16k(audioBuffer);
    
    const { WaveFile } = require('wavefile');
    const wav = new WaveFile(wavBuffer);
    wav.toBitDepth('32f');
    wav.toSampleRate(16000);
    let audioData = wav.getSamples();
    if (Array.isArray(audioData)) {
      audioData = audioData[0];
    }

    const pipe = await getLocalWhisperPipeline();
    console.log('[Transcriber] 🧠 Transcribiendo nota de voz con Whisper Local...');
    const result = await pipe(audioData, {
      language: 'spanish',
      task: 'transcribe'
    });

    if (result && result.text) {
      const cleanText = result.text.trim();
      console.log(`[Transcriber] ✨ Transcripción Whisper Local completada: "${cleanText}"`);
      return cleanText;
    }
  } catch (err) {
    console.error('[Transcriber] Error en transcripción Whisper Local:', err.message);
  }
  return null;
}

/**
 * Transcribe un buffer de audio de WhatsApp a texto utilizando IA (Whisper Local, Gemini o Groq).
 * @param {Buffer} audioBuffer - Buffer binario del archivo de audio descargado por Baileys.
 * @param {string} mimeType - Tipo MIME del audio.
 * @returns {Promise<string|null>} - Texto transcrito o null si falló.
 */
async function transcribeAudio(audioBuffer, mimeType = 'audio/ogg; codecs=opus') {
  if (!audioBuffer || audioBuffer.length === 0) return null;

  const geminiKey = process.env.GEMINI_API_KEY;
  const groqKey = process.env.GROQ_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;

  // 1. Si hay clave de Gemini API, usarla (ultrarrápida y multimodal)
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

  // 2. Si hay clave de Groq Whisper API
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

  // 3. WHISPER LOCAL (Por defecto: 100% autónomo, 0 API Key, corre en tu servidor)
  console.log('[Transcriber] 🚀 Ejecutando Whisper Local en el servidor (sin API Key)...');
  const localResult = await transcribeWithLocalWhisper(audioBuffer);
  if (localResult) {
    return localResult;
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
  transcribeAudio,
  getLocalWhisperPipeline
};
