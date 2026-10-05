import urllib.request, json, ssl

ctx = ssl._create_unverified_context()
req = urllib.request.Request(
    'https://wally_bot.dario10.pw/api/auth/login',
    data=json.dumps({'username': 'dorquera', 'password': 'tuxx6393'}).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
)
resp = urllib.request.urlopen(req, context=ctx)
token = json.loads(resp.read().decode())['token']

message = """¡FUNCIONÓ PERFECTO! 🎙️🎉

Whisper Local en Coolify transcribió tu nota de voz en tiempo real:
"Ahora, entonces yo que tenia un video por audio."

¡Ya podés darme órdenes por audio cuando quieras! ¿Qué querés que hagamos ahora?"""

msg_data = json.dumps({'phone': '5493885104530', 'message': message}).encode('utf-8')
req2 = urllib.request.Request(
    'https://wally_bot.dario10.pw/api/send',
    data=msg_data,
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
)
resp2 = urllib.request.urlopen(req2, context=ctx)
print(resp2.read().decode())
