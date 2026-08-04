# -*- coding: utf-8 -*-
"""
Scraper optimizado de supermercados de Panamá.
- Paraleliza tiendas VTEX (API) y estáticas (requests)
- Reutiliza sesiones HTTP y driver Selenium
- Timeouts agresivos, reintentos y skip de categorías fallidas
- NO ejecuta la IA (ai_engine.py) — esa es un workflow manual aparte
"""
import os
import time
import re
import csv
import sys
import argparse
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ================= CONFIGURACIÓN (defaults, sobreescribibles por CLI) =================
MAX_PAGES = 20               # límite páginas por categoría (ajusta si quieres más)
MAX_CATEGORIES = None        # None = todas
DATA_DIR = "data"
REQUEST_TIMEOUT = 15         # seg
SELENIUM_WAIT = 10           # seg max wait for elements
MAX_RETRIES = 2              # reintentos por categoría
RATE_LIMIT = 0.5             # seg entre requests (evita 429)

def parse_args():
    parser = argparse.ArgumentParser(description="Scraper supermercados Panamá")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Páginas máximas por categoría")
    parser.add_argument("--max-categories", type=int, default=None, help="Categorías máximas por tienda")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Directorio de salida CSVs")
    parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help="Timeout HTTP (seg)")
    parser.add_argument("--selenium-wait", type=int, default=SELENIUM_WAIT, help="Wait Selenium (seg)")
    parser.add_argument("--retries", type=int, default=MAX_RETRIES, help="Reintentos por categoría")
    parser.add_argument("--rate-limit", type=float, default=RATE_LIMIT, help="Delay entre requests (seg)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging DEBUG")
    return parser.parse_args()

args = parse_args()
if args.verbose:
    log.setLevel(logging.DEBUG)

# Override globals from CLI
MAX_PAGES = args.max_pages
MAX_CATEGORIES = args.max_categories
DATA_DIR = args.data_dir
REQUEST_TIMEOUT = args.timeout
SELENIUM_WAIT = args.selenium_wait
MAX_RETRIES = args.retries
RATE_LIMIT = args.rate_limit

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

# ================= HELPERS GLOBALES =================

# Pre-compiled regexes for performance
_RE_QTY = re.compile(r"^\s*(\d+)\s*[xX]\s+")
_RE_PRICE = re.compile(r"(\d[\d\.,]*)")
_RE_CLEAN_NAME = re.compile(r"\s*\.{2,}\s*|\s*\u2026\s*|\s{2,}")

_session_local = threading.local()

def _get_session() -> requests.Session:
    """Session por hilo con connection pooling."""
    if not hasattr(_session_local, "session"):
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _session_local.session = s
    return _session_local.session

def _chrome_options():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,1600")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-images")  # no cargar imágenes = más rápido
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    return opts

_driver_local = threading.local()

def _get_driver() -> webdriver.Chrome:
    """Driver Selenium por hilo (reutilizado)."""
    if not hasattr(_driver_local, "driver"):
        _driver_local.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=_chrome_options()
        )
    return _driver_local.driver

def _quit_driver():
    if hasattr(_driver_local, "driver"):
        try:
            _driver_local.driver.quit()
        except Exception:
            pass
        del _driver_local.driver

def _clean_nombre(nombre: str) -> str:
    if not nombre:
        return ""
    return _RE_CLEAN_NAME.sub(" ", nombre).strip()

def normalizar_precio(texto: str):
    if not texto:
        return None
    s = str(texto).strip().strip("()")
    cantidad = 1
    m_qty = _RE_QTY.match(s)
    if m_qty:
        cantidad = int(m_qty.group(1))
        s = s[m_qty.end():]
    s = re.sub(r"[B/\.\sUS$\$]", "", s)
    m = _RE_PRICE.search(s)
    if not m:
        return None
    monto_str = m.group(1)
    if "," in monto_str and "." in monto_str:
        monto_str = monto_str.replace(".", "").replace(",", ".")
    elif "," in monto_str:
        monto_str = monto_str.replace(",", ".")
    try:
        return {"monto": float(monto_str), "moneda": "USD", "cantidad": cantidad}
    except ValueError:
        return None

