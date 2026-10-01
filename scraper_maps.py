"""
Google Maps Scraper para Wally Bot / Aura Web
Extrae odontólogos, clínicas y profesionales de Google Maps con datos de contacto,
detección de sitio web real (o ausencia del mismo) y generación automática de mensajes.
"""

import sys
import time
import json
import re
import urllib.parse
import urllib.request
import ssl
from playwright.sync_api import sync_playwright

# Configurar encoding seguro para Windows
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def format_phone_for_whatsapp(raw_phone):
    """
    Normaliza teléfonos argentinos a formato WhatsApp internacional (549...).
    """
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
    """
    Determina si la URL es una página web propia o solo una red social / link de WhatsApp.
    """
    if not url:
        return False
    url_lower = url.lower()
    social_and_chat = [
        'instagram.com', 'facebook.com', 'fb.com', 'wa.me', 'whatsapp.com',
        'linktr.ee', 'bit.ly', 'cutt.ly', 'google.com', 'tiktok.com'
    ]
    if any(domain in url_lower for domain in social_and_chat):
        return False
    return True

def generate_custom_message(name, business_name, has_real_web, website_url, demo_url="https://demo-odontologia-seven.vercel.app/"):
    """
    Genera el mensaje personalizado cordial, ameno y directo según si tiene web propia o no.
    """
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

