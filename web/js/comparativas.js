// comparativas.js — el mismo producto en varias tiendas

function renderComparativas(data) {
  const tbody = $("#cmp-body");
  const lista = data.comparativas || [];
  $("#cmp-vacio").style.display = lista.length ? "none" : "block";
  tbody.innerHTML = lista.map((c) => {
    const precios = Object.entries(c.precios || {})
      .map(([s, v]) => `${esc(s)}: <b>B/. ${fmtNum(v)}</b>`).join(" · ");
    return `
      <tr>
        <td>
          <div class="cmp-producto">${esc(c.producto)}</div>
          <div class="cmp-cat">${esc(c.categoria)}</div>
        </td>
        <td class="cmp-ganador">${esc(c.ganador)}</td>
        <td class="cmp-ahorro">B/. ${fmtNum(c.ahorro)}</td>
        <td class="cmp-precios">${precios}</td>
        <td class="cmp-enlace">${c.enlace ? `<a href="${esc(c.enlace)}" target="_blank" rel="noopener">Ver →</a>` : ""}</td>
      </tr>`;
  }).join("");
}
