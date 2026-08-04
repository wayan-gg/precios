# -*- coding: utf-8 -*-
"""
IA Smart: canasta básica, análisis de imagen y chat con LLM (NVIDIA, gratis).

Lee los productos crudos (data/*.csv) y el data.json ya destilado y produce un
único JSON (web/data_smart.json) que combina:

1. INFORMACIÓN DE TODO: resumen del data.json (totales, mejor supermercado,
   top promociones, comparativas, estadísticas por tienda).
2. CANASTA BÁSICA por supermercado: cuánto cuesta comprar la misma canasta en
   cada tienda, cuál es la más barata y cuánto ahorras.
3. ANÁLISIS DE IMAGEN (opcional --imagen): manda una foto (volante/lista) a un
   modelo de visión de NVIDIA, extrae productos y precios, y los compara con lo
   que cobra cada supermercado.
4. CHAT (opcional --chat): envía todo el data.json a un LLM y recibe una
   respuesta en JSON.

Sin API_KEY, los modos 1 y 2 funcionan igual (100% gratis). Los modos 3 y
4 requieren la clave (gratuita de build.nvidia.com) y el paquete `openai`.
"""
import argparse
import base64
import json
import logging
import os
import re
import shutil
import sys
import unicodedata

try:
    from ai_engine import _cargar, SUPERMERCADOS, DATA_DIR
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ai_engine import _cargar, SUPERMERCADOS, DATA_DIR

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

# ================= CONFIG =================
DATA_JSON = os.path.join("web", "data.json")
OUT_JSON = os.path.join("web", "data_smart.json")
OUT_LLM = os.path.join("web", "data_llm.json")
UPLOADS_DIR = os.path.join("web", "uploads")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_VISION = "meta/llama-3.2-90b-vision-instruct"
MODEL_CHAT = "nvidia/nemotron-3-ultra-550b-a55b"
MAX_TOKENS = 4096

# ================= CANASTA BÁSICA =================
# Cada ítem: nombre descriptivo + palabras clave (regex con límites de palabra).
# Se elige el producto con mejor puntaje y, entre empates, el más barato.
CANASTA = [
    {"nombre": "Arroz",           "claves": ["arroz"]},
    {"nombre": "Aceite vegetal",  "claves": ["aceite", "aceite vegetal", "oleico"]},
    {"nombre": "Azúcar",          "claves": ["azucar"]},
    {"nombre": "Huevos",          "claves": ["huevos", "huevo"]},
    {"nombre": "Leche",           "claves": ["leche"]},
    {"nombre": "Pan",             "claves": ["pan blanco", "pan de molde", "pan sandwich", "pan tostado", "panes"]},
    {"nombre": "Café",            "claves": ["cafe", "nescafe"]},
    {"nombre": "Frijoles",        "claves": ["frijol", "frijoles", "habichuela"]},
    {"nombre": "Harina",          "claves": ["harina"]},
    {"nombre": "Sal",             "claves": ["sal"]},
    {"nombre": "Atún",            "claves": ["atun", "atun en lata", "tuna"]},
    {"nombre": "Pollo",           "claves": ["pollo"]},
    {"nombre": "Carne de res",    "claves": ["carne"]},
    {"nombre": "Queso",           "claves": ["queso"]},
    {"nombre": "Pasta",           "claves": ["pasta", "fideos", "espaguetis", "spaghetti", "macarrones"]},
    {"nombre": "Tomate",          "claves": ["tomate"]},
    {"nombre": "Cebolla",         "claves": ["cebolla"]},
    {"nombre": "Plátanos",        "claves": ["platano", "bananos"]},
    {"nombre": "Jabón",           "claves": ["jabon", "jabon de baño", "jabon de manos"]},
    {"nombre": "Detergente",      "claves": ["detergente", "jabon en polvo", "fabuloso"]},
]


