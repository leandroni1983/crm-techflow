/* ============ PANEL DE ESTADÍSTICAS Y EXPORTAR ============
   Los números se calculan de dos maneras, siempre con las mismas reglas:
   - con conexión y todo sincronizado, los pide ya sumados al servidor (/api/resumen): con miles de órdenes el
     celular no tiene que recorrerlas todas;
   - sin conexión (o con cambios sin subir), los calcula acá mismo sobre la copia local.
   Así el panel anda igual sin internet y los números no dependen de dónde salieron. */
import { $, esc, num, money, hoy, fmtD, cantR, p2, MESES, PALETA, topN } from './util.js';
import { DB } from './db.js';
import { numOrden, fechaOrd, costoRep, alertaDias, esViejo, repCat, repBajos, repDisp } from './comun.js';
import { garantiaHasta } from './orden.js';

/* Columnas del detalle: las mismas que se exportan a Excel (CSV). tipo: 'txt' o 'money' */
const COLS = [
  ['N° orden', numOrden, 'txt'], ['Fecha ingreso', fechaOrd, 'txt'], ['Cliente', o => o.cliente, 'txt'], ['Teléfono', o => o.tel, 'txt'],
  ['Equipo', o => o.equipo, 'txt'], ['Tipo de equipo', o => o.equipo_tipo, 'txt'], ['Marca', o => o.marca, 'txt'], ['N° de serie', o => o.serie, 'txt'], ['Estado', o => o.estado, 'txt'],
  ['Técnico', o => o.tecnico, 'txt'], ['Tipo de falla', o => o.falla_tipo, 'txt'], ['Falla', o => o.problema, 'txt'], ['Diagnóstico', o => o.diagnostico, 'txt'], ['Presupuesto', o => num(o.monto), 'money'],
  ['Seña', o => num(o.sena), 'money'], ['Pagado', o => o.pagado ? 'Sí' : 'No', 'txt'], ['Costo repuestos', costoRep, 'money'],
  ['Ganancia', o => num(o.monto) - costoRep(o), 'money'], ['Fecha entrega', o => fmtD(o.entrega_fecha), 'txt'],
  ['Repuestos', o => (o.repuestos || []).map(r => (r.desc || '') + (cantR(r) > 1 ? ' x' + cantR(r) : '')).filter(Boolean).join(', '), 'txt'],
  ['Garantía hasta', o => { const g = garantiaHasta(o); return g ? g.toLocaleDateString('es-AR') : ''; }, 'txt']
];
function descargarCSV(rows, nombre) {
  const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  const csv = '\ufeff' + [COLS.map(c => q(c[0])).join(';'), ...rows.map(o => COLS.map(c => q(c[1](o))).join(';'))].join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = nombre; a.click(); URL.revokeObjectURL(a.href);
}

