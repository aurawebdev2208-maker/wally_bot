"""
Bridge Daemon: Monitorea mensajes entrantes de WhatsApp en tiempo real,
gestiona comandos rápidos y conecta con Antigravity.
"""

import time
import sys
import json
import urllib.request
import ssl

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "https://wally_bot.dario10.pw"
ADMIN_PHONE = "5493885104530"

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
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Authorization': f"Bearer {token}"
        }
        req = urllib.request.Request(f"{BASE_URL}/api/campaign/status", headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        return json.loads(res.read().decode('utf-8')).get('data', {})
    except Exception:
        return {}

def get_prospects_count(token):
    try:
        ctx = ssl._create_unverified_context()
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Authorization': f"Bearer {token}"
        }
        req = urllib.request.Request(f"{BASE_URL}/api/prospects", headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        data = json.loads(res.read().decode('utf-8')).get('data', [])
        return len(data)
    except Exception:
        return 0

def process_prompt_and_reply(token, prompt_text, sender_name, sender_jid):
    text = prompt_text.strip().lower()
    print(f"\n[Bridge Daemon] 📥 Mensaje de {sender_name}: '{prompt_text}'")

    reply = None

    if text in ['hola', 'test', 'prueba']:
        reply = (
            f"¡Hola Darío! 👋 Sí, estoy activo y escuchando perfectamente desde tu entorno de desarrollo. "
            f"Podés pedirme ver el estado de la campaña, prospectos o cualquier tarea de código."
        )
    elif text in ['estado', 'campaña', 'como va', 'status']:
        st = get_campaign_status(token)
        is_running = st.get('isRunning', False)
        is_paused = st.get('isPaused', False)
        sent = st.get('sent', 0)
        total = st.get('total', 0)
        failed = st.get('failed', 0)
        pending = st.get('pending', 0)
        
        status_str = "🟢 En ejecución" if (is_running and not is_paused) else ("🟡 Pausada" if is_paused else "⚪ Detenida")
        reply = (
            f"📊 *Estado de la Campaña:*\n\n"
            f"• Estado: {status_str}\n"
            f"• Total: {total}\n"
            f"• Enviados: {sent}\n"
            f"• Pendientes: {pending}\n"
            f"• Fallidos: {failed}\n\n"
            f"Panel: https://wally_bot.dario10.pw/"
        )
    elif text in ['prospectos', 'cuantos prospectos']:
        count = get_prospects_count(token)
        reply = f"👥 Actualmente tenés *{count} prospectos* cargados en Wally Bot."
    elif text == 'pausar':
        try:
            ctx = ssl._create_unverified_context()
            headers = {'User-Agent': 'Mozilla/5.0', 'Authorization': f"Bearer {token}"}
            req = urllib.request.Request(f"{BASE_URL}/api/campaign/pause", data=b'{}', headers=headers)
            urllib.request.urlopen(req, context=ctx)
            reply = "⏸️ Campaña pausada exitosamente."
        except Exception as e:
            reply = f"Error al pausar: {e}"

    if reply:
        print(f"[Bridge Daemon] 📤 Enviando respuesta automática a WhatsApp...")
        send_whatsapp_reply(token, reply, ADMIN_PHONE)
    else:
        print(f"[Bridge Daemon] ℹ️ Mensaje complejo registrado para atención directa de Antigravity.")

def run_daemon():
    print(f"[Bridge Daemon] Iniciando escucha en tiempo real desde {BASE_URL}...")
    ctx = ssl._create_unverified_context()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/json'
    }
    
    # Login
    token = None
    try:
        login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        token = json.loads(res.read().decode('utf-8'))['token']
        headers['Authorization'] = f"Bearer {token}"
        print("[Bridge Daemon] ✅ Autenticado con éxito. Escuchando mensajes de WhatsApp en vivo...")
    except Exception as e:
        print(f"[Bridge Daemon] Error autenticando: {e}")
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
                    remote_jid = m.get('remoteJid', '')
                    print(f"👤 De: {sender} ({phone})")
                    print(f"💬 Prompt: \"{text}\"")
                    ids.append(m['id'])
                    
                    process_prompt_and_reply(token, text, sender, remote_jid)
                
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
            
        time.sleep(3)

if __name__ == "__main__":
    run_daemon()
