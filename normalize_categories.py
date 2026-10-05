import sys
import json
import psycopg2
import urllib.request
import ssl

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = psycopg2.connect(
    host='192.168.1.25',
    port=5432,
    user='postgres',
    password='6Ic19aZIVRd8nSTyPtsRx7L1tbjzyp08jTNRQFM1fJ1o3lfFIngjrZemRfdPzSHX',
    dbname='wally_aura_web'
)
cur = conn.cursor()

print("=== ACTUALIZANDO NICHOS EN POSTGRESQL ===")

# Normalizar cualquier variante de Estética a 'Estética & Spa'
cur.execute("""
    UPDATE prospects 
    SET niche = 'Estética & Spa'
    WHERE niche ILIKE '%estet%' 
       OR niche ILIKE '%spa%' 
       OR niche ILIKE '%facial%' 
       OR niche ILIKE '%corporal%' 
       OR niche ILIKE '%cosmet%' 
       OR niche ILIKE '%depil%' 
       OR niche ILIKE '%belleza%'
       OR niche ILIKE '%dermo%';
""")

# Normalizar cualquier variante de Odontología a 'Odontología'
cur.execute("""
    UPDATE prospects 
    SET niche = 'Odontología'
    WHERE niche ILIKE '%odont%' 
       OR niche ILIKE '%dent%' 
       OR niche ILIKE '%dient%' 
       OR niche ILIKE '%ortodon%';
""")

conn.commit()

# Verificación
cur.execute("SELECT niche, count(*) FROM prospects GROUP BY niche;")
rows = cur.fetchall()
print("Postgres niches después de normalizar:")
for r in rows:
    print(f" - {r[0]}: {r[1]} prospectos")

conn.close()

# También sincronizar prospects.json
prospects_file = 'E:/datos/proyectoIA/wally_bot/prospects.json'
with open(prospects_file, 'r', encoding='utf-8') as f:
    prospects = json.load(f)

for p in prospects:
    n = (p.get('niche') or '').lower()
    if any(k in n for k in ['estet', 'spa', 'facial', 'corporal', 'cosmet', 'depil', 'belleza', 'dermo']):
        p['niche'] = 'Estética & Spa'
        p['group'] = 'Estética & Spa'
    elif any(k in n for k in ['odont', 'dent', 'dient', 'ortodon']):
        p['niche'] = 'Odontología'
        p['group'] = 'Odontología'
    else:
        p['niche'] = 'Estética & Spa'
        p['group'] = 'Estética & Spa'

with open(prospects_file, 'w', encoding='utf-8') as f:
    json.dump(prospects, f, indent=2, ensure_ascii=False)

print(f"\n💾 prospects.json actualizado con {len(prospects)} prospectos en macro-categorías.")

# Sincronizar vía API de Wally Bot
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
        data=json.dumps({'prospects': prospects}).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    save_res = urllib.request.urlopen(save_req, context=ctx)
    print(f"🌐 Sincronizado con API Wally Bot: {save_res.read().decode('utf-8')}")
except Exception as api_err:
    print(f"Aviso API: {api_err}")
