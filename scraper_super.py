# -*- coding: utf-8 -*-
"""
Scraper de supermercados de Panamá por categorías.
Genera un archivo CSV por supermercado con TODOS los productos de cada categoría
(nombre, precios normalizados, enlace), recorriendo la paginación.
VERSIÓN MEJORADA PARA GITHUB ACTIONS CON TIMEOUTS
"""
import os
import time
import re
import csv
import sys
import signal
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ================= CONFIGURACIÓN =================
MAX_PAGES = None          # páginas máximas por categoría (None = todas)
MAX_CATEGORIES = None     # categorías máximas por supermercado (None = todas)
DATA_DIR = "data"         # carpeta donde se guardan las CSV
TIMEOUT_PER_SUPER = 120   # tiempo máximo en segundos por supermercado
PAGE_LOAD_WAIT = 5        # tiempo de espera para carga de página
SCROLL_WAIT = 0.8         # tiempo entre scrolls

RIBA_URL = "https://www.ribasmith.com/index.php"
RIBA_CATEGORIES = [
    ("Bebé", f"{RIBA_URL}/otros-departamentos/bebe.html"),
    ("Bebidas y Jugos", f"{RIBA_URL}/otros-departamentos/bebidas-y-jugos.html"),
    ("Carnes y Embutidos", f"{RIBA_URL}/otros-departamentos/carnes-y-embutidos.html"),
    ("Comidas Preparadas", f"{RIBA_URL}/otros-departamentos/comidas-preparadas.html"),
    ("Congelado", f"{RIBA_URL}/otros-departamentos/congelados.html"),
    ("Cuidado Personal", f"{RIBA_URL}/otros-departamentos/cuidado-personal.html"),
    ("Despensa", f"{RIBA_URL}/otros-departamentos/despensa.html"),
    ("Escolar y Oficina", f"{RIBA_URL}/otros-departamentos/escolar-y-oficina.html"),
    ("Farmacia", f"{RIBA_URL}/otros-departamentos/farmacia.html"),
    ("Frutas y Verduras", f"{RIBA_URL}/otros-departamentos/frutas-y-verduras.html"),
    ("Hogar", f"{RIBA_URL}/otros-departamentos/hogar.html"),
    ("Jardinería", f"{RIBA_URL}/otros-departamentos/jardineria.html"),
    ("Lácteos", f"{RIBA_URL}/otros-departamentos/lacteos.html"),
    ("Librería", f"{RIBA_URL}/otros-departamentos/libreria.html"),
    ("Licores", f"{RIBA_URL}/otros-departamentos/licores.html"),
    ("Mariscos", f"{RIBA_URL}/otros-departamentos/mariscos.html"),
    ("Mascotas", f"{RIBA_URL}/otros-departamentos/mascotas.html"),
    ("Misceláneos", f"{RIBA_URL}/otros-departamentos/miscelaneos.html"),
    ("Panes y Dulces", f"{RIBA_URL}/otros-departamentos/panes-y-dulces.html"),
    ("Productos de Maíz", f"{RIBA_URL}/otros-departamentos/productos-de-maiz-y-otros.html"),
    ("Snacks", f"{RIBA_URL}/otros-departamentos/snacks.html"),
    ("Refrigerado", f"{RIBA_URL}/otros-departamentos/refrigerado.html"),
    ("Promociones", "https://www.ribasmith.com/index.php/seccion/grandes-ofer.html"),
]

