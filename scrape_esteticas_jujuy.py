"""
Scraper de Centros de Estética y Esteticistas en San Salvador de Jujuy vía Google Maps
Extrae 10 prospectos únicos con teléfono verificado, genera mensaje personalizado
y los asigna al grupo 'Estética & Spa' sincronizándolos con Wally Bot y PostgreSQL.
"""

import sys
import time
import json
import re
import urllib.parse
import urllib.request
import ssl
from playwright.sync_api import sync_playwright

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE_URL = "https://wally_bot.dario10.pw"

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

def generate_custom_message(name, business_name, has_real_web, website_url, demo_url="https://auradev.online/demo/estetica/"):
    has_contact = name and name not in ['Profesional', 'Equipo', '']
    saludo = f"¡Hola {name}! ¿Cómo estás? Te escribo desde Aura Web." if has_contact else "¡Hola! ¿Cómo están? Les escribo desde Aura Web."
    cierre = "¡Que tengas un excelente día!" if has_contact else "¡Que tengan un excelente día!"
    
    if has_real_web and website_url:
        msg = (
            f"{saludo} "
            f"Estuvimos viendo el sitio web de {business_name} y te escribo porque nos especializamos en actualizar, rediseñar y modernizar páginas web existentes, "
            f"optimizándolas al 100% para teléfonos móviles (diseño visual de alta gama y carga ultra rápida) e integrando cotizadores de packs y turneros directos a WhatsApp para que tus clientas reserven al instante desde el celular. "
            f"Te comparto una demo en vivo de cómo rediseñamos sitios para estética: {demo_url} - "
            f"Si te parece interesante evaluar una actualización o rediseño sin compromiso para {business_name}, con gusto te armamos una propuesta preliminar. {cierre}"
        )
    else:
        msg = (
            f"{saludo} "
            f"Nos especializamos en el desarrollo de páginas web modernas para centros de estética, cosmetología y spas, "
            f"optimizadas al 100% para teléfonos móviles con cotizador interactivo de depilación láser en 3 pasos, catálogo de tratamientos y botón directo para solicitar turnos por WhatsApp. "
            f"Te comparto una demo en vivo de muestra: {demo_url} - "
            f"Si te gustaría ver una propuesta pensada para {business_name} sin costo ni compromiso, quedo a tu disposición. {cierre}"
        )
    return msg

