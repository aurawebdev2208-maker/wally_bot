import sys
import json
import psycopg2
import urllib.request
import ssl

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('E:/datos/proyectoIA/wally_bot/prospects.json', 'r', encoding='utf-8') as f:
    clean_prospects = json.load(f)

# Asegurar que todas las estéticas tengan 'Estética & Spa' y odontólogos tengan 'Odontología'
for p in clean_prospects:
    n = (p.get('niche') or p.get('group') or '').lower()
    if any(k in n for k in ['odont', 'dent', 'dient', 'ortodon']):
        p['niche'] = 'Odontología'
        p['group'] = 'Odontología'
    else:
        p['niche'] = 'Estética & Spa'
        p['group'] = 'Estética & Spa'

with open('E:/datos/proyectoIA/wally_bot/prospects.json', 'w', encoding='utf-8') as f:
    json.dump(clean_prospects, f, indent=2, ensure_ascii=False)

print(f"📊 Total prospectos limpios en prospects.json: {len(clean_prospects)}")

conn = psycopg2.connect(
    host='192.168.1.25',
    port=5432,
    user='postgres',
    password='6Ic19aZIVRd8nSTyPtsRx7L1tbjzyp08jTNRQFM1fJ1o3lfFIngjrZemRfdPzSHX',
    dbname='wally_aura_web'
)
cur = conn.cursor()

# 1. Truncar tabla para eliminar registros huérfanos con categorías viejas
cur.execute("TRUNCATE TABLE prospects;")

# 2. Insertar los 80 prospectos con categorías unificadas
for p in clean_prospects:
    cur.execute("""
        INSERT INTO prospects (id, business, name, niche, location, phone, custom_message, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW());
    """, (
        str(p['id']),
        p.get('business'),
        p.get('name'),
        p.get('niche'),
        p.get('location'),
        p.get('phone'),
        p.get('customMessage') or p.get('message'),
        p.get('status', 'PENDING')
    ))

conn.commit()

cur.execute("SELECT niche, count(*) FROM prospects GROUP BY niche;")
rows = cur.fetchall()
print("\n🐘 PostgreSQL Categorías Unificadas con Éxito:")
for r in rows:
    print(f"   -> {r[0]}: {r[1]} prospectos")

conn.close()

# 3. Sincronizar vía API de Wally Bot
try:
    ctx = ssl._create_unverified_context()
    login_req = urllib.request.Request(
        'https://wally_bot.dario10.pw/api/auth/login',
        data=json.dumps({'username': 'dorquera', 'password': 'tuxx6393'}).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    login_res = urllib.request.urlopen(login_req, context=ctx)
    token = json.loads(login_res.read().decode('utf-8'))['token']
    
    save_req = urllib.request.Request(
        'https://wally_bot.dario10.pw/api/prospects',
        data=json.dumps({'prospects': clean_prospects}).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    save_res = urllib.request.urlopen(save_req, context=ctx)
    print(f"\n🌐 Sincronizado con API Wally Bot: {save_res.read().decode('utf-8')}")
except Exception as api_err:
    print(f"Aviso API: {api_err}")
