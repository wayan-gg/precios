# -*- coding: utf-8 -*-
"""
Motor de destilación ("IA" heurística, sin APIs ni costos).
Lee las CSV crudas generadas por scraper_super.py y produce un único
archivo JSON 'web/data.json' con la información destilada:

- Quién tiene las MEJORES promociones hoy (mejor supermercado).
- Top de promociones rankeadas por descuento real.
- Comparativas: mismo producto en varias tiendas -> dónde está.
- Estadísticas por tienda.

El JSON resultante es la "base de datos" servida por la página (GitHub Pages
es estático, así que este archivo ES el backend).
"""
import argparse
import csv
import datetime
import json
import logging
import os
import re
import unicodedata
from collections import defaultdict

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ================= CONFIG (defaults, sobreescribibles por CLI) =================
DATA_DIR = "data"
OUT_JSON = os.path.join("web", "data.json")

SUPERMERCADOS = [
    ("riba_smith.csv", "Riba Smith"),
    ("super99.csv", "Super 99"),
    ("elrey.csv", "El Rey"),
    ("machetazo.csv", "El Machetazo"),
    ("superxtra.csv", "Super Xtra"),
]

def parse_args():
    parser = argparse.ArgumentParser(description="Motor IA - destila CSVs a JSON")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Directorio con CSVs crudos")
    parser.add_argument("--out-json", default=OUT_JSON, help="Archivo JSON de salida")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging DEBUG")
    return parser.parse_args()

args = parse_args()
if args.verbose:
    log.setLevel(logging.DEBUG)

# Override globals from CLI
DATA_DIR = args.data_dir
OUT_JSON = args.out_json

# Palabras repetidas que no distinguen productos entre tiendas.
_STOP = {"de", "la", "el", "del", "los", "las", "y", "con", "para", "en", "por", "x",
         "und", "un", "unid", "uds", "unidad", "unidades", "pack", "paq", "oferta", "promo"}

_UNITS = {"gr", "g", "kg", "ml", "lt", "l", "lb", "oz", "und", "unid", "caja", "huevo",
          "huevos", "pieza", "pza", "sobre", "bolsa", "botella", "lata", "jarra"}


# ================= utilidades =================

