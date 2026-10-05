"""
Scraper & Prospector de Centros de Estética y Esteticistas en Jujuy (10) y Salta (20)
- Extrae números de celular verificados (excluye teléfonos fijos).
- Genera mensajes cortos, time-agnostic y personalizados con link a https://auradev.online/demo/estetica/
- Asigna al grupo 'Estética & Spa' y sincroniza con PostgreSQL / Wally Bot.
"""

import sys
import time
import json
import re
import urllib.parse
import urllib.request
import ssl
import psycopg2
from psycopg2.extras import RealDictCursor
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def is_landline(clean_phone):
    """
    Detecta si un número argentino es teléfono fijo (no tiene WhatsApp).
    En Salta (387) y Jujuy (388), los fijos tienen 6 dígitos tras la característica y empiezan con 4 o 3.
    Ej: 5493874319238 (387 + 4319238 -> 6 dígitos 431xxx) = Fijo
    Ej: 5493875355363 (387 + 5355363 -> 7 dígitos 535xxxx) = Celular
    """
    if not clean_phone:
        return True
    
    num = re.sub(r'[^\d]', '', clean_phone)
    if num.startswith('549'):
        num = num[3:]
    elif num.startswith('54'):
        num = num[2:]
    elif num.startswith('0'):
        num = num[1:]

    # Salta (387)
    if num.startswith('387'):
        local = num[3:]
        # Si tiene 6 dígitos y empieza con 4, 3, 22, 21 es fijo
        if len(local) == 6 and (local.startswith('4') or local.startswith('3')):
            return True
        if len(local) < 7:
            return True

    # Jujuy (388)
    if num.startswith('388'):
        local = num[3:]
        if len(local) == 6 and (local.startswith('4') or local.startswith('3')):
            return True
        if len(local) < 7:
            return True

    return False

def format_phone_for_whatsapp(raw_phone):
    if not raw_phone:
        return ""
    clean = re.sub(r'[^\d+]', '', raw_phone)
    if clean.startswith('+'):
        clean = clean[1:]
    if clean.startswith('549'):
        return clean
    if clean.startswith('54'):
        return '549' + clean[2:]
    if clean.startswith('0'):
        clean = clean[1:]
    if clean.startswith('38815'):
        clean = '388' + clean[5:]
    elif clean.startswith('38715'):
        clean = '387' + clean[5:]
    elif clean.startswith('1115'):
        clean = '11' + clean[4:]
    if len(clean) >= 9:
        return f"549{clean}"
    return clean

def is_real_website(url):
    if not url:
        return False
    url_lower = url.lower()
    social_and_chat = [
        'instagram.com', 'facebook.com', 'fb.com', 'wa.me', 'whatsapp.com',
        'linktr.ee', 'bit.ly', 'cutt.ly', 'google.com', 'tiktok.com', 'maps.google.com'
    ]
    if any(domain in url_lower for domain in social_and_chat):
        return False
    return True

def generate_short_pitch_message(name, business_name, has_real_web, demo_url="https://auradev.online/demo/estetica/"):
    has_contact = name and name not in ['Profesional', 'Equipo', '']
    saludo_name = f" {name}" if has_contact else f" {business_name}"
    
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

def scrape_region(page, queries, target_count, location_label, existing_phones, existing_names):
    print(f"\n==========================================")
    print(f"🔍 Buscando {target_count} estéticas en {location_label}...")
    print(f"==========================================")
    
    results = []
    
    for query in queries:
        if len(results) >= target_count:
            break
            
        search_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(query)}"
        print(f"\n[Scraper] 🌐 Ejecutando query: '{query}'")
        
        try:
            page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
            time.sleep(3.5)
            
            feed_selector = 'div[role="feed"]'
            page.wait_for_selector(feed_selector, timeout=10000)
            
            for _ in range(7):
                page.evaluate(f'''
                    const feed = document.querySelector('{feed_selector}');
                    if (feed) feed.scrollTop += 1200;
                ''')
                time.sleep(1.8)
                
            links = page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
            print(f"[Scraper] Encontrados {len(links)} lugares preliminares.")
            
            hrefs = []
            for l in links:
                h = l.get_attribute('href')
                if h and h not in hrefs:
                    hrefs.append(h)
                    
            for href in hrefs:
                if len(results) >= target_count:
                    break
                    
                try:
                    page.goto(href, timeout=30000, wait_until="domcontentloaded")
                    time.sleep(2.0)
                    
                    name_el = page.query_selector('h1')
                    business_name = name_el.inner_text().strip() if name_el else ""
                    
                    if not business_name or business_name.lower() in existing_names:
                        continue
                        
                    # Extraer teléfono
                    phone_btn = page.query_selector('button[data-tooltip*="teléfono" i], button[data-tooltip*="phone" i], button[aria-label*="Teléfono" i], button[aria-label*="Phone" i]')
                    raw_phone = ""
                    if phone_btn:
                        raw_phone = phone_btn.inner_text().strip()
                    else:
                        phone_el = page.query_selector('button[data-item-id*="phone:tel:"]')
                        if phone_el:
                            raw_phone = phone_el.inner_text().strip()
                            
                    clean_phone = format_phone_for_whatsapp(raw_phone)
                    
                    if not clean_phone or clean_phone in existing_phones:
                        continue
                        
                    # VERIFICACIÓN CELULAR (Descartar fijos)
                    if is_landline(clean_phone):
                        print(f"   ⏩ Descartado fijo: {business_name} ({clean_phone})")
                        continue
                        
                    # Extraer web
                    web_btn = page.query_selector('a[data-tooltip*="sitio web" i], a[data-tooltip*="website" i], a[aria-label*="Sitio web" i], a[aria-label*="Website" i]')
                    raw_web = web_btn.get_attribute('href') if web_btn else ""
                    has_real_web = is_real_website(raw_web)
                    
                    custom_msg = generate_short_pitch_message(
                        name=business_name,
                        business_name=business_name,
                        has_real_web=has_real_web
                    )
                    
                    prospect = {
                        "id": int(time.time() * 1000) + len(results) + len(existing_phones),
                        "business": business_name,
                        "name": business_name,
                        "niche": "Estética & Spa",
                        "location": location_label,
                        "phone": clean_phone,
                        "customMessage": custom_msg,
                        "status": "PENDING",
                        "hasRealWeb": has_real_web,
                        "website": raw_web if has_real_web else None,
                        "group": "Estética & Spa"
                    }
                    
                    results.append(prospect)
                    existing_phones.add(clean_phone)
                    existing_names.add(business_name.lower())
                    print(f"   ✅ [{len(results)}/{target_count}] {business_name} -> 📱 Cel: {clean_phone} (Web: {has_real_web})")
                    
                except Exception as place_err:
                    continue
                    
        except Exception as query_err:
            print(f"[Scraper] Error en query '{query}': {query_err}")
            continue
            
    return results

