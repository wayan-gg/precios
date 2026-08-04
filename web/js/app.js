// app.js — orquesta la carga de data.json + data_smart.json y renderiza todo

(async function main() {
  initPromos();

  const [data, smart, llm] = await Promise.all([
    fetchJson(["data.json", "./data.json"]),
    fetchJson(["data_smart.json", "./data_smart.json"]),
    fetchJson(["data_llm.json", "./data_llm.json"]),
  ]);

  if (!data) {
    $("#updated").textContent = "No hay datos todavía. Ejecuta 'python ai_engine.py' y súbelos a GitHub Pages.";
    $("#promo-grid").innerHTML = `<div class="vacio">No se pudo cargar data.json</div>`;
    return;
  }

  window.DATA = data;

  $("#updated").textContent = "Última actualización: " + fmtFecha(data.generated_at) + " (se refresca 2 veces al día)";

  renderResumen(data);
  renderMejor(data);
  llenarFiltros(data);
  renderPromos(data);
  renderComparativas(data);
  renderEstadisticas(data);

  if (smart && smart.canasta_basica) {
    renderCanasta(smart);
  } else {
    $("#canasta-vacio").style.display = "block";
  }

  renderLLM(llm);
})();
