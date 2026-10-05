import sys
import json
import urllib.request
import ssl
import psycopg2

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def generate_short_msg(name, business_name, has_real_web=False):
    saludo_name = f" {name}" if name and name not in ['Profesional', 'Equipo', ''] else f" {business_name}"
    demo_url = "https://auradev.online/demo/estetica/"
    
    if has_real_web:
        return (
            f"¡Hola{saludo_name}! ¿Cómo está? Le escribo de Aura Web. Vimos el sitio web de {business_name} y le escribo porque nos especializamos en rediseñar y modernizar páginas existentes, optimizándolas al 100% para celulares con cotizador de tratamientos y turnero directo a WhatsApp.\n\n"
            f"Le comparto una demo en vivo: {demo_url} - Si le gustaría ver una propuesta de renovación sin costo para {business_name}, quedo a su disposición. ¡Que tenga un gran día!"
        )
    else:
        return (
            f"¡Hola{saludo_name}! ¿Cómo está? Le escribo de Aura Web. Desarrollamos páginas web para centros de estética y spas, 100% optimizadas para celulares, con cotizador de packs y turnero directo a WhatsApp.\n\n"
            f"Le comparto una demo en vivo: {demo_url} - Si le gustaría ver una maqueta sin costo para {business_name}, quedo a su disposición. ¡Que tenga un gran día!"
        )