def _limpiar(texto):
    """Normaliza texto: minúsculas y sin acentos, para comparar."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower().strip()


def _precio_parse(texto):
    """Devuelve (monto, cantidad) desde '2.99 USD (x1)', 'B/. 3.37', '$15.60', etc."""
    if not texto:
        return None, None
    s = str(texto).strip()
    cantidad = 1
    m_qty = re.match(r"^\s*(\d+)\s*[xX]\s+", s)
    if m_qty:
        cantidad = int(m_qty.group(1))
        s = s[m_qty.end():]
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m:
        return None, None
    s = m.group(1).replace(",", ".")
    try:
        return float(s) / cantidad, cantidad
    except ValueError:
        return None, None


def _clave_producto(nombre):
    """Clave de agrupación para comparar el mismo producto entre tiendas."""
    t = _limpiar(nombre)
    # NO dividir por dígitos: "Leche 1L" y "Leche 2L" deben seguir siendo comparables
    # Separar solo por paréntesis, comas, barras, guiones
    partes = re.split(r"[()]|,|/|\-", t)
    palabras = []
    for p in partes:
        for w in p.split():
            if w and w not in _STOP and w not in _UNITS:
                palabras.append(w)
    return " ".join(palabras)


def _leer_csv(ruta):
    """Lee una CSV del scraper y devuelve lista de dicts. Tolera CSV sin cabecera."""
    filas = []
    if not os.path.exists(ruta):
        return filas
    with open(ruta, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r]
    if not rows:
        return filas
    if rows[0] and rows[0][0].strip() == "categoria":
        rows = rows[1:]
    cols = ["categoria", "nombre", "precio_oferta", "precio_regular", "enlace"]
    for r in rows:
        filas.append(dict(zip(cols, (r + [""] * len(cols))[:len(cols)])))
    return filas


# ================= construccion =================

def _cargar():
    """Carga todos los productos de todas las tiendas."""
    productos = []
    archivos_encontrados = 0
    for archivo, nombre in SUPERMERCADOS:
        ruta = os.path.join(DATA_DIR, archivo)
        if not os.path.exists(ruta):
            log.warning("CSV no encontrado: %s", ruta)
            continue
        archivos_encontrados += 1
        for row in _leer_csv(ruta):
            oferta, _ = _precio_parse(row.get("precio_oferta"))
            regular, _ = _precio_parse(row.get("precio_regular"))
            if oferta is None:
                continue
            productos.append({
                "supermercado": nombre,
                "categoria": (row.get("categoria") or "").strip(),
                "nombre": (row.get("nombre") or "").strip(),
                "enlace": (row.get("enlace") or "").strip(),
                "precio_oferta": oferta,
                "precio_regular": regular if regular and regular > oferta else None,
            })
    if archivos_encontrados == 0:
        log.error("No se encontraron CSVs en %s. Ejecuta primero scraper_super.py", DATA_DIR)
    else:
        log.info("CSVs cargados: %d/%d", archivos_encontrados, len(SUPERMERCADOS))
    return productos


def _descuento_pct(oferta, regular):
    if not regular or regular <= oferta:
        return 0.0
    return round((regular - oferta) / regular * 100, 1)


def _distilar(productos):
    # ---- Top promociones: oferta < regular (descuento real) ----
    promos = []
    for p in productos:
        pct = _descuento_pct(p["precio_oferta"], p["precio_regular"])
        if pct <= 0:
            continue
        promos.append({
            "supermercado": p["supermercado"],
            "categoria": p["categoria"],
            "nombre": p["nombre"],
            "precio_oferta": round(p["precio_oferta"], 2),
            "precio_regular": round(p["precio_regular"], 2),
            "descuento_pct": pct,
            "enlace": p["enlace"],
            "razon": (f"{pct:.1f}% de descuento real (de B/.{p['precio_regular']:.2f} "
                      f"a B/.{p['precio_oferta']:.2f})"),
        })
    # Filtrar descuentos sospechosos (>90% suele ser dato roto)
    promos = [x for x in promos if x["descuento_pct"] <= 90]
    promos.sort(key=lambda x: (x["descuento_pct"], x["precio_oferta"]), reverse=True)
    for i, p in enumerate(promos, 1):
        p["rank"] = i
    top = promos[:50]

    # ---- Comparativas: misma clave en varias tiendas ----
    agrup = defaultdict(list)
    for p in productos:
        clave = _clave_producto(p["nombre"])
        if len(clave) < 4:
            continue
        agrup[clave].append(p)
    comparativas = []
    for clave, lista in agrup.items():
        tiendas = {p["supermercado"]: p["precio_oferta"] for p in lista}
        if len(tiendas) < 2:
            continue
        ganador = min(tiendas, key=tiendas.get)
        mejor = tiendas[ganador]
        segundos = sorted(tiendas.values())
        ahorro = round(segundos[1] - mejor, 2) if len(segundos) > 1 else 0.0
        representante = next(p for p in lista if p["supermercado"] == ganador)
        comparativas.append({
            "producto": representante["nombre"],
            "categoria": representante["categoria"],
            "precios": {k: round(v, 2) for k, v in tiendas.items()},
            "ganador": ganador,
            "ahorro": ahorro,
            "enlace": representante["enlace"],
        })
    comparativas.sort(key=lambda x: x["ahorro"], reverse=True)
    comparativas = comparativas[:50]

    # ---- Estadísticas por tienda ----
    stats = []
    for _, nombre in SUPERMERCADOS:
        tienda = [p for p in productos if p["supermercado"] == nombre]
        con_oferta = [p for p in tienda if p["precio_regular"]]
        descs = [_descuento_pct(p["precio_oferta"], p["precio_regular"]) for p in con_oferta]
        stats.append({
            "supermercado": nombre,
            "productos": len(tienda),
            "con_oferta": len(con_oferta),
            "promedio_descuento": round(sum(descs) / len(descs), 1) if descs else 0.0,
        })

    # ---- Mejor supermercado (heurística) ----
    mejor = None
    if stats:
        def score(s):
            return (s["con_oferta"] + 1) * (s["promedio_descuento"] or 1)
        m = max(stats, key=score)
        mejor = {
            "nombre": m["supermercado"],
            "promedio_descuento": m["promedio_descuento"],
            "total_ofertas": m["con_oferta"],
            "razon": (f"{m['supermercado']} tiene el mejor equilibrio: "
                      f"{m['con_oferta']} productos en oferta con un promedio "
                      f"de {m['promedio_descuento']:.1f}% de descuento."),
        }

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "totales": {
            "productos": len(productos),
            "con_oferta": sum(1 for p in productos if p["precio_regular"]),
        },
        "mejor_supermercado": mejor,
        "top_promociones": top,
        "comparativas": comparativas,
        "estadisticas_por_tienda": stats,
    }


def main():
    log.info("Cargando datos crudos desde %s", DATA_DIR)
    productos = _cargar()
    log.info("%d productos cargados", len(productos))
    destilado = _distilar(productos)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(destilado, f, ensure_ascii=False, indent=2)
    log.info("JSON generado -> %s", OUT_JSON)


if __name__ == "__main__":
    main()