def _norm(texto):
    """Normaliza texto (minúsculas, sin acentos) para comparar."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower().strip()


def _puntaje(claves, nombre):
    """Cuenta cuántas claves del ítem aparecen en el nombre (límite de palabra).
    Las frases de varias palabras pesan más (son más específicas)."""
    n = _norm(nombre)
    total = 0
    for kw in claves:
        patron = r"\b" + re.escape(_norm(kw)) + r"\b"
        if re.search(patron, n):
            total += len(kw.split())
    return total


# Palabras que indican producto procesado/compuesto (no el ítem genérico).
_PREPARADO = [
    "empanada", "sopa", "tortilla", "arepa", "cereal", "preparado", "instantaneo",
    "mezcla", "crema", "sazon", "mantequilla", "margarina", "sardina", "atun",
    "tuna", "salchicha", "chorizo", "jamon", "dentifrica", "cartulina", "galleta",
    "chocolate", "panqueque", "pancake", "adobo", "pique", "caldo", "pure",
    "papilla", "ensalada", "guiso", "estofado", "brocheta", "medallon", "albondiga",
    "hamburguesa", "nuggets", "croqueta", "ravioli", "lasagna", "burrito", "wrap",
    "sandwich", "patty", "croqueta",
]


def _claves_de_otros_items(item, claves_por_item):
    """Conjunto de claves de TODOS los otros ítems de la canasta (para penalizar)."""
    return set(kw for other, kws in claves_por_item.items() for kw in kws if other is not item)


def _mejor_producto_por_tienda(productos, item, claves_por_item):
    """Devuelve el producto con mejor puntaje (más barato si empata) o None.
    Prioriza productos genéricos: castiga nombres compuestos, largos y ambiguos."""
    otras_claves = _claves_de_otros_items(item, claves_por_item)
    mejor = None
    mejor_score = float("-inf")
    for p in productos:
        nombre_norm = _norm(p["nombre"])
        score = 0
        for kw in item["claves"]:
            if re.search(r"\b" + re.escape(_norm(kw)) + r"\b", nombre_norm):
                score += len(kw.split())
        if score < 1:
            continue
        # Producto procesado/compuesto: casi nunca es el ítem genérico.
        for pw in _PREPARADO:
            if re.search(r"\b" + re.escape(pw) + r"\b", nombre_norm):
                score -= 5
                break
        # Contiene claves de OTROS ítems de la canasta -> ambiguo.
        for okw in otras_claves:
            if re.search(r"\b" + re.escape(_norm(okw)) + r"\b", nombre_norm):
                score -= 2
        # Nombres largos = más ruido = menos específico.
        score -= 0.5 * len(nombre_norm.split())
        precio = p["precio_oferta"] or 0
        if score > mejor_score or (score == mejor_score and mejor and precio < mejor["precio_oferta"]):
            mejor = {
                "producto": p["nombre"],
                "precio_oferta": round(precio, 2),
                "enlace": p["enlace"],
            }
            mejor_score = score
    return mejor


def _canasta_basica(productos):
    """Compara la canasta básica en cada supermercado."""
    claves_por_item = {item["nombre"]: item["claves"] for item in CANASTA}
    por_tienda = {nombre: [] for _, nombre in SUPERMERCADOS}
    for _, nombre in SUPERMERCADOS:
        tienda = [p for p in productos if p["supermercado"] == nombre]
        for item in CANASTA:
            match = _mejor_producto_por_tienda(tienda, item, claves_por_item)
            por_tienda[nombre].append({
                "item": item["nombre"],
                "encontrado": bool(match),
                "producto": match["producto"] if match else None,
                "precio": match["precio_oferta"] if match else None,
                "enlace": match["enlace"] if match else None,
            })

    # Totales por tienda (solo ítems encontrados)
    totales = []
    for _, nombre in SUPERMERCADOS:
        items = por_tienda[nombre]
        encontrados = [i for i in items if i["encontrado"]]
        total = round(sum(i["precio"] for i in encontrados), 2)
        totales.append({
            "supermercado": nombre,
            "items_encontrados": len(encontrados),
            "items_totales": len(items),
            "total": total,
        })

    # Ranking: tienda más barata y cuánto se ahorra
    con_datos = [t for t in totales if t["items_encontrados"] > 0]
    ranking = sorted(con_datos, key=lambda t: t["total"])
    resultado = {
        "item_por_tienda": por_tienda,
        "totales_por_tienda": totales,
        "ranking": ranking,
    }
    if ranking:
        mas_barato = ranking[0]
        mas_caro = ranking[-1]
        resultado["mejor_tienda_canasta"] = {
            "supermercado": mas_barato["supermercado"],
            "total": mas_barato["total"],
            "ahorro_vs_mas_cara": round(mas_caro["total"] - mas_barato["total"], 2),
            "ahorro_pct": round((mas_caro["total"] - mas_barato["total"]) / mas_caro["total"] * 100, 1)
            if mas_caro["total"] else 0.0,
            "razon": (f"La canasta más barata es {mas_barato['supermercado']} con B/.{mas_barato['total']:.2f}; "
                      f"ahorras B/.{mas_caro['total'] - mas_barato['total']:.2f} "
                      f"({round((mas_caro['total'] - mas_barato['total']) / mas_caro['total'] * 100, 1)}%) "
                      f"respecto a {mas_caro['supermercado']}."),
        }
    return resultado


# ================= RESUMEN DE TODO (data.json) =================

def _resumen_datos():
    """Lee web/data.json y arma un resumen compacto para LLM y JSON."""
    if not os.path.exists(DATA_JSON):
        log.warning("No existe %s. Ejecuta primero ai_engine.py", DATA_JSON)
        return {}
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        d = json.load(f)
    return {
        "generated_at": d.get("generated_at"),
        "totales": d.get("totales"),
        "mejor_supermercado": d.get("mejor_supermercado"),
        "top_promociones": d.get("top_promociones", [])[:50],
        "comparativas": d.get("comparativas", []),
        "estadisticas_por_tienda": d.get("estadisticas_por_tienda", []),
    }


# ================= LLM (NVIDIA, OpenAI-compatible) =================

def _cliente(api_key):
    from openai import OpenAI
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)


def _extraer_json(texto):
    """Saca el primer bloque JSON de una respuesta (tolera markdown)."""
    if not texto:
        return None
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    if m:
        texto = m.group(1).strip()
    try:
        return json.loads(texto)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", texto, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    return None


def _imagen_a_base64(ruta_o_url):
    """Devuelve (tipo_uri, dato) para la imagen. Soporta archivo local o URL."""
    if re.match(r"^https?://", ruta_o_url):
        return "url", ruta_o_url
    if not os.path.exists(ruta_o_url):
        return None, None
    with open(ruta_o_url, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = os.path.splitext(ruta_o_url)[1].lower().lstrip(".")
    if ext not in ("jpg", "jpeg", "png"):
        ext = "jpeg"
    return "b64", f"data:image/{ext};base64,{b64}"


def _guardar_imagen(ruta_o_url):
    """Copia la imagen local a web/uploads/ para mostrarla en el dashboard."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    if re.match(r"^https?://", ruta_o_url):
        return ruta_o_url
    if not os.path.exists(ruta_o_url):
        return None
    nombre = os.path.basename(ruta_o_url)
    destino = os.path.join(UPLOADS_DIR, nombre)
    try:
        shutil.copyfile(ruta_o_url, destino)
    except Exception as e:
        log.warning("No se pudo copiar la imagen: %s", e)
        return ruta_o_url
    return "uploads/" + nombre


