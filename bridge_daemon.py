"""
Bridge Daemon: Monitorea mensajes entrantes de WhatsApp continuamente
y notifica a Antigravity en tiempo real.
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

def run_daemon():
    print(f"[Bridge Daemon] Iniciando escucha en tiempo real desde {BASE_URL}...")
    ctx = ssl._create_unverified_context()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/json'
    }
    
    # 1. Login
    try:
        login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        token = json.loads(res.read().decode('utf-8'))['token']
        headers['Authorization'] = f"Bearer {token}"
        print("[Bridge Daemon] ✅ Autenticado con éxito. Esperando mensajes de WhatsApp...")
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
                print(f"📥 [MENSAJE RECIBIDO DE WHATSAPP]")
                print(f"========================================================")
                ids = []
                for m in messages:
                    sender = m.get('senderName', 'Darío')
                    phone = m.get('phone', '')
                    text = m.get('messageText', '')
                    print(f"👤 De: {sender} ({phone})")
                    print(f"💬 Prompt: \"{text}\"")
                    print(f"⏰ Fecha: {m.get('createdAt', '')}")
                    ids.append(m['id'])
                
                # Acknowledge
                ack_data = json.dumps({'ids': ids}).encode('utf-8')
                ack_req = urllib.request.Request(f"{BASE_URL}/api/inbox/ack", data=ack_data, headers=headers)
                urllib.request.urlopen(ack_req, context=ctx)
                print(f"========================================================\n")
                sys.stdout.flush()

        except urllib.error.HTTPError as he:
            if he.code == 401:
                # Re-login
                try:
                    login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
                    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
                    res = urllib.request.urlopen(req, context=ctx)
                    token = json.loads(res.read().decode('utf-8'))['token']
                    headers['Authorization'] = f"Bearer {token}"
                except Exception:
                    pass
        except Exception as e:
            # Silently retry on intermittent network glitch
            pass
            
        time.sleep(3)

if __name__ == "__main__":
    run_daemon()