def scrape_google_maps(query="odontologos en Salta Capital", max_results=20, headless=True):
    print(f"\n========================================================")
    print(f"Iniciando Scraper de Google Maps para: '{query}'")
    print(f"Objetivo: Extraer hasta {max_results} resultados...")
    print(f"========================================================\n")
    
    results = []
    seen_names = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=headless)
        context = browser.new_context(
            locale='es-419',
            viewport={'width': 1280, 'height': 850},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://www.google.com/maps/search/{encoded_query}/"
        print(f"Navegando a: {search_url}")
        
        page.goto(search_url, timeout=45000)
        page.wait_for_timeout(3500)
        
        # Rechazar cookies si aparece el popup
        try:
            reject_button = page.locator('button[aria-label*="Rechazar"], button[aria-label*="Reject"], form[action*="consent"] button').first
            if reject_button.is_visible(timeout=2000):
                reject_button.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # Scrollear el contenedor de resultados
        print("Cargando lista de lugares...")
        feed = page.locator('div[role="feed"]').first
        
        for scroll_i in range(10):
            cards = page.locator('a[href*="/maps/place/"]').all()
            print(f"  > Scroll {scroll_i + 1}/10 - Lugares detectados: {len(cards)}")
            if len(cards) >= max_results * 2:
                break
            try:
                if feed.is_visible():
                    feed.evaluate("el => el.scrollBy(0, 1200)")
                else:
                    page.mouse.wheel(0, 1200)
            except Exception:
                page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)
        
        # Obtener los elementos
        place_links = page.locator('a[href*="/maps/place/"]').all()
        print(f"\nProcesando fichas encontradas ({len(place_links)} en total)...")
        
        place_urls = []
        for pl in place_links:
            href = pl.get_attribute('href')
            aria = pl.get_attribute('aria-label')
            if href and href not in place_urls:
                place_urls.append((aria or "Sin nombre", href))
        
        detail_page = context.new_page()
        
        for idx, (raw_name, url) in enumerate(place_urls):
            if len(results) >= max_results:
                break
                
            try:
                detail_page.goto(url, timeout=25000)
                detail_page.wait_for_timeout(1800)
                
                # Nombre del negocio
                name = raw_name
                try:
                    title_el = detail_page.locator('h1.DUwDvf, div.m6QErb h1').first
                    if title_el.is_visible(timeout=1500):
                        name = title_el.inner_text().strip()
                except Exception:
                    pass
                
                if name in seen_names or not name:
                    continue
                seen_names.add(name)
                
                print(f"\n--- [{len(results)+1}/{max_results}] {name} ---")
                
                # Calificación y reviews
                rating = ""
                try:
                    r_el = detail_page.locator('span.MW4etd, div.F7nice span[aria-hidden="true"]').first
                    if r_el.is_visible(timeout=1000):
                        rating = r_el.inner_text().strip()
                except Exception:
                    pass
                
                # Categoría / Nicho
                category = "Odontología"
                try:
                    c_el = detail_page.locator('button[jsaction*="category"], div.fontBodyMedium button.DkEaL').first
                    if c_el.is_visible(timeout=1000):
                        category = c_el.inner_text().strip()
                except Exception:
                    pass
                
                # Dirección
                address = ""
                try:
                    addr_btn = detail_page.locator('button[data-item-id*="address"], button[aria-label*="Dirección:"]').first
                    if addr_btn.is_visible(timeout=1000):
                        raw_addr = addr_btn.get_attribute('aria-label') or addr_btn.inner_text()
                        address = raw_addr.replace("Dirección: ", "").replace("Dirección:", "").strip()
                except Exception:
                    pass
                
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
                        all_text = detail_page.locator('body').inner_text()
                        phone_match = re.search(r'(\+?54\s*9?\s*387[\s\d-]{6,12}|0?387[\s\d-]{6,10})', all_text)
                        if phone_match:
                            raw_phone = phone_match.group(1).strip()
                    except Exception:
                        pass
                
                # Sitio Web
                website_url = ""
                try:
                    web_btn = detail_page.locator('a[data-item-id="authority"], a[aria-label*="Sitio web:"]').first
                    if web_btn.is_visible(timeout=1000):
                        website_url = web_btn.get_attribute('href') or ""
                except Exception:
                    pass
                
                formatted_phone = format_phone_for_whatsapp(raw_phone)
                has_real_web = is_real_website(website_url)
                
                # Contact name
                contact_name = name
                if "Dr." not in name and "Dra." not in name:
                    if any(w in name.lower() for w in ["clínica", "clinica", "centro", "consultorio", "odontolog", "instituto"]):
                        contact_name = f"Equipo {name}"
                    else:
                        contact_name = name
                
                msg = generate_custom_message(contact_name, name, has_real_web, website_url)
                
                item_data = {
                    "id": f"maps_{len(results)+1:02d}",
                    "business": name,
                    "name": contact_name,
                    "niche": category,
                    "location": address or "Salta Capital",
                    "phone": formatted_phone or raw_phone,
                    "rawPhone": raw_phone,
                    "hasRealWebsite": has_real_web,
                    "websiteUrl": website_url,
                    "rating": rating,
                    "customMessage": msg,
                    "status": "PENDING",
                    "source": "Google Maps"
                }
                
                web_status_desc = f"SÍ ({website_url}) [Modernización]" if has_real_web else ("Red social/WA [Crear Web Propia]" if website_url else "NO [Crear Web Propia]")
                print(f"  Dirección : {address or 'No indicada'}")
                print(f"  Teléfono  : {raw_phone or 'No disponible'} -> WhatsApp: {formatted_phone or 'No disponible'}")
                print(f"  Sitio Web : {web_status_desc}")
                print(f"  Rating    : {rating or 'S/C'}")
                
                results.append(item_data)
                
            except Exception as e:
                print(f"  [!] Error procesando lugar: {e}")
                continue
                
        detail_page.close()
        browser.close()
        
    print(f"\n========================================================")
    print(f"Scraping finalizado. Se obtuvieron {len(results)} prospectos.")
    print(f"========================================================\n")
    return results

def sync_to_wally(prospects, base_url="https://wally_bot.dario10.pw"):
    """
    Sube los prospectos scrapeados directamente a Wally Bot en la nube.
    """
    print(f"Sincronizando {len(prospects)} prospectos con Wally Bot ({base_url})...")
    ctx = ssl._create_unverified_context()
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
    
    # Save
    save_data = json.dumps({'prospects': prospects}).encode('utf-8')
    req2 = urllib.request.Request(f'{base_url}/api/prospects', data=save_data, headers=headers)
    res2 = urllib.request.urlopen(req2, context=ctx)
    print("Sincronización completada con éxito:", res2.read().decode('utf-8'))

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "odontologos en Salta Capital"
    max_count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    output_file = sys.argv[3] if len(sys.argv) > 3 else "scraped_maps_prospects.json"
    
    data = scrape_google_maps(query=query, max_results=max_count, headless=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Archivo guardado exitosamente en: {output_file}")
    
    # Si se pasa flag --sync
    if "--sync" in sys.argv:
        sync_to_wally(data)