def extract_esteticas_jujuy(target_count=10):
    prospects_file = 'E:/datos/proyectoIA/wally_bot/prospects.json'
    
    with open(prospects_file, 'r', encoding='utf-8') as f:
        existing_prospects = json.load(f)
        
    existing_phones = {p.get('phone', '') for p in existing_prospects if p.get('phone')}
    existing_names = {p.get('business', '').lower().strip() for p in existing_prospects}
    
    print(f"[Scraper] Prospectos existentes en base: {len(existing_prospects)}")
    
    queries = [
        "centro de estetica San Salvador de Jujuy",
        "esteticista San Salvador de Jujuy",
        "estetica facial San Salvador de Jujuy",
        "spa San Salvador de Jujuy",
        "medicina estetica San Salvador de Jujuy",
        "cosmetologia San Salvador de Jujuy"
    ]
    
    new_prospects = []
    collected_phones = set(existing_phones)
    collected_names = set(existing_names)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(
            locale="es-419",
            viewport={'width': 1280, 'height': 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        for q in queries:
            if len(new_prospects) >= target_count:
                break
                
            search_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(q)}/"
            print(f"\n[Scraper] Buscando: '{q}'...", flush=True)
            
            try:
                page.goto(search_url, timeout=45000)
                page.wait_for_timeout(3500)
                
                # Aceptar cookies si aparecen
                try:
                    accept_btn = page.locator('button[aria-label*="Aceptar"], button[aria-label*="Agree"], form[action*="consent"] button').first
                    if accept_btn.is_visible(timeout=2000):
                        accept_btn.click()
                        page.wait_for_timeout(1000)
                except Exception:
                    pass
                
                # Scroll panel de resultados
                print("  > Cargando lista de lugares...", flush=True)
                feed = page.locator('div[role="feed"]').first
                for _ in range(8):
                    try:
                        if feed.is_visible():
                            feed.evaluate("el => el.scrollBy(0, 1000)")
                        else:
                            page.mouse.wheel(0, 1000)
                    except Exception:
                        page.mouse.wheel(0, 1000)
                    page.wait_for_timeout(1200)
                
                cards = page.locator('a[href*="/maps/place/"]').all()
                if not cards:
                    cards = page.locator('div[role="article"]').all()
                    
                print(f"  > Tarjetas encontradas en pantalla: {len(cards)}", flush=True)
                
                for card in cards:
                    if len(new_prospects) >= target_count:
                        break
                        
                    try:
                        # Extraer link o clickear
                        card_text = card.inner_text()
                        lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                        if not lines:
                            continue
                            
                        business_name = lines[0]
                        clean_bname = business_name.lower().strip()
                        
                        if clean_bname in collected_names:
                            continue
                            
                        # Clickear para abrir detalles
                        card.click()
                        time.sleep(2.5)
                        
                        # Extraer datos del panel lateral
                        phone_elem = page.locator('button[data-tooltip*="teléfono"], button[data-tooltip*="phone"], button[aria-label*="Teléfono:"]').first
                        raw_phone = ""
                        if phone_elem.count() > 0:
                            raw_phone = phone_elem.inner_text() or phone_elem.get_attribute('aria-label') or ""
                            raw_phone = raw_phone.replace("Teléfono:", "").strip()
                        else:
                            # Buscar patrón de teléfono en el texto
                            body_text = page.locator('div[role="main"]').inner_text()
                            phone_match = re.search(r'(\+?54\s?9?\s?388\s?\d{3}[\s-]?\d{4}|\b0?388[\s-]?\d{3}[\s-]?\d{4}|\b388\d{7}\b)', body_text)
                            if phone_match:
                                raw_phone = phone_match.group(1)
                                
                        formatted_phone = format_phone_for_whatsapp(raw_phone)
                        if not formatted_phone or len(formatted_phone) < 10 or formatted_phone in collected_phones:
                            continue
                            
                        # Web
                        web_elem = page.locator('a[data-tooltip*="sitio web"], a[data-tooltip*="website"], a[aria-label*="Sitio web:"]').first
                        website_url = ""
                        if web_elem.count() > 0:
                            website_url = web_elem.get_attribute('href') or ""
                        has_real_web = is_real_website(website_url)
                        
                        # Dirección
                        addr_elem = page.locator('button[data-tooltip*="dirección"], button[aria-label*="Dirección:"]').first
                        address = "San Salvador de Jujuy, Jujuy"
                        if addr_elem.count() > 0:
                            address = addr_elem.inner_text().replace("Dirección:", "").strip() or address
                            
                        # Rating
                        rating = 4.8
                        try:
                            rate_elem = page.locator('span[aria-label*="estrellas"]').first
                            if rate_elem.count() > 0:
                                rate_text = rate_elem.get_attribute('aria-label') or ""
                                match_rate = re.search(r'(\d+[\.,]\d+)', rate_text)
                                if match_rate:
                                    rating = float(match_rate.group(1).replace(',', '.'))
                        except Exception:
                            pass
                            
                        # Nombre de contacto
                        contact_name = ""
                        match_contact = re.search(r'(Lic\.|Dra\.|Dra|Lic)\s+([A-Za-zÁÉÍÓÚáéíóúñ]+)', business_name)
                        if match_contact:
                            contact_name = match_contact.group(0)
                            
                        custom_msg = generate_custom_message(contact_name, business_name, has_real_web, website_url)
                        
                        prospect_obj = {
                            "id": f"est_jujuy_{int(time.time())}_{len(new_prospects)+1}",
                            "business": business_name,
                            "name": contact_name or "Profesional",
                            "niche": "Estética & Spa",
                            "specialty": "Estética & Cosmetología",
                            "location": "San Salvador de Jujuy, Jujuy",
                            "address": address,
                            "phone": formatted_phone,
                            "raw_phone": raw_phone,
                            "website": website_url if has_real_web else None,
                            "has_website": has_real_web,
                            "rating": rating,
                            "customMessage": custom_msg,
                            "status": "PENDING"
                        }
                        
                        new_prospects.append(prospect_obj)
                        collected_phones.add(formatted_phone)
                        collected_names.add(clean_bname)
                        
                        print(f"  [+] ({len(new_prospects)}/{target_count}) {business_name} -> {formatted_phone} (Web: {'Sí' if has_real_web else 'No'})")
                        
                    except Exception as err:
                        # print(f"  [!] Error procesando tarjeta: {err}")
                        continue
                        
            except Exception as e:
                print(f"[Scraper] Error buscando '{q}': {e}")
                
        browser.close()
        
    print(f"\n[Scraper] ✅ Total nuevos prospectos de estética extraídos: {len(new_prospects)}")
    
    if new_prospects:
        all_prospects = existing_prospects + new_prospects
        with open(prospects_file, 'w', encoding='utf-8') as f:
            json.dump(all_prospects, f, indent=2, ensure_ascii=False)
        print(f"[Scraper] Guardados {len(all_prospects)} prospectos totales en prospects.json.")
        
        # Sincronizar con API y PostgreSQL
        try:
            ctx = ssl._create_unverified_context()
            login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
            headers = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
            req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers=headers)
            token = json.loads(urllib.request.urlopen(req, context=ctx).read().decode('utf-8'))['token']
            headers['Authorization'] = f"Bearer {token}"
            
            save_data = json.dumps({'prospects': all_prospects}).encode('utf-8')
            req2 = urllib.request.Request(f"{BASE_URL}/api/prospects", data=save_data, headers=headers)
            urllib.request.urlopen(req2, context=ctx)
            print("[Scraper] 🐘 ¡Sincronizados exitosamente con PostgreSQL en Wally Bot!")
        except Exception as e:
            print(f"[Scraper] Error sincronizando con servidor: {e}")
            
    return new_prospects

if __name__ == "__main__":
    extract_esteticas_jujuy(10)