S99_URL = "https://www.super99.com"
S99_CATEGORIES = [
    ("Accesorios Hogar", f"{S99_URL}/accesorios-para-el-hogar"),
    ("Aseo del Hogar", f"{S99_URL}/aseo-del-hogar"),
    ("Bebidas no Alcoholicas", f"{S99_URL}/bebidas-no-alcoholicas"),
    ("Cervezas, Vinos y Licores", f"{S99_URL}/cervezas-vinos-y-licores"),
    ("Comidas Preparadas", f"{S99_URL}/comidas-preparadas"),
    ("Congelados y Refrigerados", f"{S99_URL}/congelados"),
    ("Cuidado de Bebes", f"{S99_URL}/cuidado-de-bebes"),
    ("Despensa", f"{S99_URL}/despensa"),
    ("Escolar", f"{S99_URL}/escolar"),
    ("Farmacia", f"{S99_URL}/farmacia"),
    ("Ferreteria", f"{S99_URL}/ferreteria"),
    ("Higiene y Belleza", f"{S99_URL}/higiene-belleza"),
    ("Jardineria", f"{S99_URL}/jardineria"),
    ("Jugueteria", f"{S99_URL}/jugueteria"),
    ("Lacteos y Huevos", f"{S99_URL}/lacteos-y-huevos"),
    ("Mascotas", f"{S99_URL}/mascotas"),
    ("Panes y Dulces", f"{S99_URL}/panes-dulces"),
    ("Productos Frescos", f"{S99_URL}/productos-frescos"),
    ("Accesorios de Cocina", f"{S99_URL}/accesorios-de-cocina"),
    ("Super Oferta", f"{S99_URL}/super-oferta"),
]

ELREY_URL = "https://www.smrey.com"
ELREY_CATEGORIES = [
    ("Carnes, Aves y Mariscos", f"{ELREY_URL}/ca/carnes-aves-y-mariscos/res/00200001/002000010007"),
    ("El Corte Ingles", f"{ELREY_URL}/ca/el-corte-ingles/00900002"),
    ("Frutas y Verduras", f"{ELREY_URL}/ca/frutas-y-verduras/00200005"),
    ("Hogar y Limpieza - Flores", f"{ELREY_URL}/ca/hogar-y-limpieza/patio-y-jardin/flores/00100006/001000060017/001000060017000006"),
    ("Lacteos y Huevos - Quesos", f"{ELREY_URL}/ca/lacteos-y-huevos/quesos/00200006/002000060005"),
    ("Marcas Propias", f"{ELREY_URL}/ca/marcas-propias/127?availablePromotions=true"),
    ("Punto de Oro", f"{ELREY_URL}/ca/punto-de-oro/00100010"),
    ("Tierra de Emprendedores", f"{ELREY_URL}/ca/tierra-de-emprendedores/00900004"),
    ("Promociones", f"{ELREY_URL}/promotions"),
]

MACHETAZO_URL = "https://www.elmachetazo.com"
MACHETAZO_CATEGORIES = [
    ("Supermercado", f"{MACHETAZO_URL}/supermercado"),
    ("Farmacia", f"{MACHETAZO_URL}/farmacia"),
    ("Tecnologia", f"{MACHETAZO_URL}/tecnologia"),
    ("Hogar", f"{MACHETAZO_URL}/hogar"),
    ("Escolar", f"{MACHETAZO_URL}/escolar"),
    ("Bebes", f"{MACHETAZO_URL}/bebes"),
    ("Ferreteria", f"{MACHETAZO_URL}/ferreteria"),
    ("Jugueteria", f"{MACHETAZO_URL}/jugueteria"),
    ("Deportes", f"{MACHETAZO_URL}/deportes"),
    ("Bicicletas", f"{MACHETAZO_URL}/bicicletas"),
    ("Sederia", f"{MACHETAZO_URL}/sederia"),
    ("Fiestas", f"{MACHETAZO_URL}/fiestas"),
]

SUPERXTRA_URL = "https://www.superxtra.com"
SUPERXTRA_CATEGORIES = [
    ("Supermercado", f"{SUPERXTRA_URL}/supermercado"),
    ("Licor, Cerveza y Vino", f"{SUPERXTRA_URL}/licor-cerveza-y-vino"),
    ("Cuidado Personal y Belleza", f"{SUPERXTRA_URL}/cuidado-personal-y-belleza"),
    ("Limpieza del Hogar y Ropa", f"{SUPERXTRA_URL}/limpieza-del-hogar-y-ropa"),
    ("Mascotas", f"{SUPERXTRA_URL}/mascotas"),
    ("Bebes", f"{SUPERXTRA_URL}/bebes"),
    ("Linea Blanca y Electrodomesticos", f"{SUPERXTRA_URL}/linea-blanca-y-electrodomesticos"),
    ("Hogar, Jardin y Ferreteria", f"{SUPERXTRA_URL}/hogar-jardin-y-ferreteria"),
    ("Jugueteria, Recreacion y Deportes", f"{SUPERXTRA_URL}/jugueteria-recreacion-y-deportes"),
    ("Xtra Farmacia", f"{SUPERXTRA_URL}/xtra-farmacia"),
    ("Escolar y Oficina", f"{SUPERXTRA_URL}/escolar-y-oficina"),
    ("Chef Cafe", f"{SUPERXTRA_URL}/chef-cafe"),
]