def _analizar_imagen(ruta_o_url, api_key, productos):
    """Extrae productos y precios de la imagen con el modelo de visión."""
    tipo, dato = _imagen_a_base64(ruta_o_url)
    if not dato:
        log.error("Imagen no válida: %s", ruta_o_url)
        return {"error": "imagen no válida"}

    content = [{"type": "text", "text": (
        "Eres un lector de volantes de supermercados de Panamá. "
        "Extrae TODOS los productos visibles con su precio en balboas (B/. o $). "
        "Devuelve ÚNICAMENTE un JSON con esta forma exacta: "
        '{"productos": [{"nombre": "NOMBRE", "precio": 1.23}]}. '
        "No agregues texto ni markdown. Si un precio está como '2 X B/.4.55' usa el precio unitario."
    )}]
    content.append({"type": "image_url", "image_url": {"url": dato}})

    client = _cliente(api_key)
    try:
        resp = client.chat.completions.create(
            model=MODEL_VISION,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=MAX_TOKENS,
        )
    except Exception as e:
        log.error("Error llamando a la API de visión: %s", e)
        return {"error": str(e)}

    texto = resp.choices[0].message.content or ""
    data = _extraer_json(texto)
    if not data or "productos" not in data:
        log.warning("Respuesta sin JSON parseable: %s", texto[:300])
        return {"raw": texto, "error": "respuesta sin JSON parseable"}

    return {
        "imagen": _guardar_imagen(ruta_o_url),
        "productos_imagen": data["productos"],
        "comparacion": _comparar_con_tiendas(data["productos"], productos),
    }