/* ---- período seleccionado ---- */
const ym = iso => { const d = new Date(iso); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}`; };
const d2s = d => d ? `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}` : null;
function rango() {
  const per = $('rPer').value, ahora2 = new Date(), y = ahora2.getFullYear(), mo = ahora2.getMonth();
  const finMes = (yy, m0) => new Date(yy, m0 + 1, 0);
  let desde, hasta = finMes(y, mo), etiqueta = '';
  if (per === 'mes') {
    const [yy, mm] = ($('rMes').value || `${y}-${p2(mo + 1)}`).split('-').map(Number);
    desde = new Date(yy, mm - 1, 1); hasta = finMes(yy, mm - 1);
    etiqueta = desde.toLocaleDateString('es-AR', { month: 'long', year: 'numeric' });
  } else if (per === '3m' || per === '6m' || per === '12m') {
    desde = new Date(y, mo - parseInt(per) + 1, 1); hasta = finMes(y, mo); etiqueta = `Últimos ${parseInt(per)} meses`;
  } else if (per === 'ano') {
    desde = new Date(y, 0, 1); hasta = new Date(y, 11, 31); etiqueta = 'Año ' + y;
  } else { desde = null; hasta = null; etiqueta = 'Todo el historial'; }
  return { desde: d2s(desde), hasta: d2s(hasta), etiqueta };
}
const enRango = (iso, r) => { const d = String(iso || '').slice(0, 10); return !!d && (!r.desde || d >= r.desde) && (!r.hasta || d <= r.hasta); };
function ultimosMeses(n, hastaIso) {
  const d = new Date((hastaIso || hoy()) + 'T12:00:00'), out = [];
  for (let i = n - 1; i >= 0; i--) { const x = new Date(d.getFullYear(), d.getMonth() - i, 1); out.push(`${x.getFullYear()}-${p2(x.getMonth() + 1)}`); }
  return out;
}

/* ---- gráficos (SVG/CSS puro, sin librerías) ---- */
const vacio = t => `<div class="mut" style="padding:6px 0">${esc(t || 'Sin datos')}</div>`;
function barrasH(items) {
  const L = items.filter(i => i.value > 0); if (!L.length) return vacio();
  const max = Math.max(...L.map(i => i.value));
  return `<div class="barras">` + L.map((it, i) =>
    `<div class="barra"><span class="barra-l" title="${esc(it.label)}">${esc(it.label)}</span>` +
    `<span class="barra-t"><i style="width:${Math.max(4, Math.round(it.value / max * 100))}%;background:${PALETA[i % PALETA.length]}"></i></span>` +
    `<b class="barra-v">${it.value}</b></div>`).join('') + `</div>`;
}
function barrasV(labels, series) {
  if (!labels.length) return vacio();
  const max = Math.max(1, ...series.flatMap(s => s.values.map(num)));
  return `<div class="cv"><div class="cv-plot">` + labels.map((lb, i) =>
    `<div class="cv-col" title="${esc(lb)}"><div class="cv-bars">` +
    series.map(s => `<i style="height:${Math.max(2, Math.round(num(s.values[i]) / max * 100))}%;background:${s.color}"></i>`).join('') +
    `</div><small>${esc(lb)}</small></div>`).join('') +
    `</div><div class="cv-leg">` + series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('') + `</div></div>`;
}
function dona(items) {
  const L = items.filter(i => i.value > 0), total = L.reduce((a, i) => a + i.value, 0);
  if (!total) return vacio();
  const r = 54, c = 2 * Math.PI * r; let off = 0;
  const segs = L.map((it, i) => {
    const len = it.value / total * c;
    const s = `<circle cx="70" cy="70" r="${r}" fill="none" stroke="${PALETA[i % PALETA.length]}" stroke-width="20" stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-off}"></circle>`;
    off += len; return s;
  }).join('');
  return `<div class="dona"><svg viewBox="0 0 140 140" role="img" aria-label="Distribución">${segs}` +
    `<text x="70" y="67" text-anchor="middle" class="dona-n">${total}</text><text x="70" y="85" text-anchor="middle" class="dona-s">órdenes</text></svg>` +
    `<div class="dona-leg">` + L.map((it, i) =>
      `<div class="kv"><span><i class="dot" style="background:${PALETA[i % PALETA.length]}"></i>${esc(it.label)}</span><b>${it.value} · ${Math.round(it.value / total * 100)}%</b></div>`).join('') + `</div></div>`;
}

/* ---- los números: o los trae el servidor, o se calculan acá ---- */
const items = (arr, n) => topN(arr, n).map(([label, value]) => ({ label, value }));
const mesesDe = r => ultimosMeses(12, r.hasta || hoy());
function datosLocal(r) {
  const L = DB.ordenes;
  const ing = L.filter(o => enRango(o.creada, r));
  const ent = L.filter(o => o.entrega_fecha && enRango(o.entrega_fecha, r));
  const fact = ent.reduce((a, o) => a + num(o.monto), 0), cost = ent.reduce((a, o) => a + costoRep(o), 0);
  const meses = mesesDe(r), porMes = {}; meses.forEach(m => porMes[m] = { n: 0, fact: 0, cost: 0 });
  L.forEach(o => { const m = ym(o.creada); if (porMes[m]) porMes[m].n++; });
  ent.forEach(o => { const m = String(o.entrega_fecha).slice(0, 7); if (porMes[m]) { porMes[m].fact += num(o.monto); porMes[m].cost += costoRep(o); } });
  return {
    ingresadas: ing.length, pendientes: ing.filter(o => o.estado !== 'Entregado').length, entregadas: ent.length,
    facturado: fact, repuestos: cost, ganancia: fact - cost, sinretirar: L.filter(esViejo).length,
    ticket: ent.length ? fact / ent.length : 0, meses, porMes,
    estados: items(ing.map(o => o.estado), 8), tecnicos: items(ing.map(o => o.tecnico || '(sin asignar)'), 8),
    equipos: items(ing.map(o => (o.equipo_tipo || '').trim() || 'Sin clasificar'), 8),
    marcas: items(ing.map(o => (o.marca || '').trim().toLowerCase()).filter(Boolean), 8),
    fallas: items(ing.map(o => (o.falla_tipo || '').trim() || 'Sin clasificar'), 8)
  };
}
/* ¿Podemos confiar en el servidor? Solo si hay conexión y no quedan cambios locales sin subir. */
const puedeServidor = () => !!(DB.api && DB.sync && DB.sync.online && !DB.sync.pendientes && !DB.sync.errores);
async function datosServidor(r) {
  const qs = new URLSearchParams({ desde: r.desde || '', hasta: r.hasta || '', tz: String(-new Date().getTimezoneOffset()) });
  const d = await DB.reqJSON('/api/resumen?' + qs);
  return d && Array.isArray(d.meses) ? d : null;
}