# ================= HELPERS =================

def _chrome_options():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,2200')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--remote-debugging-port=9222')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    return options

def _new_driver():
    try:
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=_chrome_options())
    except Exception as e:
        print(f"  Error al crear driver: {e}")
        return None

def _clean_nombre(nombre):
    if not nombre:
        return ""
    nombre = re.sub(r'\s*\.{2,}\s*', '', nombre)
    nombre = re.sub(r'\s*\u2026\s*', '', nombre)
    nombre = re.sub(r'\s{2,}', ' ', nombre)
    return nombre.strip()

def normalizar_precio(texto):
    if not texto:
        return None
    s = str(texto).strip().strip('()')
    cantidad = 1
    m_qty = re.match(r'^\s*(\d+)\s*[xX]\s+', s)
    if m_qty:
        cantidad = int(m_qty.group(1))
        s = s[m_qty.end():]
    s = re.sub(r'B/\.', '', s)
    s = re.sub(r'US\$', '', s)
    s = re.sub(r'\$', '', s)
    m = re.search(r'(\d[\d\.,]*)', s)
    if not m:
        return None
    monto_str = m.group(1)
    tiene_punto = '.' in monto_str
    tiene_coma = ',' in monto_str
    if tiene_punto and tiene_coma:
        if monto_str.rfind(',') > monto_str.rfind('.'):
            monto_str = monto_str.replace('.', '').replace(',', '.')
        else:
            monto_str = monto_str.replace(',', '')
    elif tiene_coma:
        dec = monto_str.split(',')[-1]
        monto_str = monto_str.replace(',', '.') if len(dec) <= 2 else monto_str.replace(',', '')
    try:
        monto = float(monto_str)
    except ValueError:
        return None
    return {"monto": monto, "moneda": "USD", "cantidad": cantidad}

def _precio_obj(texto):
    p = normalizar_precio(texto)
    if not p:
        return None
    return {"texto": str(texto).replace('\u00a0', ' ').strip().strip('()'), "monto": p["monto"],
            "moneda": p["moneda"], "cantidad": p["cantidad"],
            "precio_unit": round(p["monto"] / p["cantidad"], 4) if p["cantidad"] else p["monto"]}

def _precio_csv(p):
    if not p:
        return ""
    if 'monto' in p:
        return f"{p['monto']:.2f} {p['moneda']} (x{p['cantidad']})"
    return p

def _dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it["nombre"], it["enlace"])
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out

def _scroll(driver, veces=3, espera=0.8):
    for _ in range(veces):
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(espera)
        except Exception:
            break

# ================= RIBA SMITH (estático) =================

def _riba_parse(soup):
    out = []
    for prod in soup.select('.product-item-details'):
        name_el = prod.select_one('.product-item-link')
        nombre = _clean_nombre(name_el.get_text(strip=True)) if name_el else ""
        if not nombre:
            continue
        enlace = name_el.get('href') if name_el else ""
        if enlace and enlace.startswith('/'):
            enlace = RIBA_URL + enlace
        final_el = prod.select_one('.price-wrapper[data-price-type=finalPrice] .price')
        old_el = prod.select_one('.old-price .price')
        spec_el = prod.select_one('.special-price .price')
        if spec_el:
            oferta = spec_el.get_text(strip=True)
            regular = old_el.get_text(strip=True) if old_el else (final_el.get_text(strip=True) if final_el else "")
        else:
            oferta = final_el.get_text(strip=True) if final_el else ""
            regular = ""
        out.append({
            "nombre": nombre,
            "precio_oferta": _precio_obj(oferta),
            "precio_regular": _precio_obj(regular) or _precio_obj(oferta),
            "enlace": enlace or "",
        })
    return out