def main():
    prospects_file = 'E:/datos/proyectoIA/wally_bot/prospects.json'
    with open(prospects_file, 'r', encoding='utf-8') as f:
        all_prospects = json.load(f)
        
    existing_phones = {p.get('phone', '') for p in all_prospects if p.get('phone')}
    existing_names = {p.get('business', '').lower().strip() for p in all_prospects}
    
    print(f"📊 Prospectos actuales en prospects.json: {len(all_prospects)}")
    
    jujuy_queries = [
        "centro de estetica San Salvador de Jujuy",
        "esteticista San Salvador de Jujuy",
        "estetica corporal facial San Salvador de Jujuy",
        "spa San Salvador de Jujuy",
        "cosmetologia dermatocosmiatria San Salvador de Jujuy",
        "depilacion laser San Salvador de Jujuy",
        "medicina estetica San Salvador de Jujuy"
    ]
    
    salta_queries = [
        "centro de estetica Salta",
        "esteticista Salta capital",
        "estetica corporal facial Salta",
        "spa urbano Salta",
        "cosmiatria cosmetologia Salta",
        "depilacion definitiva laser Salta",
        "medicina estetica Salta capital",
        "estetica integral Salta"
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="es-419"
        )
        page = context.new_page()
        
        # 1. Extraer 10 de Jujuy
        jujuy_leads = scrape_region(page, jujuy_queries, target_count=10, location_label="Jujuy", existing_phones=existing_phones, existing_names=existing_names)
        
        # 2. Extraer 20 de Salta
        salta_leads = scrape_region(page, salta_queries, target_count=20, location_label="Salta", existing_phones=existing_phones, existing_names=existing_names)
        
        browser.close()
        
    new_leads = jujuy_leads + salta_leads
    print(f"\n==========================================")
    print(f"✨ Total nuevos prospectos móviles extraídos: {len(new_leads)} ({len(jujuy_leads)} Jujuy, {len(salta_leads)} Salta)")
    print(f"==========================================")
    
    # Agregar a prospects.json
    all_prospects.extend(new_leads)
    with open(prospects_file, 'w', encoding='utf-8') as f:
        json.dump(all_prospects, f, indent=2, ensure_ascii=False)
    print(f"💾 Guardados en {prospects_file} (Total: {len(all_prospects)})")
    
    # Sincronizar en PostgreSQL
    try:
        conn = psycopg2.connect(
            host='192.168.1.25',
            port=5432,
            user='postgres',
            password='6Ic19aZIVRd8nSTyPtsRx7L1tbjzyp08jTNRQFM1fJ1o3lfFIngjrZemRfdPzSHX',
            dbname='wally_aura_web'
        )
        cur = conn.cursor()
        
        # Sincronizar campo group en PostgreSQL si no existe
        cur.execute("ALTER TABLE prospects ADD COLUMN IF NOT EXISTS target_group VARCHAR(100) DEFAULT 'General';")
        conn.commit()
        
        inserted = 0
        for p in new_leads:
            cur.execute("""
                INSERT INTO prospects (id, business, name, niche, location, phone, custom_message, status, target_group, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (id) DO UPDATE SET
                    business = EXCLUDED.business,
                    name = EXCLUDED.name,
                    niche = EXCLUDED.niche,
                    location = EXCLUDED.location,
                    phone = EXCLUDED.phone,
                    custom_message = EXCLUDED.custom_message,
                    status = EXCLUDED.status,
                    target_group = EXCLUDED.target_group,
                    updated_at = NOW();
            """, (
                p['id'],
                p['business'],
                p['name'],
                p['niche'],
                p['location'],
                p['phone'],
                p['customMessage'],
                p['status'],
                p['group']
            ))
            inserted += 1
            
        conn.commit()
        conn.close()
        print(f"🐘 ¡Sincronizados exitosamente {inserted} prospectos en PostgreSQL Coolify!")
    except Exception as db_err:
        print(f"⚠️ Error sincronizando con PostgreSQL: {db_err}")

if __name__ == '__main__':
    main()
