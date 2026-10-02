import sys
import psycopg2
from psycopg2.extras import RealDictCursor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    conn = psycopg2.connect(
        host='192.168.1.25',
        port=5432,
        user='postgres',
        password='6Ic19aZIVRd8nSTyPtsRx7L1tbjzyp08jTNRQFM1fJ1o3lfFIngjrZemRfdPzSHX',
        dbname='wally_aura_web'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=== MESSAGES TABLE ===")
    cur.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 25;")
    rows = cur.fetchall()
    for r in rows:
        print(f"[{r.get('created_at')}] id={r.get('id')} sender={r.get('sender_name')} phone={r.get('phone')} text={r.get('message_text')}")

    print("\n=== INBOX_MESSAGES TABLE ===")
    cur.execute("SELECT * FROM inbox_messages ORDER BY created_at DESC LIMIT 10;")
    rows2 = cur.fetchall()
    for r in rows2:
        print(f"[{r.get('created_at')}] id={r.get('id')} sender={r.get('sender_name')} phone={r.get('phone')} text={r.get('message_text')} processed={r.get('processed')}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
