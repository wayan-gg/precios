// util.js — helpers compartidos por todas las secciones
const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtFecha(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-PA", { dateStyle: "long", timeStyle: "short" });
  } catch (_) { return iso; }
}

function fmtNum(n, dec = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toFixed(dec);
}

function precioCelda(precio, mejor) {
  if (precio === null || precio === undefined) {
    return '<td class="precio-celda precio-no">—</td>';
  }
  const cls = mejor ? "precio-mejor" : "";
  return `<td class="precio-celda ${cls}">B/. ${fmtNum(precio)}</td>`;
}

async function fetchJson(rutas) {
  for (const r of rutas) {
    try {
      const res = await fetch(r, { cache: "no-store" });
      if (res.ok) return await res.json();
    } catch (_) { /* probar siguiente */ }
  }
  return null;
}
