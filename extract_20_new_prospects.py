"""
Extracción de 20 nuevos prospectos odontológicos en Salta vía Google Maps
Evita duplicados con los 20 existentes, genera mensajes y sincroniza con Wally Bot.
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
    if clean.startswith('38715'):
        clean = '387' + clean[5:]
    elif clean.startswith('38815'):
        clean = '388' + clean[5:]
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

def generate_custom_message(name, business_name, has_real_web, website_url, demo_url="https://demo-odontologia-seven.vercel.app/"):
    is_doctor = "Dr." in name or "Dra." in name or "Dr." in business_name or "Dra." in business_name
    saludo = f"Hola {name}, ¿cómo está? Buenas tardes." if is_doctor else "Hola, ¿cómo están? Buenas tardes."
    
    if has_real_web and website_url:
        msg = (
            f"{saludo} Le escribo desde Aura Web. "
            f"Estuve viendo la presencia web de {business_name} y noté que se beneficiaría mucho de una actualización mobile-first "
            f"y un turnero interactivo directo a WhatsApp para que los pacientes agenden al instante. "
            f"Le comparto una demo en vivo de cómo modernizamos sitios para odontología: {demo_url} - "
            f"Si le parece interesante evaluar un rediseño sin compromiso, con gusto le armamos una propuesta preliminar. ¡Saludos cordiales!"
        )
    else:
        msg = (
            f"{saludo} Le escribo desde Aura Web. "
            f"Nos especializamos en el desarrollo de páginas web modernas para profesionales y clínicas odontológicas. "
            f"Diseñamos plataformas ágiles para celulares con catálogo de especialidades y botón directo para solicitar turnos por WhatsApp. "
            f"Le comparto una demo en vivo de muestra: {demo_url} - "
            f"Si le gustaría ver una maqueta pensada para {business_name} sin costo ni compromiso, quedo a su disposición. ¡Que tenga una excelente jornada!"
        )
    return msg

def extract_new_prospects(existing_file, target_new_count=20):
    # 1. Cargar existentes
    with open(existing_file, 'r', encoding='utf-8') as f:
        existing_prospects = json.load(f)
        
    existing_phones = {p.get('phone', '') for p in existing_prospects if p.get('phone')}
    existing_names = {p.get('business', '').lower().strip() for p in existing_prospects}
    
    print(f"Cargados {len(existing_prospects)} prospectos existentes.")
    print(f"Teléfonos existentes: {len(existing_phones)}")
    
    queries = [
        "odontologos en Salta Capital",
        "clinica dental Salta Capital",
        "consultorio odontologico Salta",
        "ortodoncia Salta Capital",
        "implantes dentales Salta",
        "odontologia general Salta"
    ]
    
    new_prospects = []
    collected_phones = set(existing_phones)
    collected_names = set(existing_names)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(
            locale='es-419',
            viewport={'width': 1280, 'height': 850},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        search_page = context.new_page()
        detail_page = context.new_page()
        
        for q in queries:
            if len(new_prospects) >= target_new_count:
                break
                
            print(f"\n========================================================")
            print(f"Buscando en Google Maps: '{q}'")
            print(f"Progreso nuevos: {len(new_prospects)}/{target_new_count}")
            print(f"========================================================")
            
            encoded_query = urllib.parse.quote_plus(q)
            search_url = f"https://www.google.com/maps/search/{encoded_query}/"
            
            try:
                search_page.goto(search_url, timeout=35000)
                search_page.wait_for_timeout(3000)
            except Exception as e:
                print(f"Error cargando búsqueda: {e}")
                continue
                
            # Scroll feed
            feed = search_page.locator('div[role="feed"]').first
            for _ in range(6):
                try:
                    if feed.is_visible():
                        feed.evaluate("el => el.scrollBy(0, 1000)")
                    else:
                        search_page.mouse.wheel(0, 1000)
                except Exception:
                    pass
                search_page.wait_for_timeout(1200)
                
            place_links = search_page.locator('a[href*="/maps/place/"]').all()
            print(f"Lugares encontrados en query: {len(place_links)}")
            
            place_urls = []
            for pl in place_links:
                href = pl.get_attribute('href')
                aria = pl.get_attribute('aria-label')
                if href and href not in [u[1] for u in place_urls]:
                    place_urls.append((aria or "", href))
                    
            for raw_name, url in place_urls:
                if len(new_prospects) >= target_new_count:
                    break
                    
                name_clean = raw_name.lower().strip()
                if name_clean in collected_names:
                    continue
                    
                try:
                    detail_page.goto(url, timeout=20000)
                    detail_page.wait_for_timeout(1500)
                    
                    # Título
                    name = raw_name
                    try:
                        title_el = detail_page.locator('h1.DUwDvf, div.m6QErb h1').first
                        if title_el.is_visible(timeout=1000):
                            name = title_el.inner_text().strip()
                    except Exception:
                        pass
                    
                    if not name or name.lower().strip() in collected_names:
                        continue
                        
                    # Teléfono
                    raw_phone = ""
                    try:
                        phone_btn = detail_page.locator('button[data-item-id*="phone:"], button[aria-label*="Teléfono:"]').first
                        if phone_btn.is_visible(timeout=1000):
                            raw_p = phone_btn.get_attribute('aria-label') or phone_btn.inner_text()
                            raw_phone = raw_p.replace("Teléfono: ", "").replace("Teléfono:", "").strip()
                    except Exception:
                        pass
                        
                    if not raw_phone:
                        try:
                            body_text = detail_page.locator('body').inner_text()
                            phone_match = re.search(r'(\+?54\s*9?\s*387[\s\d-]{6,12}|0?387[\s\d-]{6,10})', body_text)
                            if phone_match:
                                raw_phone = phone_match.group(1).strip()
                        except Exception:
                            pass
                            
                    formatted_phone = format_phone_for_whatsapp(raw_phone)
                    
                    # Requerimos que tenga teléfono válido y que no esté duplicado
                    if not formatted_phone or len(formatted_phone) < 10 or formatted_phone in collected_phones:
                        continue
                        
                    # Dirección
                    address = ""
                    try:
                        addr_btn = detail_page.locator('button[data-item-id*="address"], button[aria-label*="Dirección:"]').first
                        if addr_btn.is_visible(timeout=1000):
                            raw_addr = addr_btn.get_attribute('aria-label') or addr_btn.inner_text()
                            address = raw_addr.replace("Dirección: ", "").replace("Dirección:", "").strip()
                    except Exception:
                        pass
                        
                    # Nicho
                    category = "Odontología"
                    try:
                        c_el = detail_page.locator('button[jsaction*="category"], div.fontBodyMedium button.DkEaL').first
                        if c_el.is_visible(timeout=1000):
                            category = c_el.inner_text().strip()
                    except Exception:
                        pass
                        
                    # Sitio web
                    website_url = ""
                    try:
                        web_btn = detail_page.locator('a[data-item-id="authority"], a[aria-label*="Sitio web:"]').first
                        if web_btn.is_visible(timeout=1000):
                            website_url = web_btn.get_attribute('href') or ""
                    except Exception:
                        pass
                        
                    has_real_web = is_real_website(website_url)
                    
                    # Nombre contacto
                    contact_name = name
                    if "Dr." not in name and "Dra." not in name:
                        if any(w in name.lower() for w in ["clínica", "clinica", "centro", "consultorio", "odontolog", "instituto", "grupo", "dental"]):
                            contact_name = f"Equipo {name}"
                        else:
                            contact_name = name
                            
                    msg = generate_custom_message(contact_name, name, has_real_web, website_url)
                    
                    idx_num = len(existing_prospects) + len(new_prospects) + 1
                    item_data = {
                        "id": f"salta_dent_{idx_num:02d}",
                        "business": name,
                        "name": contact_name,
                        "niche": category,
                        "location": address or "Salta Capital",
                        "phone": formatted_phone,
                        "customMessage": msg,
                        "status": "PENDING"
                    }
                    
                    new_prospects.append(item_data)
                    collected_phones.add(formatted_phone)
                    collected_names.add(name.lower().strip())
                    
                    print(f"\n[+ Nuevo {len(new_prospects)}/20] {name}")
                    print(f"  Teléfono : {formatted_phone} (Orig: {raw_phone})")
                    print(f"  Dirección: {address or 'Salta Capital'}")
                    print(f"  Web Real : {'SÍ (' + website_url + ')' if has_real_web else 'NO'}")
                    
                except Exception as e:
                    print(f"Error procesando lugar: {e}")
                    continue
                    
        browser.close()
        
    print(f"\n========================================================")
    print(f"Extracción completada. Total de nuevos prospectos: {len(new_prospects)}")
    print(f"========================================================")
    
    # 2. Combinar 20 anteriores + 20 nuevos
    all_prospects = existing_prospects + new_prospects
    
    # Guardar en prospects.json
    with open(existing_file, 'w', encoding='utf-8') as f:
        json.dump(all_prospects, f, ensure_ascii=False, indent=2)
    print(f"Archivo {existing_file} actualizado con {len(all_prospects)} prospectos totales.")
    
    # 3. Sincronizar con Wally Bot API
    print("Sincronizando con Wally Bot en la nube...")
    ctx = ssl._create_unverified_context()
    base_url = "https://wally_bot.dario10.pw"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/json'
    }
    
    # Login
    login_data = json.dumps({'username': 'antig', 'password': 'antig6393'}).encode('utf-8')
    req1 = urllib.request.Request(f'{base_url}/api/auth/login', data=login_data, headers=headers)
    res1 = urllib.request.urlopen(req1, context=ctx)
    token = json.loads(res1.read().decode('utf-8'))['token']
    headers['Authorization'] = f'Bearer {token}'
    
    # Guardar todos los 40 prospectos
    save_data = json.dumps({'prospects': all_prospects}).encode('utf-8')
    req2 = urllib.request.Request(f'{base_url}/api/prospects', data=save_data, headers=headers)
    res2 = urllib.request.urlopen(req2, context=ctx)
    print("Respuesta de sincronización:", res2.read().decode('utf-8'))
    
    # 4. Enviar notificación por WhatsApp a Dario
    print("Enviando notificación por WhatsApp a Darío (5493885104530)...")
    notif_msg = (
        f"¡Hola Darío! 👋 Ya finalicé la búsqueda con el scraper de Google Maps y extraje 20 nuevos odontólogos y clínicas de Salta "
        f"(100% diferentes a los anteriores, sin duplicados). Ahora tenés un total de {len(all_prospects)} prospectos cargados con sus teléfonos, "
        f"direcciones y mensajes personalizados según tengan o no sitio web. Ya podés verlos y gestionarlos en https://wally_bot.dario10.pw/"
    )
    send_data = json.dumps({'phone': '5493885104530', 'message': notif_msg}).encode('utf-8')
    req3 = urllib.request.Request(f'{base_url}/api/send', data=send_data, headers=headers)
    try:
        res3 = urllib.request.urlopen(req3, context=ctx)
        print("Notificación WhatsApp enviada:", res3.read().decode('utf-8'))
    except Exception as e:
        print("Error enviando WhatsApp:", e)

if __name__ == "__main__":
    extract_new_prospects(r"E:\datos\proyectoIA\wally_bot\prospects.json", target_new_count=20)
