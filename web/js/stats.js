// stats.js — resumen general, mejor supermercado, estadísticas por tienda

function renderResumen(data) {
  const grid = $("#stats-grid");
  const t = data.totales || {};
  const cards = [
    { label: "Productos rastreados", value: (t.productos || 0).toLocaleString("es-PA"), sub: "en todas las tiendas", cls: "stat-accent" },
    { label: "Con oferta", value: (t.con_oferta || 0).toLocaleString("es-PA"), sub: "descuento real detectado", cls: "stat-green" },
  ];
  grid.innerHTML = cards.map((c) => `
    <div class="stat-card ${c.cls}">
      <div class="stat-label">${c.label}</div>
      <div class="stat-value">${c.value}</div>
      <div class="stat-sub">${c.sub}</div>
    </div>`).join("");
}

function renderMejor(data) {
  const m = data.mejor_supermercado;
  const sec = $("#mejor-section");
  if (!m) { sec.hidden = true; return; }
  sec.hidden = false;
  $("#champ-name").textContent = m.nombre;
  $("#champ-meta").textContent = `${m.total_ofertas} ofertas · ${m.promedio_descuento}% promedio`;
  $("#champ-razon").textContent = m.razon;
}

function renderEstadisticas(data) {
  const grid = $("#est-grid");
  const stats = data.estadisticas_por_tienda || [];
  const max = Math.max(...stats.map((s) => s.con_oferta), 1);
  grid.innerHTML = stats.map((s) => {
    const pct = s.productos ? Math.round((s.con_oferta / s.productos) * 100) : 0;
    const ancho = s.con_oferta ? Math.max(4, Math.round((s.con_oferta / max) * 100)) : 0;
    return `
      <div class="est-card">
        <div class="est-nombre">${esc(s.supermercado)}</div>
        <div class="est-tienda"><span>Productos</span><b>${s.productos.toLocaleString("es-PA")}</b></div>
        <div class="est-tienda"><span>Con oferta</span><b>${s.con_oferta.toLocaleString("es-PA")}</b></div>
        <div class="est-tienda"><span>% en oferta</span><b>${pct}%</b></div>
        <div class="est-tienda"><span>Descuento promedio</span><b>${s.promedio_descuento}%</b></div>
        <div class="est-bar"><span style="width:${ancho}%"></span></div>
      </div>`;
  }).join("");
}