function dibujar(r, d) {
  const kpi = (t, v, s, cls) => `<div class="kpi ${cls || ''}"><span class="kpi-t">${esc(t)}</span><b class="kpi-v">${v}</b>${s ? `<span class="kpi-s">${esc(s)}</span>` : ''}</div>`;
  const etiquetas = d.meses.map(m => { const [yy, mm] = m.split('-'); return MESES[+mm - 1] + ' ' + yy.slice(2); });
  $('rSub').textContent = `${r.etiqueta} · generado el ${new Date().toLocaleString('es-AR')}`;
  $('rOut').innerHTML =
    `<div class="kpis">
      ${kpi('Órdenes ingresadas', d.ingresadas, `${d.pendientes} sin entregar`)}
      ${kpi('Equipos entregados', d.entregadas, d.ticket ? 'Ticket prom. ' + money(d.ticket) : '')}
      ${kpi('Facturado', money(d.facturado), 'sobre entregados', 'ok')}
      ${kpi('Costo repuestos', money(d.repuestos))}
      ${kpi('Ganancia', money(d.ganancia), '', d.ganancia >= 0 ? 'ok' : 'dg')}
      ${kpi('Sin retirar', d.sinretirar, `+ de ${alertaDias()} días`, d.sinretirar ? 'warn' : '')}
    </div>
    <section class="pane"><h4>Órdenes ingresadas · últimos 12 meses</h4>
      ${barrasV(etiquetas, [{ name: 'Órdenes', color: PALETA[0], values: d.meses.map(m => d.porMes[m].n) }])}</section>
    <section class="pane"><h4>Facturado y ganancia por mes</h4>
      ${barrasV(etiquetas, [
        { name: 'Facturado', color: PALETA[1], values: d.meses.map(m => d.porMes[m].fact) },
        { name: 'Ganancia', color: PALETA[2], values: d.meses.map(m => d.porMes[m].fact - d.porMes[m].cost) }])}</section>
    <div class="grid2">
      <section class="pane"><h4>Por estado</h4>${dona(d.estados)}</section>
      <section class="pane"><h4>Órdenes por técnico</h4>${barrasH(d.tecnicos)}</section>
      <section class="pane"><h4>Equipos más frecuentes</h4>${barrasH(d.equipos)}</section>
      <section class="pane"><h4>Marcas más frecuentes</h4>${barrasH(d.marcas)}</section>
      <section class="pane"><h4>Fallas más comunes</h4>${barrasH(d.fallas)}</section>
      ${repCat().length ? `<section class="pane"><h4>Repuestos a reponer</h4>${repBajos().length
        ? repBajos().map(it => `<div class="kv"><span>${esc(it.nombre)}</span><span class="mut">disp. ${repDisp(it)} · mínimo ${esc(it.minimo)}</span></div>`).join('')
        : '<div class="mut">Todo con stock suficiente.</div>'}</section>` : ''}
    </div>`;
}
export async function resumen() {
  const r = rango();
  let d = null;
  if (puedeServidor()) { try { d = await datosServidor(r); } catch (e) { d = null; } }
  dibujar(r, d || datosLocal(r));
}
$('rPer').onchange = () => { $('rMesW').style.display = $('rPer').value === 'mes' ? '' : 'none'; resumen(); };
$('rMes').onchange = resumen;
$('rExcel').onclick = () => descargarCSV(DB.ordenes.filter(o => enRango(o.creada, rango())), 'estadisticas-' + hoy() + '.csv');
$('bCsv').onclick = () => descargarCSV(DB.ordenes, 'ordenes-' + hoy() + '.csv');