def _comparar_con_tiendas(productos_imagen, productos, top=3):
    """Para cada producto de la imagen, encuentra el precio en cada tienda."""
    resultados = []
    for item in productos_imagen:
        nombre_img = item.get("nombre", "")
        precio_img = item.get("precio")
        matches = {}
        for _, nombre in SUPERMERCADOS:
            tienda = [p for p in productos if p["supermercado"] == nombre]
            mejor = None
            mejor_score = 0
            for p in tienda:
                score = _puntaje([nombre_img], p["nombre"])
                if score >= 1 and score > mejor_score:
                    mejor = p
                    mejor_score = score
            if mejor:
                matches[nombre] = round(mejor["precio_oferta"], 2)
        if matches:
            ganador = min(matches, key=matches.get)
            ahorro = None
            if isinstance(precio_img, (int, float)) and precio_img:
                ahorro = round(precio_img - matches[ganador], 2)
            resultados.append({
                "producto_imagen": nombre_img,
                "precio_imagen": round(precio_img, 2) if isinstance(precio_img, (int, float)) else precio_img,
                "precios_tiendas": matches,
                "tienda_mas_barata": ganador,
                "ahorro_en_tienda": ahorro,
            })
    resultados.sort(key=lambda x: (x.get("ahorro_en_tienda") is None, -(x.get("ahorro_en_tienda") or 0)))
    return resultados[:top]


def _chat(pregunta, resumen, api_key):
    """Envía todo el data.json + canasta a un LLM y devuelve una respuesta JSON."""
    contexto = {
        "informacion_todo": resumen,
        "pregunta": pregunta,
    }
    client = _cliente(api_key)
    try:
        resp = client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[
                {"role": "system", "content": (
                    "Eres un asistente de comparación de precios de supermercados de Panamá. "
                    "Recibes datos JSON de todos los supermercados. "
                    "Responde SIEMPRE con un JSON válido con esta forma: "
                    '{"respuesta": "texto claro en español", "recomendacion": "tienda o consejo", '
                    '"detalles": ["lista", "de", "datos"]}. No uses markdown."'
                )},
                {"role": "user", "content": json.dumps(contexto, ensure_ascii=False)},
            ],
            temperature=0.3,
            max_tokens=MAX_TOKENS,
        )
    except Exception as e:
        log.error("Error llamando al chat: %s", e)
        return {"error": str(e)}

    texto = resp.choices[0].message.content or ""
    data = _extraer_json(texto)
    if data:
        return data
    return {"raw": texto}


# Prompt fijo y concreto para el modo "distill": la IA genera el análisis final.
PROMPT_DISTIL = (
    "Eres el analista jefe de precios de supermercados de Panamá. "
    "Recibes el siguiente contexto en JSON: toda la información destilada de las tiendas "
    "(totales, mejor supermercado, top promociones, comparativas, estadísticas) y el "
    "resultado de la canasta básica por supermercado.\n\n"
    "Tu tarea es producir UN análisis final. Responde ÚNICAMENTE con un JSON válido, "
    "sin markdown ni texto adicional, con EXACTAMENTE esta estructura:\n"
    "{\n"
    '  "resumen": "párrafo breve de 2-3 frases con el panorama general",\n'
    '  "mejor_supermercado": {"nombre": "tienda", "razon": "explica por qué en 1-2 frases"},'
    "\n"
    '  "mejores_promociones": [{"nombre": "producto", "supermercado": "tienda", '
    '"precio": 1.23, "precio_regular": 2.5, "descuento_pct": 50.8, "razon": "por qué es buena"},'
    " ... hasta 15 items del top],\n"
    '  "canasta_recomendada": {"supermercado": "tienda", "total": 28.66, "ahorro": 10.14, '
    '"razon": "por qué conviene"},'
    "\n"
    '  "insights": ["3 a 5 observaciones concretas en texto, con números cuando sea posible"]\n'
    "}\n\n"
    "Reglas: usa SOLO los datos del contexto (no inventes precios); "
    "el descuento_pct se calcula como (regular - precio)/regular*100; "
    "escribe siempre en español; precios en balboas (B/.)."
)