def _precio_obj(texto):
    p = normalizar_precio(texto)
    if not p:
        return None
    return {"texto": str(texto).replace("\u00a0", " ").strip().strip("()"),
            "monto": p["monto"], "moneda": p["moneda"], "cantidad": p["cantidad"],
            "precio_unit": round(p["monto"] / p["cantidad"], 4) if p["cantidad"] else p["monto"]}

def _precio_csv(p):
    if not p:
        return ""
    if "monto" in p:
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

# ================= RIBA SMITH (requests + BS4) =================

def _riba_parse(soup):
    out = []
    for prod in soup.select(".product-item-details"):
        name_el = prod.select_one(".product-item-link")
        nombre = _clean_nombre(name_el.get_text(strip=True)) if name_el else ""
        if not nombre:
            continue
        enlace = name_el.get("href") if name_el else ""
        if enlace.startswith("/"):
            enlace = RIBA_URL + enlace
        final_el = prod.select_one(".price-wrapper[data-price-type=finalPrice] .price")
        old_el = prod.select_one(".old-price .price")
        spec_el = prod.select_one(".special-price .price")
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
            "enlace": enlace,
        })
    return out

def _riba_pages(url, session):
    urls = [url]
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        pg = soup.select_one(".pages")
        if pg:
            for a in pg.find_all("a", href=True):
                h = a.get("href")
                if re.search(r"\?p=\d+", h) and h.startswith("http"):
                    urls.append(h)
        seen = set()
        return [u for u in urls if not (u in seen or seen.add(u))]
    except Exception:
        return [url]

