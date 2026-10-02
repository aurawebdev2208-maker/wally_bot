"""
WhatsApp <-> Antigravity Bridge Client
Monitorea mensajes entrantes de Darío enviados por WhatsApp a Wally Bot,
y envía respuestas directamente desde Antigravity a su celular.
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
ADMIN_PHONE = "5493885104530"

class WhatsAppBridge:
    def __init__(self, base_url=BASE_URL, username="antig", password="antig6393"):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.ctx = ssl._create_unverified_context()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Content-Type': 'application/json'
        }
        self.login()

    def login(self):
        try:
            data = json.dumps({'username': self.username, 'password': self.password}).encode('utf-8')
            req = urllib.request.Request(f"{self.base_url}/api/auth/login", data=data, headers=self.headers)
            res = urllib.request.urlopen(req, context=self.ctx)
            json_res = json.loads(res.read().decode('utf-8'))
            if json_res.get('success') and json_res.get('token'):
                self.token = json_res['token']
                self.headers['Authorization'] = f"Bearer {self.token}"
                return True
        except Exception as e:
            print(f"[Bridge] Error en login con Wally Bot: {e}")
            return False

    def get_unread_messages(self):
        try:
            req = urllib.request.Request(f"{self.base_url}/api/inbox/unread", headers=self.headers)
            res = urllib.request.urlopen(req, context=self.ctx)
            json_res = json.loads(res.read().decode('utf-8'))
            if json_res.get('success'):
                return json_res.get('messages', [])
        except urllib.error.HTTPError as he:
            if he.code == 401:
                self.login()
        except Exception as e:
            print(f"[Bridge] Error consultando unread: {e}")
        return []

    def mark_processed(self, ids):
        if not ids:
            return True
        try:
            data = json.dumps({'ids': ids}).encode('utf-8')
            req = urllib.request.Request(f"{self.base_url}/api/inbox/ack", data=data, headers=self.headers)
            res = urllib.request.urlopen(req, context=self.ctx)
            json_res = json.loads(res.read().decode('utf-8'))
            return json_res.get('success', False)
        except Exception as e:
            print(f"[Bridge] Error marcando ack: {e}")
            return False

    def send_reply(self, message, phone=ADMIN_PHONE):
        try:
            clean_message = message.replace('\\n', '\n')
            data = json.dumps({'phone': phone, 'message': clean_message}).encode('utf-8')
            req = urllib.request.Request(f"{self.base_url}/api/send", data=data, headers=self.headers)
            res = urllib.request.urlopen(req, context=self.ctx)
            json_res = json.loads(res.read().decode('utf-8'))
            return json_res.get('success', False)
        except Exception as e:
            print(f"[Bridge] Error enviando respuesta WhatsApp: {e}")
            return False

    def check_once(self):
        msgs = self.get_unread_messages()
        if msgs:
            print(f"\n========================================================")
            print(f"📥 [NUEVOS MENSAJES DE WHATSAPP RECIBIDOS ({len(msgs)})]")
            print(f"========================================================")
            ids_to_ack = []
            for m in msgs:
                sender = m.get('senderName', 'Darío')
                phone = m.get('phone', '')
                text = m.get('messageText', '')
                print(f"\n📱 De: {sender} ({phone})")
                print(f"💬 Mensaje / Prompt: \"{text}\"")
                ids_to_ack.append(m['id'])
            
            self.mark_processed(ids_to_ack)
            return msgs
        return []

if __name__ == "__main__":
    bridge = WhatsAppBridge()
    if len(sys.argv) > 1 and sys.argv[1] == "--send":
        # Enviar mensaje rápido
        reply_msg = sys.argv[2] if len(sys.argv) > 2 else "Mensaje de prueba"
        target_phone = sys.argv[3] if len(sys.argv) > 3 else ADMIN_PHONE
        ok = bridge.send_reply(reply_msg, target_phone)
        print(f"Envío {'exitoso' if ok else 'fallido'}")
    else:
        # Chequear mensajes pendientes
        bridge.check_once()