def _distill_llm(contexto, api_key):
    """Envía el contexto completo (resumen + canasta) al LLM con el prompt fijo."""
    client = _cliente(api_key)
    try:
        resp = client.chat.completions.create(
            model=MODEL_CHAT,
            messages=[
                {"role": "system", "content": PROMPT_DISTIL},
                {"role": "user", "content": json.dumps(contexto, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=MAX_TOKENS,
        )
    except Exception as e:
        log.error("Error llamando al distill: %s", e)
        return {"error": str(e)}

    texto = resp.choices[0].message.content or ""
    data = _extraer_json(texto)
    if data:
        return data
    return {"raw": texto}


# ================= MAIN =================

def parse_args():
    parser = argparse.ArgumentParser(description="IA Smart: canasta básica, imagen y chat")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Directorio con CSVs crudos")
    parser.add_argument("--data-json", default=DATA_JSON, help="data.json ya destilado")
    parser.add_argument("--out-json", default=OUT_JSON, help="JSON de salida")
    parser.add_argument("--imagen", default=None, help="Ruta o URL de una imagen (volante) a analizar")
    parser.add_argument("--chat", default=None, help="Pregunta en lenguaje natural sobre los datos")
    parser.add_argument("--distill", action="store_true", help="Genera web/data_llm.json con el análisis del LLM (prompt fijo)")
    parser.add_argument("--out-llm", default=OUT_LLM, help="JSON de salida del modo distill")
    parser.add_argument("--model-chat", default=MODEL_CHAT, help="Modelo de chat")
    parser.add_argument("--model-vision", default=MODEL_VISION, help="Modelo de visión")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging DEBUG")
    return parser.parse_args()


def main():
    global DATA_DIR, DATA_JSON, OUT_JSON, OUT_LLM, MODEL_CHAT, MODEL_VISION
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)
    DATA_DIR = args.data_dir
    DATA_JSON = args.data_json
    OUT_JSON = args.out_json
    OUT_LLM = args.out_llm
    MODEL_CHAT = args.model_chat
    MODEL_VISION = args.model_vision

    api_key = os.environ.get("API_KEY")

    # --- Modo distill: solo pide al LLM el análisis final y lo guarda ---
    if args.distill:
        if not api_key:
            log.error("Se necesita API_KEY para el modo distill")
            return
        resumen = _resumen_datos()
        if not resumen:
            log.error("No hay data.json; ejecuta primero ai_engine.py")
            return
        log.info("Modo distill: enviando contexto al LLM (%s)...", MODEL_CHAT)
        respuesta = _distill_llm({"informacion_todo": resumen}, api_key)
        import datetime
        salida = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "origen": "LLM " + MODEL_CHAT,
            **respuesta,
        }
        os.makedirs(os.path.dirname(OUT_LLM), exist_ok=True)
        with open(OUT_LLM, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
        log.info("JSON distill generado -> %s", OUT_LLM)
        return

    log.info("Cargando productos crudos desde %s", DATA_DIR)
    productos = _cargar()
    log.info("%d productos cargados", len(productos))

    log.info("Construyendo canasta básica...")
    canasta = _canasta_basica(productos)

    log.info("Resumen de data.json...")
    resumen = _resumen_datos()

    output = {
        "generated_at": None,
        "informacion_todo": resumen,
        "canasta_basica": canasta,
    }

    if args.imagen:
        if not api_key:
            log.error("Se necesita API_KEY para analizar la imagen")
        else:
            log.info("Analizando imagen %s con %s...", args.imagen, MODEL_VISION)
            output["analisis_imagen"] = _analizar_imagen(args.imagen, api_key, productos)

    if args.chat:
        if not api_key:
            log.error("Se necesita API_KEY para el modo chat")
        else:
            log.info("Consultando chat...")
            output["chat"] = _chat(args.chat, resumen, api_key)

    import datetime
    output["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info("JSON generado -> %s", OUT_JSON)
    if canasta.get("mejor_tienda_canasta"):
        m = canasta["mejor_tienda_canasta"]
        log.info("Canasta: %s es la más barata (B/.%.2f, ahorro B/.%.2f)",
                 m["supermercado"], m["total"], m["ahorro_vs_mas_cara"])


if __name__ == "__main__":
    main()
