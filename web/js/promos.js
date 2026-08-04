// promos.js — top promociones con filtros

function llenarFiltros(data) {
  const sup = new Set(), cat = new Set();
  (data.top_promociones || []).forEach((p) => { sup.add(p.supermercado); cat.add(p.categoria); });
  const selS = $("#filtro-super"), selC = $("#filtro-cat");
  selS.innerHTML = `<option value="">Todos los supermercados</option>` +
    [...sup].sort().map((s) => `<option>${esc(s)}</option>`).join("");
  selC.innerHTML = `<option value="">Todas las categorías</option>` +
    [...cat].sort().map((s) => `<option>${esc(s)}</option>`).join("");
}

function renderPromos(data) {
  const busq = $("#busqueda").value.trim().toLowerCase();
  const superF = $("#filtro-super").value;
  const catF = $("#filtro-cat").value;
  const lista = (data.top_promociones || []).filter((p) =>
    (!busq || (p.nombre || "").toLowerCase().includes(busq)) &&
    (!superF || p.supermercado === superF) &&
    (!catF || p.categoria === catF)
  );
  $("#vacio").style.display = lista.length ? "none" : "block";
  const grid = $("#promo-grid");
  grid.innerHTML = lista.map((p) => {
    const rankCls = p.rank === 1 ? "r1" : p.rank === 2 ? "r2" : p.rank === 3 ? "r3" : "";
    const badge = p.descuento_pct >= 40 ? `badge big` : "badge";
    return `
      <article class="promo-card">
        <div class="promo-top">
          <div class="promo-rank ${rankCls}">${p.rank}</div>
          <div>
            <div class="promo-nombre">${esc(p.nombre)}</div>
            <div class="promo-cat">${esc(p.supermercado)} · ${esc(p.categoria)}</div>
          </div>
        </div>
        <div class="promo-desc">🤖 ${esc(p.razon)}</div>
        <div class="promo-precios">
          <span class="promo-oferta">B/. ${fmtNum(p.precio_oferta)}</span>
          <span class="promo-regular">B/. ${fmtNum(p.precio_regular)}</span>
          <span class="promo-badge ${badge}">-${p.descuento_pct.toFixed(0)}%</span>
        </div>
        <a class="promo-enlace" href="${esc(p.enlace)}" target="_blank" rel="noopener">Ver oferta →</a>
      </article>`;
  }).join("");
}

function initPromos() {
  $("#busqueda").addEventListener("input", () => renderPromos(window.DATA));
  $("#filtro-super").addEventListener("change", () => renderPromos(window.DATA));
  $("#filtro-cat").addEventListener("change", () => renderPromos(window.DATA));
}
