"""
Actualiza los mensajes personalizados de todos los prospectos en prospects.json y PostgreSQL
con versiones ultracortas, directas y de alta conversión para WhatsApp.
- Odontología: https://auradev.online/demo/odontologia/
- Estética & Spa: https://auradev.online/demo/estetica/
"""

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

def generate_odonto_msg(name, business_name, has_real_web, website_url):
    is_doctor = 'Dr.' in name or 'Dra.' in name or 'Dr.' in business_name or 'Dra.' in business_name
    has_contact = name and name not in ['Profesional', 'Equipo', '']
    saludo = f'¡Hola {name}! ¿Cómo está? Le escribo de Aura Web.' if (is_doctor or has_contact) else '¡Hola! ¿Cómo están? Les escribo de Aura Web.'
    cierre = '¡Que tenga un gran día!' if (is_doctor or has_contact) else '¡Que tengan un gran día!'
    demo_url = 'https://auradev.online/demo/odontologia/'
    
    if has_real_web and website_url:
        return (
            f'{saludo} Vi su sitio web y nos especializamos en modernizarlo y optimizarlo 100% para celulares con turnero directo a WhatsApp.\n\n'
            f'Le comparto una demo en vivo: {demo_url} - Si le interesa evaluar una propuesta para {business_name}, con gusto se la armamos sin compromiso. {cierre}'
        )
    else:
        return (
            f'{saludo} Desarrollamos páginas web para odontología, 100% optimizadas para celulares y con turnero directo a WhatsApp.\n\n'
            f'Le comparto una demo en vivo: {demo_url} - Si le gustaría ver una maqueta sin costo para {business_name}, quedo a su disposición. {cierre}'
        )

def generate_estetica_msg(name, business_name, has_real_web, website_url):
    has_contact = name and name not in ['Profesional', 'Equipo', '']
    saludo = f'¡Hola {name}! ¿Cómo estás? Te escribo de Aura Web.' if has_contact else '¡Hola! ¿Cómo están? Les escribo de Aura Web.'
    cierre = '¡Que tengas un gran día!' if has_contact else '¡Que tengan un gran día!'
    demo_url = 'https://auradev.online/demo/estetica/'
    
    if has_real_web and website_url:
        return (
            f'{saludo} Vi su web de {business_name} y nos especializamos en modernizarla y optimizarla 100% para celulares con cotizador de packs y turnos por WhatsApp.\n\n'
            f'Te comparto una demo en vivo: {demo_url} - Si te interesa evaluar una propuesta para {business_name}, con gusto te la armamos sin compromiso. {cierre}'
        )
    else:
        return (
            f'{saludo} Creamos páginas web de lujo para estética y spas, 100% optimizadas para celulares y con reservas directas por WhatsApp.\n\n'
            f'Te comparto una demo en vivo: {demo_url} - Si te gustaría ver una propuesta sin costo para {business_name}, quedo a tu disposición. {cierre}'
        )

def main():
    with open('E:/datos/proyectoIA/wally_bot/prospects.json', 'r', encoding='utf-8') as f:
        prospects = json.load(f)

    odonto_count = 0
    estetica_count = 0
    with_web_count = 0

    for p in prospects:
        niche = (p.get('niche') or '').lower()
        bname = p.get('business', '')
        name = p.get('name', '')
        has_web = p.get('has_website', False)
        web_url = p.get('website', '')
        
        if has_web and web_url:
            with_web_count += 1
        
        if any(k in niche for k in ['est', 'spa', 'cosmet']):
            p['customMessage'] = generate_estetica_msg(name, bname, has_web, web_url)
            p['group'] = 'Estética & Spa'
            estetica_count += 1
        else:
            p['customMessage'] = generate_odonto_msg(name, bname, has_web, web_url)
            p['group'] = 'Odontología'
            odonto_count += 1

    with open('E:/datos/proyectoIA/wally_bot/prospects.json', 'w', encoding='utf-8') as f:
        json.dump(prospects, f, indent=2, ensure_ascii=False)

    print(f"[OK] Actualizados en prospects.json con versión CORTA:")
    print(f"  - Total: {len(prospects)} prospectos")
    print(f"  - Odontología: {odonto_count}")
    print(f"  - Estética & Spa: {estetica_count}")

    # Sincronizar con API y PostgreSQL
    try:
        ctx = ssl._create_unverified_context()
        headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
        login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
        req = urllib.request.Request(f'{BASE_URL}/api/auth/login', data=login_data, headers=headers)
        token = json.loads(urllib.request.urlopen(req, context=ctx).read().decode('utf-8'))['token']
        headers['Authorization'] = f'Bearer {token}'
        
        save_data = json.dumps({'prospects': prospects}).encode('utf-8')
        req2 = urllib.request.Request(f'{BASE_URL}/api/prospects', data=save_data, headers=headers)
        urllib.request.urlopen(req2, context=ctx)
        print("[OK] Sincronizado exitosamente con Wally Bot y PostgreSQL!")
    except Exception as e:
        print(f"[WARN] Error sincronizando con API: {e}")

if __name__ == '__main__':
    main()
