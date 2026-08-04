// llm.js — renderiza web/data_llm.json (análisis del LLM)

function renderLLM(llm) {
  const sec = $("#ia-analisis");
  if (!llm || (llm.error && !llm.resumen)) {
    sec.hidden = true;
    return;
  }
  sec.hidden = false;
  $("#ia-vacio").style.display = "none";

  if (llm.resumen) {
    $("#ia-resumen").textContent = llm.resumen;
  } else {
    $("#ia-resumen").textContent = llm.raw ? llm.raw.slice(0, 400) : "";
  }

  const mejor = $("#ia-mejor");
  if (llm.mejor_supermercado) {
    mejor.hidden = false;
    mejor.innerHTML = `
      <div class="l-titulo">La IA recomienda</div>
      <div class="l-nombre">${esc(llm.mejor_supermercado.nombre)}</div>
      <div class="l-razon">${esc(llm.mejor_supermercado.razon || "")}</div>`;
  } else {
    mejor.hidden = true;
  }

  const promos = $("#ia-promos");
  if (Array.isArray(llm.mejores_promociones) && llm.mejores_promociones.length) {
    promos.hidden = false;
    promos.innerHTML = `<h3>Promociones destacadas</h3>` + llm.mejores_promociones.map((p) => `
      <div class="ia-promo">
        <div class="p-nombre">${esc(p.nombre)}</div>
        <div class="p-tienda">${esc(p.supermercado)} · B/. ${fmtNum(p.precio)} <s>${fmtNum(p.precio_regular)}</s> -${p.descuento_pct}%</div>
        <div class="p-desc">${esc(p.razon || "")}</div>
      </div>`).join("");
  } else {
    promos.hidden = true;
  }

  const insights = $("#ia-insights");
  if (Array.isArray(llm.insights) && llm.insights.length) {
    insights.hidden = false;
    insights.innerHTML = `<h3>Insights</h3>` + llm.insights.map((i) => `<div class="ia-insight">${esc(i)}</div>`).join("");
  } else {
    insights.hidden = true;
  }
}