def scrape_riba(url, nombre_cat):
    log.info("[Riba] %s", url)
    session = _get_session()
    resultados = []
    for page_url in _riba_pages(url, session):
        for attempt in range(MAX_RETRIES + 1):
            try:
                r = session.get(page_url, timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                resultados.extend(_riba_parse(BeautifulSoup(r.text, "html.parser")))
                break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    log.warning("página falló tras reintentos: %s", e)
                else:
                    time.sleep(1)
        time.sleep(RATE_LIMIT)
    return _dedupe(resultados)

# ================= VTEX (Machetazo, Super Xtra) =================

def _vtex_api_path(cat_url):
    path = cat_url.split(".com", 1)[-1]
    return "/" + path.strip("/").replace("//", "/")

def _vtex_scrape(base_url, cat_url, nombre_cat):
    api = f"{base_url}/api/catalog_system/pub/products/search{_vtex_api_path(cat_url)}"
    session = _get_session()
    resultados = []
    from_ = 0
    total = None
    while True:
        if MAX_PAGES and (from_ // 50) >= MAX_PAGES:
            break
        for attempt in range(MAX_RETRIES + 1):
            try:
                r = session.get(api, params={"_from": from_, "_to": from_ + 49}, timeout=REQUEST_TIMEOUT)
                if r.status_code not in (200, 206):
                    if attempt == MAX_RETRIES:
                        log.warning("API status %s", r.status_code)
                    break
                data = r.json() or []
                if not data:
                    return _dedupe(resultados)
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
                    return _dedupe(resultados)
                break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    log.warning("error API: %s", e)
                    return _dedupe(resultados)
                time.sleep(1)
        time.sleep(RATE_LIMIT)
    return _dedupe(resultados)

def scrape_machetazo(url, nombre_cat):
    log.info("[Machetazo] %s", url)
    return _vtex_scrape(MACHETAZO_URL, url, nombre_cat)

def scrape_superxtra(url, nombre_cat):
    log.info("[Super Xtra] %s", url)
    return _vtex_scrape(SUPERXTRA_URL, url, nombre_cat)

# ================= SUPER 99 (Selenium) =================

def _s99_parse(soup):
    out = []
    for item in soup.select(".ds-sdk-product-item"):
        name_el = item.select_one(".ds-sdk-product-item__product-name")
        nombre = _clean_nombre(name_el.get_text(strip=True)) if name_el else ""
        if not nombre:
            continue
        link_el = item.select_one(".ds-sdk-product-item__link")
        enlace = link_el.get("href") if link_el else ""
        if enlace.startswith("//"):
            enlace = "https:" + enlace
        elif enlace.startswith("/"):
            enlace = S99_URL + enlace
        badge = item.select_one(".plp-discount-percentage-badge")
        if badge:
            final = badge.get("data-final")
            regular = badge.get("data-regular")
            texto_o = f"${final}" if final else ""
            texto_r = f"${regular}" if regular else texto_o
        else:
            price_el = item.select_one(".ds-sdk-product-price")
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
    try:
        for li in driver.find_elements(By.CSS_SELECTOR, ".ds-plp-pagination__item"):
            if (li.get_attribute("textContent") or "").strip() == str(numero):
                driver.execute_script("arguments[0].click();", li)
                time.sleep(1.5)
                return True
    except Exception:
        pass
    return False

def scrape_super99(url, nombre_cat):
    log.info("[Super99] %s", url)
    driver = _get_driver()
    resultados = []
    try:
        driver.get(url)
        # wait for products to load
        WebDriverWait(driver, SELENIUM_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".ds-sdk-product-item"))
        )
        time.sleep(1)
        resultados.extend(_s99_parse(BeautifulSoup(driver.page_source, "html.parser")))
        pagina = 1
        while (not MAX_PAGES or pagina < MAX_PAGES) and _s99_click_page(driver, pagina + 1):
            pagina += 1
            if not MAX_PAGES or pagina <= MAX_PAGES:
                time.sleep(0.8)
                resultados.extend(_s99_parse(BeautifulSoup(driver.page_source, "html.parser")))
        return _dedupe(resultados)
    except Exception as e:
        log.warning("error Super99: %s", e)
        return []
    # NO quitamos driver aquí: se reutiliza en la siguiente categoría

# ================= EL REY (Selenium) =================

def _elrey_parse(soup):
    out = []
    for div in soup.select('div[data-testid^="product-context-provider-"]'):
        name_el = div.select_one('h3[data-testid="card-name"]')
        nombre = _clean_nombre(name_el.get_text(strip=True)) if name_el else ""
        if not nombre:
            continue
        enlace = ""
        a = div.find("a", href=True)
        if a and isinstance(a["href"], str):
            enlace = a["href"] if a["href"].startswith("http") else ELREY_URL + a["href"]
        base_el = div.select_one('p[data-testid="card-base-price"]')
        base_unit = base_el.get_text(strip=True) if base_el else None
        crossed = div.select_one('div[data-testid="crossed-out-price-a"]')
        oferta_text = regular_text = None
        if crossed:
            cur = crossed.select_one("p.base__price")
            old = crossed.select_one("p.prod-crossed-out__price__old")
            if cur:
                oferta_text = cur.get_text(strip=True)
            if old:
                regular_text = old.get_text(strip=True).strip("()")
        promo_el = div.select_one("p.prod__n-per-price__text")
        promo_text = promo_el.get_text(strip=True) if promo_el else None
        if not oferta_text and promo_text:
            oferta_text = promo_text
            if base_unit:
                pb = normalizar_precio(base_unit)
                pp = normalizar_precio(promo_text)
                if pb and pp:
                    regular_text = f"B/. {round(pb['monto'] * pp['cantidad'], 2):.2f}"
        if not regular_text:
            regular_text = base_unit or oferta_text or ""
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
        if not els or "ant-pagination-disabled" in (els[0].get_attribute("class") or ""):
            return False
        driver.execute_script("arguments[0].click();", els[0])
        time.sleep(1.5)
        return True
    except Exception:
        return False

