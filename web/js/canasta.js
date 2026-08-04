// canasta.js — canasta básica por supermercado (dato de la IA)

function renderCanastaBanner(cb) {
  const banner = $("#canasta-banner");
  const mejor = cb.mejor_tienda_canasta;
  if (!mejor) { banner.hidden = true; return; }
  banner.hidden = false;
  banner.innerHTML = `
    <div class="b-icon">🧺</div>
    <div>
      <div class="b-titulo">Canasta más barata</div>
      <div class="b-nombre">${esc(mejor.supermercado)}</div>
      <div class="b-razon">${esc(mejor.razon)}</div>
    </div>
    <div class="b-ahorro">
      <div class="b-ahorro-val">B/. ${fmtNum(mejor.total)}</div>
      <div class="b-ahorro-lab">ahorras B/. ${fmtNum(mejor.ahorro_vs_mas_cara)} (${fmtNum(mejor.ahorro_pct, 1)}%)</div>
    </div>`;
}

function renderCanastaBarras(cb) {
  const cont = $("#canasta-barras");
  const totales = cb.totales_por_tienda || [];
  const conDatos = totales.filter((t) => t.items_encontrados > 0);
  if (!conDatos.length) { cont.hidden = true; return; }
  cont.hidden = false;
  const max = Math.max(...conDatos.map((t) => t.total));
  const mejorNombre = (cb.mejor_tienda_canasta || {}).supermercado;
  cont.innerHTML = conDatos.map((t) => {
    const pct = max ? Math.round((t.total / max) * 100) : 0;
    const cls = t.supermercado === mejorNombre ? "bar-mejor" : "";
    const sinDatos = t.items_encontrados < t.items_totales;
    return `
      <div class="canasta-bar ${cls}">
        <div class="bar-nombre">${esc(t.supermercado)} ${t.supermercado === mejorNombre ? "🏆" : ""}</div>
        <div class="bar-total">B/. ${fmtNum(t.total)}</div>
        <div class="bar-meta">${t.items_encontrados}/${t.items_totales} productos${sinDatos ? " (incompleto)" : ""}</div>
        <div class="bar-pista"><span style="width:${pct}%"></span></div>
      </div>`;
  }).join("");
}

function renderCanastaTabla(cb) {
  const thead = $("#canasta-thead");
  const tbody = $("#canasta-tbody");
  const porTienda = cb.item_por_tienda || {};
  const nombres = Object.keys(porTienda).filter((n) => porTienda[n].length);
  const hayDatos = Object.values(porTienda).some((arr) => arr.some((x) => x.encontrado));
  if (!nombres.length || !hayDatos) {
    $("#canasta-vacio").style.display = "block";
    $("#canasta-tabla").style.display = "none";
    return;
  }
  $("#canasta-vacio").style.display = "none";
  $("#canasta-tabla").style.display = "";

  // Items de la primera tienda (todos tienen la misma lista)
  const items = porTienda[nombres[0]];

  // Precio mínimo por ítem para resaltar la tienda más barata
  const minPorItem = {};
  items.forEach((it) => {
    let min = Infinity;
    nombres.forEach((n) => {
      const match = porTienda[n].find((x) => x.item === it.item);
      if (match && match.precio !== null && match.precio < min) min = match.precio;
    });
    if (min !== Infinity) minPorItem[it.item] = min;
  });

  thead.innerHTML = `<tr><th>Producto</th>${nombres.map((n) => `<th>${esc(n)}</th>`).join("")}</tr>`;

  tbody.innerHTML = items.map((it) => {
    const celdas = nombres.map((n) => {
      const match = porTienda[n].find((x) => x.item === it.item);
      if (!match || !match.encontrado) return `<td class="precio-celda precio-no" title="No encontrado">—</td>`;
      const esMejor = minPorItem[it.item] === match.precio;
      const titulo = `${esc(match.producto)}`;
      return `<td class="precio-celda ${esMejor ? "precio-mejor" : ""}" title="${titulo}">B/. ${fmtNum(match.precio)}</td>`;
    });
    return `<tr><td class="canasta-item">${esc(it.item)}</td>${celdas.join("")}</tr>`;
  }).join("");
}

function renderCanasta(smart) {
  const cb = (smart && smart.canasta_basica) || {};
  renderCanastaBanner(cb);
  renderCanastaBarras(cb);
  renderCanastaTabla(cb);
}