def _riba_pages(url):
    urls = [url]
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        pg = soup.select_one('.pages')
        if pg:
            for a in pg.find_all('a', href=True):
                h = a.get('href')
                if h and re.search(r'\?p=\d+', h) and h.startswith('http'):
                    urls.append(h)
        seen = set(); out = []
        for u in urls:
            if u not in seen:
                seen.add(u); out.append(u)
        return out[:MAX_PAGES] if MAX_PAGES else out
    except Exception as e:
        print(f"    error obteniendo páginas: {e}")
        return [url]

def scrape_riba(url, nombre_cat):
    print(f"  [Riba] {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resultados = []
    for page_url in _riba_pages(url):
        try:
            r = requests.get(page_url, headers=headers, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            resultados.extend(_riba_parse(soup))
        except Exception as e:
            print(f"    error página {page_url}: {e}")
            break
    return _dedupe(resultados)

# ================= VTEX (Machetazo, Super Xtra) =================

def scrape_machetazo(url, nombre_cat):
    print(f"  [Machetazo] {url}")
    return _vtex_scrape(MACHETAZO_URL, url, nombre_cat)

def scrape_superxtra(url, nombre_cat):
    print(f"  [Super Xtra] {url}")
    return _vtex_scrape(SUPERXTRA_URL, url, nombre_cat)

def _vtex_scrape(base_url, cat_url, nombre_cat):
    """Scraper genérico para VTEX (Machetazo, Super Xtra, etc.)."""
    def api_path(cat_url):
        path = cat_url.split(".com", 1)[-1]
        return "/" + path.strip("/").replace("//", "/")
    api = f"{base_url}/api/catalog_system/pub/products/search{api_path(cat_url)}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    resultados = []
    try:
        from_ = 0
        total = None
        while True:
            if MAX_PAGES is not None and (from_ // 50) >= MAX_PAGES:
                break
            r = requests.get(api, headers=headers, params={"_from": from_, "_to": from_ + 49}, timeout=20)
            if r.status_code not in (200, 206):
                print(f"    API status {r.status_code} (categoria no disponible)")
                break
            data = r.json() or []
            if not data:
                break
            for p in data if isinstance(data, list) else []:
                name = _clean_nombre(p.get("productName") or "")
                if not name:
                    continue
                link_text = p.get("linkText") or p.get("productReference") or ""
                enlace = f"{base_url}/{link_text}/p" if link_text else ""
                oferta = regular = None
                items = p.get("items") or []
                if items:
                    sellers = items[0].get("sellers") or []
                    if sellers:
                        co = sellers[0].get("commertialOffer") or {}
                        price = co.get("Price")
                        list_price = co.get("ListPrice")
                        if price is not None:
                            oferta = f"B/. {price:.2f}"
                            if list_price and abs(list_price - price) > 0.001:
                                regular = f"B/. {list_price:.2f}"
                resultados.append({
                    "nombre": name,
                    "precio_oferta": _precio_obj(oferta),
                    "precio_regular": _precio_obj(regular) or _precio_obj(oferta),
                    "enlace": enlace,
                })
            res = r.headers.get("resources") or ""
            if "/" in res:
                total = int(res.rsplit("/", 1)[-1])
            from_ += 50
            if total and from_ >= total:
                break
        return _dedupe(resultados)
    except Exception as e:
        print(f"  error en VTEX: {e}")
        return []

# ================= SUPER 99 (Selenium) =================

def _s99_parse(soup):
    out = []
    for item in soup.select('.ds-sdk-product-item'):
        name_el = item.select_one('.ds-sdk-product-item__product-name')
        nombre = _clean_nombre(name_el.get_text(strip=True)) if name_el else ""
        if not nombre:
            continue
        link_el = item.select_one('.ds-sdk-product-item__link')
        enlace = link_el.get('href') if link_el else ""
        if enlace.startswith('//'):
            enlace = "https:" + enlace
        elif enlace.startswith('/'):
            enlace = S99_URL + enlace
        badge = item.select_one('.plp-discount-percentage-badge')
        if badge:
            final = badge.get('data-final')
            regular = badge.get('data-regular')
            texto_o = f"${final}" if final else ""
            texto_r = f"${regular}" if regular else texto_o
        else:
            price_el = item.select_one('.ds-sdk-product-price')
            texto_o = price_el.get_text(strip=True) if price_el else ""
            texto_r = ""
        out.append({
            "nombre": nombre,
            "precio_oferta": _precio_obj(texto_o),
            "precio_regular": _precio_obj(texto_r) or _precio_obj(texto_o),
            "enlace": enlace,
        })
    return out

def _s99_click_page(driver, numero):
    """Hace clic en el <li> de paginación cuyo texto es el número dado."""
    try:
        for li in driver.find_elements(By.CSS_SELECTOR, ".ds-plp-pagination__item"):
            if (li.get_attribute('textContent') or '').strip() == str(numero):
                driver.execute_script("arguments[0].click();", li)
                time.sleep(1.5)
                return True
    except Exception:
        pass
    return False

def scrape_super99(url, nombre_cat):
    print(f"  [Super99] {url}")
    driver = _new_driver()
    if driver is None:
        return []
    resultados = []
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(PAGE_LOAD_WAIT)
        _scroll(driver, veces=3)
        resultados.extend(_s99_parse(BeautifulSoup(driver.page_source, 'html.parser')))
        pagina = 1
        while (not MAX_PAGES or pagina < MAX_PAGES) and _s99_click_page(driver, pagina + 1):
            pagina += 1
            if not MAX_PAGES or pagina <= MAX_PAGES:
                resultados.extend(_s99_parse(BeautifulSoup(driver.page_source, 'html.parser')))
        return _dedupe(resultados)
    except TimeoutException:
        print(f"  [Super99] Timeout cargando {url}")
        return resultados
    except Exception as e:
        print(f"  [Super99] Error: {e}")
        return resultados
    finally:
        try:
            driver.quit()
        except:
            pass

# ================= EL REY (Selenium) =================

def _elrey_parse(soup):
    out = []
    for div in soup.select('div[data-testid^="product-context-provider-"]'):
        name_el = div.select_one('h3[data-testid="card-name"]')
        nombre = _clean_nombre(name_el.get_text(strip=True)) if name_el else ""
        if not nombre:
            continue
        enlace = ""
        a = div.find('a', href=True)
        if a and isinstance(a['href'], str):
            enlace = a['href'] if a['href'].startswith('http') else ELREY_URL + a['href']
        base_el = div.select_one('p[data-testid="card-base-price"]')
        base_unit = base_el.get_text(strip=True) if base_el else None
        crossed = div.select_one('div[data-testid="crossed-out-price-a"]')
        oferta_text = None
        regular_text = None
        if crossed:
            cur = crossed.select_one('p.base__price')
            old = crossed.select_one('p.prod-crossed-out__price__old')
            if cur: oferta_text = cur.get_text(strip=True)
            if old: regular_text = old.get_text(strip=True).strip('()')
        promo_el = div.select_one('p.prod__n-per-price__text')
        promo_text = promo_el.get_text(strip=True) if promo_el else None

        if oferta_text:
            pass
        elif promo_text:
            oferta_text = promo_text
            if base_unit:
                pb = normalizar_precio(base_unit)
                pp = normalizar_precio(promo_text)
                if pb and pp:
                    regular_text = f"B/. {round(pb['monto'] * pp['cantidad'], 2):.2f}"
        else:
            oferta_text = base_unit
        if not regular_text:
            regular_text = base_unit or (oferta_text if oferta_text else "")

        out.append({
            "nombre": nombre,
            "precio_oferta": _precio_obj(oferta_text) or ({"texto": oferta_text} if oferta_text else None),
            "precio_regular": _precio_obj(regular_text) or _precio_obj(oferta_text),
            "enlace": enlace,
        })
    return out

def _elrey_next(driver):
    try:
        els = driver.find_elements(By.CSS_SELECTOR, ".ant-pagination-next")
        if not els:
            return False
        if 'ant-pagination-disabled' in (els[0].get_attribute('class') or ''):
            return False
        driver.execute_script("arguments[0].click();", els[0])
        time.sleep(1.5)
        return True
    except Exception:
        return False

def scrape_elrey(url, nombre_cat):
    print(f"  [ElRey] {url}")
    driver = _new_driver()
    if driver is None:
        return []
    resultados = []
    try:
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(PAGE_LOAD_WAIT)
        _scroll(driver, veces=4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        resultados.extend(_elrey_parse(soup))
        pagina = 1
        while (not MAX_PAGES or pagina < MAX_PAGES) and _elrey_next(driver):
            pagina += 1
            resultados.extend(_elrey_parse(BeautifulSoup(driver.page_source, 'html.parser')))
        return _dedupe(resultados)
    except TimeoutException:
        print(f"  [ElRey] Timeout cargando {url}")
        return resultados
    except Exception as e:
        print(f"  [ElRey] Error: {e}")
        return resultados
    finally:
        try:
            driver.quit()
        except:
            pass

# ================= SALIDA CSV =================

def _init_csv(filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, filename), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["categoria", "nombre", "precio_oferta", "precio_regular", "enlace"])

def _dump_csv(filename, nombre_cat, rows):
    with open(os.path.join(DATA_DIR, filename), "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([
                nombre_cat,
                r["nombre"],
                _precio_csv(r["precio_oferta"]),
                _precio_csv(r["precio_regular"]),
                r["enlace"],
            ])

def scrape_with_timeout(super_name, scraper_func, url, cat):
    """Ejecuta un scraper con timeout usando signal."""
    import signal
    import functools
    
    class TimeoutError(Exception):
        pass
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Timeout en {super_name} - {cat}")
    
    # Configurar el timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT_PER_SUPER)
    
    try:
        result = scraper_func(url, cat)
        signal.alarm(0)  # Cancelar timeout
        return result
    except TimeoutError as e:
        print(f"  ⚠️ {e}")
        return []
    finally:
        signal.signal(signal.SIGALRM, old_handler)

def main():
    runs = [
        ("Riba Smith", "riba_smith.csv", RIBA_CATEGORIES, scrape_riba),
        ("Super 99", "super99.csv", S99_CATEGORIES, scrape_super99),
        ("El Rey", "elrey.csv", ELREY_CATEGORIES, scrape_elrey),
        ("El Machetazo", "machetazo.csv", MACHETAZO_CATEGORIES, scrape_machetazo),
        ("Super Xtra", "superxtra.csv", SUPERXTRA_CATEGORIES, scrape_superxtra),
    ]
    
    total_global = 0
    
    for super_, outname, cats, scraper in runs:
        print(f"\n{'='*55}")
        print(f"{super_}")
        print(f"{'='*55}")
        
        _init_csv(outname)
        cats = cats[:MAX_CATEGORIES] if MAX_CATEGORIES else cats
        total = 0
        
        for cat, url in cats:
            print(f"\n  Categoría: {cat}")
            print(f"  URL: {url}")
            
            try:
                # Ejecutar con timeout
                data = scrape_with_timeout(super_, scraper, url, cat)
                _dump_csv(outname, cat, data)
                print(f"  ✅ {cat}: {len(data)} productos")
                total += len(data)
                total_global += len(data)
            except Exception as e:
                print(f"  ❌ Error en {cat}: {e}")
                # Continuar con la siguiente categoría
        
        print(f"\n  📊 {super_}: {total} productos totales -> {outname}")
    
    print(f"\n{'='*55}")
    print(f"✅ SCRAPING COMPLETADO: {total_global} productos totales")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
