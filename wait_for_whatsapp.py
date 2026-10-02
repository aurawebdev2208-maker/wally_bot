"""
Wait for WhatsApp Message from Dario to Antigravity
Monitorea la bandeja de entrada en tiempo real. En el milisegundo exacto en que
llega un mensaje desde WhatsApp, lo imprime y termina el proceso para despertar
inmediatamente a Antigravity en esta conversación.
"""

import sys
import time
import json
import urllib.request
import ssl

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "https://wally_bot.dario10.pw"

def wait_for_message():
    ctx = ssl._create_unverified_context()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/json'
    }

    # Autenticación
    try:
        login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
        res = urllib.request.urlopen(req, context=ctx)
        token = json.loads(res.read().decode('utf-8'))['token']
        headers['Authorization'] = f"Bearer {token}"
    except Exception as e:
        print(f"[Waiter] Error autenticando: {e}")
        return

    print("[Waiter] 👂 Escuchando WhatsApp en tiempo real para despertar a Antigravity...")
    sys.stdout.flush()

    while True:
        try:
            req = urllib.request.Request(f"{BASE_URL}/api/inbox/unread", headers=headers)
            res = urllib.request.urlopen(req, context=ctx)
            data = json.loads(res.read().decode('utf-8'))
            
            messages = data.get('messages', [])
            if messages:
                print("\n" + "="*60)
                print(f"🚨 [NUEVA SOLICITUD DE WHATSAPP PARA ANTIGRAVITY]")
                print("="*60)
                
                ids = []
                for m in messages:
                    sender = m.get('senderName', 'Darío Orquera')
                    phone = m.get('phone', '5493885104530')
                    text = m.get('messageText', '')
                    ids.append(m['id'])
                    
                    print(f"👤 De: {sender} ({phone})")
                    print(f"📝 Prompt para Antigravity:")
                    print(f">>> {text} <<<")
                
                # Marcar como procesados para que no se dupliquen
                ack_data = json.dumps({'ids': ids}).encode('utf-8')
                ack_req = urllib.request.Request(f"{BASE_URL}/api/inbox/ack", data=ack_data, headers=headers)
                urllib.request.urlopen(ack_req, context=ctx)
                print("="*60 + "\n")
                sys.stdout.flush()
                
                # TERMINA EL PROCESO para activar el Reactive Wakeup de Antigravity
                sys.exit(0)

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
        except Exception:
            pass

        time.sleep(1.5)

if __name__ == "__main__":
    wait_for_message()
