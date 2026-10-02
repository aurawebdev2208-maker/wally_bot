"""
Actualiza los mensajes personalizados de todos los prospectos en prospects.json y PostgreSQL
utilizando saludos atemporales (aptos para mañana, tarde o noche) y enlaces de auradev.online:
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
    saludo = f'¡Hola {name}! ¿Cómo está? Le escribo desde Aura Web.' if (is_doctor or has_contact) else '¡Hola! ¿Cómo están? Les escribo desde Aura Web.'
    cierre = '¡Que tenga un excelente día!' if (is_doctor or has_contact) else '¡Que tengan un excelente día!'
    demo_url = 'https://auradev.online/demo/odontologia/'
    
    if has_real_web and website_url:
        return (
            f'{saludo} '
            f'Estuve viendo la presencia web de {business_name} y noté que se beneficiaría mucho de una actualización mobile-first '
            f'y un turnero interactivo directo a WhatsApp para que los pacientes agenden al instante. '
            f'Le comparto una demo en vivo de cómo modernizamos sitios para odontología: {demo_url} - '
            f'Si le parece interesante evaluar un rediseño sin compromiso, con gusto le armamos una propuesta preliminar. ¡Saludos cordiales!'
        )
    else:
        return (
            f'{saludo} '
            f'Nos especializamos en el desarrollo de páginas web modernas para profesionales y clínicas odontológicas. '
            f'Diseñamos plataformas ágiles para celulares con selector de tratamientos, cotizador de cuotas y botón directo para solicitar turnos por WhatsApp. '
            f'Le comparto una demo en vivo de muestra: {demo_url} - '
            f'Si le gustaría ver una maqueta pensada para {business_name} sin costo ni compromiso, quedo a su disposición. {cierre}'
        )

def generate_estetica_msg(name, business_name, has_real_web, website_url):
    has_contact = name and name not in ['Profesional', 'Equipo', '']
    saludo = f'¡Hola {name}! ¿Cómo estás? Te escribo desde Aura Web.' if has_contact else '¡Hola! ¿Cómo están? Les escribo desde Aura Web.'
    cierre = '¡Que tengas un excelente día!' if has_contact else '¡Que tengan un excelente día!'
    demo_url = 'https://auradev.online/demo/estetica/'
    
    if has_real_web and website_url:
        return (
            f'{saludo} '
            f'Estuvimos viendo el perfil de {business_name} y notamos que se beneficiaría mucho de una web mobile-first de alto impacto, '
            f'con cotizador interactivo de depilación láser en 3 pasos, catálogo de tratamientos y turnero directo a WhatsApp para que tus clientas reserven al instante. '
            f'Te comparto una demo en vivo de cómo diseñamos para estética: {demo_url} - '
            f'Si te parece interesante evaluar una propuesta o rediseño sin compromiso para {business_name}, con gusto te armamos una maqueta. ¡Saludos cordiales!'
        )
    else:
        return (
            f'{saludo} '
            f'Nos especializamos en el desarrollo de páginas web modernas para centros de estética, medicina estética y spas. '
            f'Diseñamos sitios ágiles para celulares con cotizador interactivo de depilación láser, catálogo de tratamientos y botón directo para solicitar turnos por WhatsApp. '
            f'Te comparto una demo en vivo de muestra: {demo_url} - '
            f'Si te gustaría ver una propuesta pensada para {business_name} sin costo ni compromiso, quedo a tu disposición. {cierre}'
        )

def main():
    with open('E:/datos/proyectoIA/wally_bot/prospects.json', 'r', encoding='utf-8') as f:
        prospects = json.load(f)

    odonto_count = 0
    estetica_count = 0

    for p in prospects:
        niche = (p.get('niche') or '').lower()
        bname = p.get('business', '')
        name = p.get('name', '')
        has_web = p.get('has_website', False)
        web_url = p.get('website', '')
        
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

    print(f"[OK] Actualizados en prospects.json:")
    print(f"  - Odontología: {odonto_count} prospectos con saludo general atemporal")
    print(f"  - Estética & Spa: {estetica_count} prospectos con saludo general atemporal")

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
