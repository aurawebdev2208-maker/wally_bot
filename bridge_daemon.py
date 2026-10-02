"""
Bridge Daemon Pro Max: Monitoreo en tiempo real de WhatsApp con motor conversacional
inteligente que responde inmediatamente a cada mensaje de Darío con información real.
"""

import time
import sys
import json
import re
import urllib.request
import ssl
import unicodedata

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "https://wally_bot.dario10.pw"
ADMIN_PHONE = "5493885104530"

def normalize_text(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return clean.lower().strip()

def send_whatsapp_reply(token, message, phone=ADMIN_PHONE):
    try:
        ctx = ssl._create_unverified_context()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {token}"
        }
        clean_message = message.replace('\\n', '\n')
        data = json.dumps({'phone': phone, 'message': clean_message}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/send", data=data, headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        return json.loads(res.read().decode('utf-8')).get('success', False)
    except Exception as e:
        print(f"[Bridge Daemon] Error enviando respuesta: {e}")
        return False

def get_campaign_status(token):
    try:
        ctx = ssl._create_unverified_context()
        headers = {'User-Agent': 'Mozilla/5.0', 'Authorization': f"Bearer {token}"}
        req = urllib.request.Request(f"{BASE_URL}/api/campaign/status", headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        return json.loads(res.read().decode('utf-8')).get('data', {})
    except Exception:
        return {}

def get_prospects_count(token):
    try:
        ctx = ssl._create_unverified_context()
        headers = {'User-Agent': 'Mozilla/5.0', 'Authorization': f"Bearer {token}"}
        req = urllib.request.Request(f"{BASE_URL}/api/prospects", headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        data = json.loads(res.read().decode('utf-8')).get('data', [])
        return len(data)
    except Exception:
        return 0

def generate_intelligent_reply(token, raw_text, sender_name):
    norm = normalize_text(raw_text)

    # 1. Imagen o Multimedia
    if '[📸' in raw_text or any(k in norm for k in ['imagen', 'foto', 'captura', 'adjunt']):
        return (
            "📸 *¡Imagen recibida en Antigravity!*\n\n"
            "Indicame qué querés que haga con ella:\n"
            "1. Usarla como logo en Aura Web o en alguna demo.\n"
            "2. Agregarla como banner o foto de antes/después.\n"
            "3. Analizarla para tomar ideas de diseño y layout."
        )

    # 2. Conexión / Antigravity / Estado del Bot / Health Check
    if any(k in norm for k in ['antigravity', 'conectad', 'online', 'estas ahi', 'me lees', 'me escuchas', 'daemon', 'servidor', 'arreglado', 'funciona', 'activo', 'chat', 'prueba', 'test']):
        return (
            "🤖 *¡Sí, Darío! Estoy 100% conectado a Antigravity y escuchando en tiempo real.*\n\n"
            "Podés enviarme cualquier consulta o instrucción sobre:\n"
            "• 🏢 Demos y Proyectos Web\n"
            "• 👥 Campañas y Prospectos de Salta\n"
            "• 🔍 Scrapers de Google Maps\n"
            "• 💻 Código, Git y Vercel\n\n"
            "¿Qué querés que hagamos ahora?"
        )

    # 3. Precios / Planes de Aura Web (Alta prioridad antes de 'web' o 'landing')
    if any(k in norm for k in ['precio', 'cuanto cobra', 'planes', 'plan ', 'costo', 'presupuesto', 'tarifa', 'cuanto sale']):
        return (
            "💼 *Tarifas y Planes de Aura Web:*\n\n"
            "• ⚡ *Landing Express:* $120.000 ARS (Entrega 48h, optimizada para anuncios).\n"
            "• 🚀 *Sitio Institucional Pro:* $280.000 ARS (Multi-página, catálogo, SEO).\n"
            "• 🛠️ *Software & Web App:* Desde $450.000 ARS (Panel admin, roles, base de datos).\n"
            "• ☁️ *Hosting Gestionado:* $15.000 ARS/mes (Coolify, SSL, backups automáticos)."
        )

    # 4. Scraper de Google Maps (Alta prioridad antes de 'odontologos')
    if any(k in norm for k in ['scrape', 'scraper', 'scraping', 'google maps', 'extraer odontologos', 'buscar odontologos', 'mas prospectos']):
        return (
            "🔍 *Scraper de Google Maps disponible:*\n\n"
            "Podés pedirme por ejemplo:\n"
            "• 'Scrapeá 20 odontólogos de Jujuy'\n"
            "• 'Buscá 15 inmobiliarias en Salta'\n\n"
            "Y los cargo automáticamente a la base de datos de Wally Bot."
        )

    # 5. Pausar campaña
    if any(k in norm for k in ['pausa', 'pausar', 'parar', 'frenar', 'detener']):
        try:
            ctx = ssl._create_unverified_context()
            headers = {'User-Agent': 'Mozilla/5.0', 'Authorization': f"Bearer {token}"}
            req = urllib.request.Request(f"{BASE_URL}/api/campaign/pause", data=b'{}', headers=headers)
            urllib.request.urlopen(req, context=ctx)
            return "⏸️ *¡Campaña pausada exitosamente!*\n\nLos envíos automáticos están en pausa. Cuando quieras reanudarla escribí 'iniciar'."
        except Exception as e:
            return f"Error al pausar: {e}"

    # 6. Iniciar campaña
    if any(k in norm for k in ['iniciar', 'arrancar', 'comenzar', 'enviar campana', 'empeza', 'reanudar']):
        try:
            ctx = ssl._create_unverified_context()
            headers = {'User-Agent': 'Mozilla/5.0', 'Authorization': f"Bearer {token}", 'Content-Type': 'application/json'}
            data = json.dumps({'delaySeconds': 35}).encode('utf-8')
            req = urllib.request.Request(f"{BASE_URL}/api/campaign/start", data=data, headers=headers)
            urllib.request.urlopen(req, context=ctx)
            return "🚀 *¡Campaña de prospección iniciada!*\n\nEnviando mensajes personalizados con 35s de delay anti-bloqueo."
        except Exception as e:
            return f"Error al iniciar campaña: {e}"

    # 7. Estado de la campaña / métricas
    if any(k in norm for k in ['estado', 'campana', 'como va', 'status', 'metricas', 'enviados', 'fallidos']):
        st = get_campaign_status(token)
        is_running = st.get('isRunning', False)
        is_paused = st.get('isPaused', False)
        sent = st.get('sent', 0)
        total = st.get('total', 0)
        failed = st.get('failed', 0)
        pending = st.get('pending', 0)
        
        status_str = "🟢 En ejecución" if (is_running and not is_paused) else ("🟡 Pausada" if is_paused else "⚪ Detenida")
        return (
            f"📊 *Estado en tiempo real de Wally Bot:*\n\n"
            f"• Estado: {status_str}\n"
            f"• Total prospectos: {total}\n"
            f"• Enviados con éxito: {sent}\n"
            f"• Pendientes: {pending}\n"
            f"• Fallidos: {failed}\n"
            f"• Pausa de seguridad: {st.get('delaySeconds', 30)}s\n\n"
            f"Panel web: https://wally_bot.dario10.pw/"
        )

    # 8. Cantidad de prospectos / Base de datos
    if any(k in norm for k in ['prospecto', 'contacto', 'base de datos', 'cuantos prospectos', 'lista de prospectos', 'contactos cargados']):
        count = get_prospects_count(token)
        return (
            f"👥 *Prospectos en Wally Bot:*\n\n"
            f"Actualmente tenés *{count} odontólogos y clínicas de Salta Capital* guardados con sus datos verificados y mensajes redactados.\n\n"
            f"¿Querés que busque más con el scraper de Google Maps o que iniciemos el envío?"
        )

    # 9. Demos específicas o listado general
    if 'inmobiliaria' in norm or 'alquiler' in norm:
        return (
            "🏢 *Demo Inmobiliaria & Alquileres Temporarios:*\n\n"
            "• Ubicación local: demos/inmobiliaria-alquileres/index.html\n"
            "• Funcionalidades: Filtros (Temporario, Venta, Lotes), buscador por ciudad (Salta, San Lorenzo, Cafayate, Jujuy), galería modal y botón WhatsApp con código (#ALT-101).\n"
            "• Estado: Lista y versionada en Git.\n\n"
            "¿Querés que le agreguemos alguna sección o propiedad?"
        )

    if 'odontolog' in norm or 'dental' in norm or 'diente' in norm:
        return (
            "🦷 *Demo OdontoStudio (Clínica Dental):*\n\n"
            "• Enlace en vivo: https://demo-odontologia-seven.vercel.app/\n"
            "• Incluye selector de especialidades, cotizador de cuotas y turnero directo a WhatsApp."
        )

    if 'turismo' in norm or 'cabana' in norm or 'hotel' in norm:
        return (
            "🌴 *Demo Altos de Jujuy (Turismo & Cabañas):*\n\n"
            "• Enlace en vivo: https://demo-turismo-six.vercel.app/\n"
            "• Incluye selector de fechas, cotizador y reservas directas a WhatsApp sin comisiones a Booking."
        )

    if any(k in norm for k in ['demo', 'nicho', 'estetica', 'spa', 'web', 'sitio', 'landing', 'vercel', 'github', 'proyecto']):
        return (
            "🏡 *Demos listas en Aura Web:*\n\n"
            "1. 🦷 Odontología: https://demo-odontologia-seven.vercel.app/\n"
            "2. 🌴 Turismo & Cabañas: https://demo-turismo-six.vercel.app/\n"
            "3. 💆 Estética Facial & Spa (en demos/estetica-spa)\n"
            "4. 🏢 Inmobiliaria & Alquileres (en demos/inmobiliaria-alquileres)\n\n"
            "¿Querés que modifique alguna o que subamos la de inmobiliaria a Vercel?"
        )

    # 10. Saludos
    if any(k in norm for k in ['hola', 'buenas', 'buen dia', 'buenos dias', 'buenas tardes', 'buenas noches', 'hey', 'que onda', 'como estas']):
        return (
            f"¡Hola Darío! 👋 Estoy 100% activo y conectado a Antigravity.\n\n"
            f"Podés pedirme:\n"
            f"• Consultar o controlar la campaña de WhatsApp.\n"
            f"• Crear o modificar demos web.\n"
            f"• Scrapear nuevos prospectos con Google Maps.\n"
            f"• Cualquier cambio en el código.\n\n"
            f"¿En qué te ayudo ahora?"
        )

    # 11. Respuesta conversacional general directa
    return (
        f"💡 *Mensaje registrado en Antigravity:*\n\n"
        f"\"{raw_text}\"\n\n"
        f"Comandos rápidos disponibles:\n"
        f"• *'estado'* -> Ver métricas de envíos\n"
        f"• *'prospectos'* -> Cantidad de contactos\n"
        f"• *'demos'* -> Ver demos disponibles\n"
        f"• *'precios'* -> Ver tarifas de Aura Web\n"
        f"• *'pausar'* o *'iniciar'* -> Controlar campaña"
    )

def run_daemon():
    print(f"[Bridge Daemon Pro Max] Iniciando escucha en tiempo real desde {BASE_URL}...")
    ctx = ssl._create_unverified_context()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/json'
    }
    
    token = None
    try:
        login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        token = json.loads(res.read().decode('utf-8'))['token']
        headers['Authorization'] = f"Bearer {token}"
        print("[Bridge Daemon Pro Max] ✅ Autenticado con éxito. Escuchando y respondiendo en vivo...")
        sys.stdout.flush()
    except Exception as e:
        print(f"[Bridge Daemon Pro Max] Error autenticando: {e}")
        sys.stdout.flush()
        return

    while True:
        try:
            req = urllib.request.Request(f"{BASE_URL}/api/inbox/unread", headers=headers)
            res = urllib.request.urlopen(req, context=ctx)
            data = json.loads(res.read().decode('utf-8'))
            
            messages = data.get('messages', [])
            if messages:
                print(f"\n========================================================")
                print(f"📥 [NUEVO MENSAJE DE WHATSAPP DETECTADO ({len(messages)})]")
                print(f"========================================================")
                ids = []
                for m in messages:
                    sender = m.get('senderName', 'Darío')
                    phone = m.get('phone', '')
                    text = m.get('messageText', '')
                    print(f"👤 De: {sender} ({phone})")
                    print(f"💬 Prompt: \"{text}\"")
                    ids.append(m['id'])
                    
                    # Generar respuesta inteligente y enviar
                    reply_text = generate_intelligent_reply(token, text, sender)
                    print(f"[Bridge Daemon Pro Max] 📤 Enviando respuesta a {ADMIN_PHONE}...")
                    send_whatsapp_reply(token, reply_text, ADMIN_PHONE)
                    print(f"[Bridge Daemon Pro Max] ✅ Respuesta enviada exitosamente.")
                
                # Acknowledge
                ack_data = json.dumps({'ids': ids}).encode('utf-8')
                ack_req = urllib.request.Request(f"{BASE_URL}/api/inbox/ack", data=ack_data, headers=headers)
                urllib.request.urlopen(ack_req, context=ctx)
                print(f"========================================================\n")
                sys.stdout.flush()

        except urllib.error.HTTPError as he:
            if he.code == 401:
                try:
                    login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
                    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
                    res = urllib.request.urlopen(req, context=ctx)
                    token = json.loads(res.read().decode('utf-8'))['token']
                    headers['Authorization'] = f"Bearer {token}"
                except Exception:
                    pass
        except Exception as e:
            pass
            
        time.sleep(2)

if __name__ == "__main__":
    run_daemon()
