// Dashboard estático: lee web/data.json (generado por ai_engine.py) y lo renderiza.
// No requiere backend: funciona en GitHub Pages sin API keys.

const $ = (sel) => document.querySelector(sel);

let DATA = null;

async function cargarDatos() {
  const rutas = ["data.json", "./data.json"];
  for (const r of rutas) {
    try {
      const res = await fetch(r, { cache: "no-store" });
      if (res.ok) {
        const d = await res.json();
        if (d && d.generated_at) return d;
      }
    } catch (_) { /* probar siguiente */ }
  }
  throw new Error("No se pudo cargar data.json");
}

function fmtFecha(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-PA", { dateStyle: "long", timeStyle: "short" });
  } catch (_) { return iso; }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderGanador() {
  const m = DATA.mejor_supermercado;
  if (!m) { $("#ganador-section").hidden = true; return; }
  $("#ganador-section").hidden = false;
  $("#champ-name").textContent = m.nombre;
  $("#champ-meta").textContent = `${m.total_ofertas} ofertas · ${m.promedio_descuento}% promedio`;
  $("#champ-reason").textContent = m.razon;
}

function llenarFiltros() {
  const sup = new Set(), cat = new Set();
  DATA.top_promociones.forEach((p) => { sup.add(p.supermercado); cat.add(p.categoria); });
  const selS = $("#filtro-super"), selC = $("#filtro-cat");
  selS.innerHTML = `<option value="">Todos los supermercados</option>` +
    [...sup].sort().map((s) => `<option>${esc(s)}</option>`).join("");
  selC.innerHTML = `<option value="">Todas las categorías</option>` +
    [...cat].sort().map((s) => `<option>${esc(s)}</option>`).join("");
}

function renderPromos() {
  const busq = $("#busqueda").value.trim().toLowerCase();
  const superF = $("#filtro-super").value;
  const catF = $("#filtro-cat").value;
  const lista = DATA.top_promociones.filter((p) =>
    (!busq || p.nombre.toLowerCase().includes(busq)) &&
    (!superF || p.supermercado === superF) &&
    (!catF || p.categoria === catF)
  );
  $("#vacio").style.display = lista.length ? "none" : "block";
  $("#top-list").innerHTML = lista.map((p) => `
    <li>
      <div class="rank">${p.rank}</div>
      <div class="p-info">
        <h3>${esc(p.nombre)}</h3>
        <div class="cat">${esc(p.supermercado)} · ${esc(p.categoria)}</div>
        <div class="reason">🤖 ${esc(p.razon)}</div>
      </div>
      <div class="p-precios">
        <div class="oferta">B/. ${p.precio_oferta.toFixed(2)}</div>
        <div class="regular">B/. ${p.precio_regular.toFixed(2)}</div>
        <div class="badge">-${p.descuento_pct.toFixed(0)}%</div>
        <br><a class="compra" href="${esc(p.enlace)}" target="_blank" rel="noopener">Ver oferta →</a>
      </div>
    </li>`).join("");
}

function renderComparativas() {
  const tbody = $("#cmp-body");
  $("#cmp-vacio").style.display = DATA.comparativas.length ? "none" : "block";
  tbody.innerHTML = DATA.comparativas.map((c) => {
    const precios = Object.entries(c.precios)
      .map(([s, v]) => `${s}: <b>B/. ${v.toFixed(2)}</b>`).join(" · ");
    return `<tr>
      <td>${esc(c.producto)}<br><span class="cat" style="font-size:12px;color:var(--muted)">${esc(c.categoria)}</span></td>
      <td class="ganador">${esc(c.ganador)}</td>
      <td class="ahorro">B/. ${c.ahorro.toFixed(2)}</td>
      <td class="precios">${precios}</td>
    </tr>`;
  }).join("");
}

function init() {
  $("#busqueda").addEventListener("input", renderPromos);
  $("#filtro-super").addEventListener("change", renderPromos);
  $("#filtro-cat").addEventListener("change", renderPromos);
}

(async function main() {
  init();
  try {
    DATA = await cargarDatos();
    $("#updated").textContent = "Última actualización: " + fmtFecha(DATA.generated_at) + " (se refresca 2 veces al día)";
    renderGanador();
    llenarFiltros();
    renderPromos();
    renderComparativas();
  } catch (e) {
    $("#updated").textContent = "No hay datos todavía. Ejecuta 'python ai_engine.py' y súbelos a GitHub Pages.";
    $("#top-list").innerHTML = `<li style="grid-template-columns:1fr"><div>${esc(e.message)}</div></li>`;
  }
})();