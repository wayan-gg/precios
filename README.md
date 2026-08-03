# Supermercados Panamá – Promociones Inteligentes

Pipeline 100% **gratis** (sin APIs pagas) para encontrar las **mejores promociones** en 5 supermercados de Panamá. Se ejecuta 2×/día en GitHub Actions y publica un dashboard estático en **GitHub Pages**.

---

## 🎯 Qué hace

| Componente | Qué produce |
|------------|-------------|
| `scraper_super.py` | 5 CSV en `data/` con **todos los productos** (nombre, precio_oferta, precio_regular, enlace, categoría) |
| `ai_engine.py` | Un solo JSON `web/data.json` destilado: **mejor supermercado**, **top 50 promociones**, **comparativas multi-tienda**, estadísticas |
| `web/` | Dashboard estático (HTML/CSS/JS) que lee `data.json` → funciona en GitHub Pages sin backend |

---

## 📦 Supermercados soportados

| Supermercado | Tecnología | Estado |
|--------------|------------|--------|
| Riba Smith | HTML estático (requests + BS4) | ✅ |
| Super 99 | JS + paginación por clic (Selenium) | ✅ |
| El Rey | JS + data-testid (Selenium) | ✅ |
| El Machetazo | API VTEX pública (requests) | ✅ |
| Super Xtra | API VTEX pública (requests) | ✅ |

> **El Fuerte** quedó fuera: bloqueado por Cloudflare Turnstile (no hay bypass gratis sin interacción humana).

---

## 🔄 Flujo automático (GitHub Actions)

1. **Cron**: 06:00 y 18:00 UTC (`cron: "0 6,18 * * *"`)
2. **Ejecuta**:
   - `python scraper_super.py`  → escribe 5 CSV en `data/`
   - `python ai_engine.py`       → genera `web/data.json`
3. **Commit & push** de `data/` y `web/data.json`
4. **Deploy** a GitHub Pages (gratis, estático)

El dashboard se actualiza **2 veces al día** sin intervención manual.

---

## 📂 Estructura del repo

```
scraper/
├── scraper_super.py      # Scraper unificado (5 tiendas)
├── ai_engine.py          # "IA" heurística → web/data.json
├── data/                 # CSVs crudos (base de datos)
│   ├── riba_smith.csv
│   ├── super99.csv
│   ├── elrey.csv
│   ├── machetazo.csv
│   └── superxtra.csv
├── web/                  # Sitio estático (GitHub Pages root)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── data.json         # ← Generado por ai_engine.py
├── .github/workflows/
│   └── scrape.yml        # Cron 2×/día + Pages deploy
└── README.md
```

---

## ⚙️ Configuración rápida

### 1. Variables del scraper (`scraper_super.py`)

```python
MAX_PAGES = None          # None = todas las páginas por categoría
MAX_CATEGORIES = None     # None = todas las categorías
DATA_DIR = "data"         # Carpeta de salida CSVs
```

### 2. GitHub Pages

1. Repo → **Settings** → **Pages** → Source: **GitHub Actions**
2. El workflow ya usa `actions/deploy-pages@v4`
3. Primera ejecución manual: **Actions → Scrape y publicar promociones → Run workflow**

### 3. Ejecución local (opcional)

```bash
pip install requests beautifulsoup4 selenium webdriver-manager
python scraper_super.py       # → data/*.csv  (tarda ~15–30 min)
python ai_engine.py           # → web/data.json
# Servir web local:
python -m http.server -d web 8000
# Abrir http://localhost:8000
```

> **Selenium** necesita Chrome instalado localmente. En Windows: `winget install Google.Chrome`. En GitHub Actions el workflow ya lo instala.

---

## 🧠 La "IA" — sin APIs, gratis, local

`ai_engine.py` aplica **reglas determinísticas**:

1. **Normaliza precios**: parsea formatos (`B/. 3.37`, `$15.60`, `2 X B/. 4.55`) → `(monto, cantidad)`
2. **Detecta descuento real**: `oferta < regular` → `descuento_pct = (regular - oferta) / regular`
3. **Top promociones**: ordena por `descuento_pct` (filtra > 90% como datos rotos)
4. **Comparativas**: agrupa por **clave normalizada** (quita acentos, stop-words, unidades, números) → encuentra mismo producto en ≥2 tiendas
5. **Mejor supermercado**: score = `(#ofertas + 1) × (promedio_descuento + 1)`
6. **Razones textuales**: plantillas generadas ("33.6% de descuento real (de B/.4.50 a B/.2.99)")

Sin LLM, sin claves, **cero coste**. Si quieres LLM real, añade una llamada a API en `ai_engine.py` (fuera de scope "gratis").

---

## 📊 Formato de `web/data.json` (la "base de datos")

```jsonc
{
  "generated_at": "2026-08-03T20:50:12.677067+00:00",
  "totales": { "productos": 17106, "con_oferta": 947 },
  "mejor_supermercado": {
    "nombre": "Riba Smith",
    "promedio_descuento": 27.2,
    "total_ofertas": 124,
    "razon": "Riba Smith tiene el mejor equilibrio: 124 productos en oferta con un promedio de 27.2% de descuento."
  },
  "top_promociones": [
    { "rank": 1, "supermercado": "Riba Smith", "categoria": "Lácteos",
      "nombre": "Leche Entera 1L", "precio_oferta": 1.20, "precio_regular": 1.65,
      "descuento_pct": 27.3, "enlace": "https://...", "razon": "27.3% de descuento real..." }
  ],
  "comparativas": [
    { "producto": "Huevos Cariño 30un", "categoria": "Lácteos",
      "precios": { "Riba Smith": 5.40, "Super 99": 5.65 }, "ganador": "Riba Smith",
      "ahorro": 0.25, "enlace": "https://..." }
  ],
  "estadisticas_por_tienda": [
    { "supermercado": "Riba Smith", "productos": 2046, "con_oferta": 124, "promedio_descuento": 27.2 },
    { "supermercado": "Super 99", "productos": 15060, "con_oferta": 823, "promedio_descuento": 18.0 }
  ]
}
```

---

## 🛠️ Personalización

| Qué cambiar | Dónde |
|-------------|-------|
| Categorías por tienda | `scraper_super.py` → listas `*_CATEGORIES` |
| Límite páginas/categorías | `MAX_PAGES`, `MAX_CATEGORIES` |
| Scoring "mejor super" | `ai_engine.py` → `score(s)` |
| Umbral descuento top | `ai_engine.py` → filtro `descuento_pct <= 90` |
| Estilos dashboard | `web/style.css` |

---

## 📝 Licencia

MIT — úsalo, modifícalo, compártelo. Si mejora tus compras, ¡cuéntame!

---

> **Nota**: Los precios y disponibilidad cambian; el dashboard refleja el último scrape (2×/día). Verifica en el enlace antes de comprar.