def scrape_elrey(url, nombre_cat):
    log.info("[ElRey] %s", url)
    driver = _get_driver()
    resultados = []
    try:
        driver.get(url)
        WebDriverWait(driver, SELENIUM_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid^="product-context-provider-"]'))
        )
        time.sleep(1)
        _scroll_fast(driver)
        resultados.extend(_elrey_parse(BeautifulSoup(driver.page_source, "html.parser")))
        pagina = 1
        while (not MAX_PAGES or pagina < MAX_PAGES) and _elrey_next(driver):
            pagina += 1
            if not MAX_PAGES or pagina <= MAX_PAGES:
                time.sleep(0.8)
                _scroll_fast(driver)
                resultados.extend(_elrey_parse(BeautifulSoup(driver.page_source, "html.parser")))
        return _dedupe(resultados)
    except Exception as e:
        log.warning("error ElRey: %s", e)
        return []

def _scroll_fast(driver, veces=3):
    for _ in range(veces):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)

# ================= SALIDA CSV =================

def _init_csv(filename):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, filename), "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow(["categoria", "nombre", "precio_oferta", "precio_regular", "enlace"])

def _dump_csv(filename, nombre_cat, rows):
    with open(os.path.join(DATA_DIR, filename), "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([nombre_cat, r["nombre"], _precio_csv(r["precio_oferta"]), _precio_csv(r["precio_regular"]), r["enlace"]])

# ================= MAIN: PARALELIZA TIENDAS INDEPENDIENTES =================

def _scrape_store(args):
    """Wrapper para ThreadPoolExecutor."""
    super_name, filename, cats, scraper = args
    log.info("\n%s\n%s\n%s", "="*50, super_name, "="*50)
    _init_csv(filename)
    cats = cats[:MAX_CATEGORIES] if MAX_CATEGORIES else cats
    total = 0
    for cat, url in cats:
        try:
            data = scraper(url, cat)
            _dump_csv(filename, cat, data)
            log.info("  %s: %d productos (total %d)", cat, len(data), total + len(data))
            total += len(data)
        except Exception as e:
            log.warning("  %s falló: %s", cat, e)
    log.info("-> %s: %d productos -> %s", super_name, total, filename)
    return super_name, total

def main():
    runs = [
        ("Riba Smith", "riba_smith.csv", RIBA_CATEGORIES, scrape_riba),
        ("Super 99", "super99.csv", S99_CATEGORIES, scrape_super99),
        ("El Rey", "elrey.csv", ELREY_CATEGORIES, scrape_elrey),
        ("El Machetazo", "machetazo.csv", MACHETAZO_CATEGORIES, scrape_machetazo),
        ("Super Xtra", "superxtra.csv", SUPERXTRA_CATEGORIES, scrape_superxtra),
    ]

    # Grupos que pueden correr en paralelo (no comparten driver)
    # Grupo 1: requests-only (Riba, Machetazo, Super Xtra) — 3 hilos
    # Grupo 2: Selenium (Super99, ElRey) — secuencial para reutilizar driver
    with ThreadPoolExecutor(max_workers=3) as ex:
        # Grupo requests
        req_runs = [r for r in runs if r[0] in ("Riba Smith", "El Machetazo", "Super Xtra")]
        futuros = {ex.submit(_scrape_store, r): r[0] for r in req_runs}
        for fut in as_completed(futuros):
            try:
                fut.result()
            except Exception as e:
                log.error("%s error fatal: %s", futuros[fut], e)

    # Grupo Selenium (secuencial, reutiliza driver)
    for r in runs:
        if r[0] in ("Super 99", "El Rey"):
            try:
                _scrape_store(r)
            except Exception as e:
                log.error("%s error fatal: %s", r[0], e)

    # Limpieza drivers
    _quit_driver()
    log.info("Scraper terminado. CSVs en %s/", DATA_DIR)

if __name__ == "__main__":
    main()