ESTETICAS_JUJUY = [
    {"business": "Nova Estetika Jujuy", "name": "Dra. Nova & Equipo", "phone": "5493884643989", "location": "San Salvador de Jujuy", "web": True},
    {"business": "Bellessima Estética & Spa", "name": "Equipo Bellessima", "phone": "5493885821369", "location": "San Salvador de Jujuy", "web": False},
    {"business": "MB Centro de Belleza", "name": "Equipo MB Belleza", "phone": "5493883387805", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Estética Integral Epiler", "name": "Equipo Epiler Jujuy", "phone": "5493885050548", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Gabriela Parola Estética", "name": "Gabriela Parola", "phone": "5493884170353", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Noris Uñas Esculpidas & Spa Urbano", "name": "Noris & Equipo", "phone": "5493885025108", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Estética Integral Corporal y Facial", "name": "Cosm. Mariela", "phone": "5493885726620", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Laskmi Spa Jujuy", "name": "Equipo Laskmi", "phone": "5493885710686", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Dra. Sofía Mendoza Medicina Estética", "name": "Dra. Sofía Mendoza", "phone": "5493885706841", "location": "San Salvador de Jujuy (Los Perales)", "web": False},
    {"business": "Centro de Estética & Cosmiatría Altea", "name": "Lic. Valentina Cruz", "phone": "5493884772294", "location": "San Salvador de Jujuy", "web": False},
    {"business": "SOLER Clínica Estética Jujuy", "name": "Dra. Soler & Equipo", "phone": "5493884620118", "location": "San Salvador de Jujuy (Av. Illia)", "web": False},
    {"business": "Estética Essence Jujuy", "name": "Equipo Essence", "phone": "5493885057727", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Dermolife Estética Facial y Corporal", "name": "Equipo Dermolife", "phone": "5493884377726", "location": "San Salvador de Jujuy (Belgrano)", "web": False},
    {"business": "Perfecta Depilación Definitiva", "name": "Equipo Perfecta", "phone": "5493885131236", "location": "San Salvador de Jujuy (Lavalle)", "web": False},
    {"business": "Belha Estética & Bienestar", "name": "Equipo Belha", "phone": "5493885008830", "location": "San Salvador de Jujuy", "web": False},
    {"business": "El Manantial del Silencio Spa", "name": "Equipo Spa Manantial", "phone": "5493884908080", "location": "Jujuy", "web": True},
    {"business": "Dra. Florencia Morales Estética", "name": "Dra. Florencia Morales", "phone": "5493885796255", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Centro Estético Jujuy Bienestar", "name": "Cosm. Romina", "phone": "5493884218094", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Studio Belleza & Cosmetología Jujuy", "name": "Equipo Studio Belleza", "phone": "5493884711400", "location": "San Salvador de Jujuy", "web": False},
    {"business": "Kirei Estética Avanzada Jujuy", "name": "Lic. Andrea Vargas", "phone": "5493883130530", "location": "San Salvador de Jujuy", "web": False}
]

ESTETICAS_SALTA = [
    {"business": "Estética CIAC Centro Médico", "name": "Equipo Estética CIAC", "phone": "5493874816548", "location": "Salta Capital", "web": True},
    {"business": "Medicina y Estética Salta", "name": "Dra. Carolina Ledesma & Dr. Eduardo Halusch", "phone": "5493874433459", "location": "Salta Capital", "web": True},
    {"business": "Gabinete de Estética Corporal", "name": "Karina Chiarini", "phone": "5493875239634", "location": "Salta Capital", "web": False},
    {"business": "Amber Spa Salta", "name": "Equipo Amber Spa", "phone": "5493874681921", "location": "Salta Capital", "web": False},
    {"business": "Velvet Beauty Bar Salta", "name": "Equipo Velvet Beauty", "phone": "5493875604123", "location": "Salta Capital", "web": False},
    {"business": "Alma Spa & Estética", "name": "Dra. Silvina Romero", "phone": "5493875883210", "location": "Salta Capital", "web": False},
    {"business": "Dermoestética Salta", "name": "Lic. Valeria Morales", "phone": "5493875129483", "location": "Salta Capital", "web": False},
    {"business": "Vitalis Centro Estético", "name": "Dra. Florencia Gómez", "phone": "5493875748921", "location": "Salta Capital", "web": False},
    {"business": "Estética Avanzada Salta", "name": "Cosm. Patricia Ibáñez", "phone": "5493875392014", "location": "Salta Capital", "web": False},
    {"business": "Harmonie Spa Urbano", "name": "Equipo Harmonie", "phone": "5493875410982", "location": "Salta Capital", "web": False},
    {"business": "Siluet Estética Integral", "name": "Cosm. Andrea Toledo", "phone": "5493875283910", "location": "Salta Capital", "web": False},
    {"business": "Bella Piel Cosmiatría", "name": "Lic. María Elena Ramos", "phone": "5493875691024", "location": "Salta Capital", "web": False},
    {"business": "Equilibrio Spa & Wellness", "name": "Equipo Equilibrio", "phone": "5493875324890", "location": "Salta Capital", "web": False},
    {"business": "Lumina Depilación Láser", "name": "Equipo Lumina", "phone": "5493875812903", "location": "Salta Capital", "web": False},
    {"business": "Estética Sublime Salta", "name": "Cosm. Romina Soria", "phone": "5493875473912", "location": "Salta Capital", "web": False},
    {"business": "Centro Dermatocosmiátrico Salta", "name": "Dra. Marcela Díaz", "phone": "5493875901248", "location": "Salta Capital", "web": False},
    {"business": "Pureza Spa & Relax", "name": "Equipo Pureza", "phone": "5493875184930", "location": "Salta Capital", "web": False},
    {"business": "Renacer Medicina Estética", "name": "Dr. Fernando Cabrera", "phone": "5493875630291", "location": "Salta Capital", "web": False},
    {"business": "Estética & Bronceado Salta", "name": "Equipo Bronceado & Spa", "phone": "5493875294018", "location": "Salta Capital", "web": False},
    {"business": "Aura Spa Salta", "name": "Cosm. Gisela Cruz", "phone": "5493875719382", "location": "Salta Capital", "web": False}
]

def main():
    prospects_file = 'E:/datos/proyectoIA/wally_bot/prospects.json'
    with open(prospects_file, 'r', encoding='utf-8') as f:
        existing = json.load(f)

    odontologia = [p for p in existing if p.get('niche') == 'Odontología']
    
    esteticas = []
    
    # 20 de Jujuy
    for i, item in enumerate(ESTETICAS_JUJUY):
        esteticas.append({
            "id": 2000 + i + 1,
            "business": item["business"],
            "name": item["name"],
            "niche": "Estética & Spa",
            "location": item["location"],
            "phone": item["phone"],
            "customMessage": generate_short_msg(item["name"], item["business"], item.get("web", False)),
            "status": "PENDING",
            "hasRealWeb": item.get("web", False),
            "group": "Estética & Spa"
        })
        
    # 20 de Salta
    for j, item in enumerate(ESTETICAS_SALTA):
        esteticas.append({
            "id": 2100 + j + 1,
            "business": item["business"],
            "name": item["name"],
            "niche": "Estética & Spa",
            "location": item["location"],
            "phone": item["phone"],
            "customMessage": generate_short_msg(item["name"], item["business"], item.get("web", False)),
            "status": "PENDING",
            "hasRealWeb": item.get("web", False),
            "group": "Estética & Spa"
        })

    all_prospects = odontologia + esteticas
    
    with open(prospects_file, 'w', encoding='utf-8') as f:
        json.dump(all_prospects, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Guardados en {prospects_file}: {len(all_prospects)} prospectos.")
    print(f"   - Odontología: {len(odontologia)}")
    print(f"   - Estética & Spa Jujuy: {len(ESTETICAS_JUJUY)}")
    print(f"   - Estética & Spa Salta: {len(ESTETICAS_SALTA)}")

    # 1. Guardar en PostgreSQL
    try:
        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5432,
            user='postgres',
            password='6Ic19aZIVRd8nSTyPtsRx7L1tbjzyp08jTNRQFM1fJ1o3lfFIngjrZemRfdPzSHX',
            dbname='wally_aura_web'
        )
        cur = conn.cursor()
        
        cur.execute("DELETE FROM prospects WHERE niche = 'Estética & Spa';")
        
        for p in esteticas:
            cur.execute("""
                INSERT INTO prospects (id, business, name, niche, location, phone, custom_message, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    business = EXCLUDED.business,
                    name = EXCLUDED.name,
                    niche = EXCLUDED.niche,
                    location = EXCLUDED.location,
                    phone = EXCLUDED.phone,
                    custom_message = EXCLUDED.custom_message,
                    status = EXCLUDED.status,
                    updated_at = NOW();
            """, (
                p['id'],
                p['business'],
                p['name'],
                p['niche'],
                p['location'],
                p['phone'],
                p['customMessage'],
                p['status']
            ))
            
        conn.commit()
        conn.close()
        print(f"🐘 ¡Sincronizados en PostgreSQL exitosamente los 40 prospectos de Estética & Spa (20 Jujuy + 20 Salta)!")
    except Exception as e:
        print(f"Error en Postgres: {e}")

    # 2. Sincronizar con API
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
            data=json.dumps({'prospects': all_prospects}).encode('utf-8'),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        save_res = urllib.request.urlopen(save_req, context=ctx)
        print(f"🌐 Sincronizado con API Wally Bot: {save_res.read().decode('utf-8')}")
    except Exception as api_err:
        print(f"Aviso API: {api_err}")

if __name__ == '__main__':
    main()
