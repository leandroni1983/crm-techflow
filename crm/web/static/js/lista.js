/* ============ LISTA, FILTROS, SIN RETIRAR ============
   La pantalla de órdenes: accesos rápidos, buscador, acordeón y el aviso de equipos sin retirar.
   La lista se dibuja de a 50 para que con miles de órdenes el celular siga andando rápido. */
import { $, esc, num, money, fmtD, diasDesde } from './util.js';
import { DB } from './db.js';
import { find, yo, nombreEq, fechaOrd, saldo, costoRep, numOrden, normTel, esViejo, alertaDias, segLink, copiarLink, log, tareasPend, tareasVencidas } from './comun.js';
import { tipoMsg, LBL, LOGT, waLink, waComp, faltaPresu, garTxt, garantiaHasta, imprimir, etiquetar, enviarPDF, openOrd, nuevaOrden, aPapelera, enGarantia } from './orden.js';

const PAGINA = 50;                       // órdenes que se dibujan de una vez
let quick = '', abierta = null, limite = PAGINA;
const PRIO = { Alta: 0, Normal: 1, Baja: 2 };   // para ordenar por prioridad (menor = más urgente)

const QUICK = {
  dx: ['Para diagnosticar', o => o.estado === 'En diagnóstico'],
  pre: ['Presupuesto', o => o.estado === 'Presupuesto'],
  rep: ['Esperando repuesto', o => o.estado === 'Esperando repuesto'],
  listo: ['Listos para retirar', o => o.estado === 'Listo para retirar'],
  tar: ['Con tareas', o => tareasPend(o).length > 0],
  venc: ['Tareas vencidas', o => tareasVencidas(o).length > 0],
  viejos: ['Sin retirar +días', esViejo],
  gar: ['En garantía', enGarantia]
};
function drawChips() {
  const L = DB.ordenes;
  $('chips').innerHTML = `<button class="chip ${quick ? '' : 'on'}" data-q="">Todos (${L.length})</button>` + Object.entries(QUICK).map(([k, [t, fn]]) => {
    const n = L.filter(fn).length;
    return n || quick === k ? `<button class="chip ${quick === k ? 'on' : ''}" data-q="${k}">${k === 'viejos' ? `Sin retirar +${alertaDias()} días` : t} (${n})</button>` : '';
  }).join('');
}
function card(o) {
  const g = garantiaHasta(o), tipo = tipoMsg(o), costos = costoRep(o), viejo = esViejo(o), tp = tareasPend(o);
  const sal = saldo(o);
  const dinero = [num(o.monto) && 'Presupuesto: ' + money(num(o.monto)), (num(o.sena) || (o.pagos||[]).length) && 'Pagado: ' + money(num(o.sena) + (o.pagos||[]).reduce((a,p)=>a+num(p.monto),0)),
    num(o.monto) && ((o.pagado === '1' || o.pagado === true) ? '✅ Pagado' : (sal>0?'Saldo: ' + money(sal):'✅ Pagado'))].filter(Boolean).join(' · ');
  const datos = [o.equipo_tipo && 'Tipo: ' + esc(o.equipo_tipo), o.serie && 'S/N ' + esc(o.serie), o.color && esc(o.color), o.accesorios && 'Accesorios: ' + esc(o.accesorios), o.fisico && 'Físico: ' + esc(o.fisico), o.prioridad && 'Prioridad: ' + esc(o.prioridad)].filter(Boolean).join(' · ');
  const dias = viejo ? ' · +' + Math.floor(diasDesde(o.estado_fecha || o.creada)) + ' días' : '';
  return `<div class="ord" data-id="${o.id}">
    <button type="button" class="ord-line" data-a="toggle" data-id="${o.id}" aria-expanded="false">
      <span class="num">${esc(numOrden(o))}</span>
      <span class="ord-cli">${esc(o.cliente)}</span>
      <span class="ord-eq mut">${esc(nombreEq(o))}</span>
      <span class="ord-tag"><span class="tag ${viejo ? 'warn' : ''}">${esc(o.estado)}${dias}</span></span>
      <span class="ord-fecha mut">${esc(fechaOrd(o))}${o.hora ? ' ' + esc(o.hora) : ''}</span>
      <span class="ord-chev" aria-hidden="true">›</span>
    </button>
    <div class="ord-body" hidden>
    ${datos ? `<div class="mut ln">${datos}</div>` : ''}
    ${o.tel ? `<div class="mut ln">📱 ${esc(o.tel)}${o.direccion ? ' · ' + esc(o.direccion) : ''}</div>` : ''}
    ${o.tecnico ? `<div class="mut ln">👷 ${esc(o.tecnico)}</div>` : ''}
    ${o.clave ? `<div class="mut ln">🔒 Clave: ${esc(o.clave)}</div>` : ''}
    ${o.problema ? `<div class="mut ln">Falla: ${esc(o.problema)}</div>` : ''}
    ${o.diagnostico ? `<div class="mut ln">Diagnóstico: ${esc(o.diagnostico)}</div>` : ''}
    ${o.checklist.length ? `<div class="mut ln">Checklist: ${o.checklist.map(esc).join(', ')}</div>` : ''}
    ${dinero ? `<div class="ln">💲 ${dinero}</div>` : ''}
    ${o.entrega_est && o.estado !== 'Entregado' ? `<div class="mut ln">📅 Entrega estimada: ${fmtD(o.entrega_est)}</div>` : ''}
    ${g ? `<div class="ln"><span class="tag ${g >= new Date() ? 'ok' : 'warn'}">${esc(garTxt(o))}</span></div>` : ''}
    ${costos ? `<div class="mut ln">Costo repuestos: ${money(costos)}${num(o.monto) ? ' · Ganancia: ' + money(num(o.monto) - costos) : ''}</div>` : ''}
    ${tp.length ? `<div class="ln tareas${tareasVencidas(o).length ? ' venc' : ''}">✅ ${tp.length} tarea${tp.length > 1 ? 's' : ''}: ${tp.map(t => esc(t.t) + (t.f ? ' (' + fmtD(t.f) + ')' : '')).join(' · ')}</div>` : ''}
    ${o.adjuntos.length ? `<div class="mut ln">📎 ${o.adjuntos.map(a => `<a href="${esc(a.u)}" target="_blank" rel="noopener">${esc(a.n)}</a>`).join(', ')}</div>` : ''}
    ${o.imagenes.length ? `<div class="imgs">${o.imagenes.map(s => s.startsWith('data:') ? `<img src="${s}" alt="foto">` : `<a href="${s}" target="_blank" rel="noopener"><img loading="lazy" decoding="async" src="${s}" alt="foto"></a>`).join('')}</div>` : ''}
    <div class="acts">
      ${faltaPresu(o) ? `<button class="wa" data-a="falta">${LBL.presupuesto}</button>`
        : `<a class="wa" data-log="${tipo}" data-id="${o.id}" href="${waLink(o)}" target="_blank" rel="noopener">${LBL[tipo]}</a>`}
      <button class="wa2" data-a="pdf" data-id="${o.id}">📄 Comprobante PDF</button>
      ${['Listo para retirar', 'Entregado'].includes(o.estado) ? `<button class="wa2" data-a="pdfe" data-id="${o.id}">📄 Entrega PDF</button><button data-a="printe" data-id="${o.id}">🖨️ Entrega</button>` : ''}
      <a class="wa wa2" data-log="texto" data-id="${o.id}" href="${waComp(o)}" target="_blank" rel="noopener">Comprobante (texto)</a>
      <button data-a="print" data-id="${o.id}">🖨️ Imprimir</button>
      <button data-a="label" data-id="${o.id}">🏷️ Etiqueta</button>
      ${o.seg ? `<button data-a="seg" data-id="${o.id}" title="Link privado para que el cliente vea cómo va su orden">🔗 Seguimiento</button>` : ''}
      <button data-a="cli" data-id="${o.id}" title="Historial, deuda y equipos del cliente">👤 Cliente</button>
      <button data-a="edit" data-id="${o.id}">Editar</button>
      <button class="dg" data-a="del" data-id="${o.id}" title="Manda la orden a la papelera (se puede recuperar desde Configuración)">🗑️ Borrar</button>
    </div></div></div>`;
}
export function render() {
  drawChips();
  const sv = listosViejos().length; $('bSinRet').textContent = '📦 Sin retirar' + (sv ? ` (${sv})` : '');
  const q = $('q').value.toLowerCase(), f = $('fs').value, tf = $('fT').value, qf = quick ? QUICK[quick][1] : () => true;
  const L = DB.ordenes.filter(o => (!f || o.estado === f) && (!tf || o.tecnico === (tf === '@yo' ? yo() : tf)) && qf(o) &&
    (numOrden(o) + o.cliente + nombreEq(o) + (o.equipo_tipo || '') + o.tel + o.serie).toLowerCase().includes(q));
  const ord = $('orden').value;
  if (ord === 'prioridad') L.sort((a, b) => (PRIO[a.prioridad] ?? 1) - (PRIO[b.prioridad] ?? 1) || String(b.creada).localeCompare(String(a.creada)));
  else if (ord === 'deuda') L.sort((a, b) => saldo(b) - saldo(a));
  else if (ord === 'antiguos') L.sort((a, b) => String(a.creada).localeCompare(String(b.creada)));
  else L.sort((a, b) => String(b.creada).localeCompare(String(a.creada)));
  const visibles = L.slice(0, limite);
  $('list').innerHTML = visibles.length
    ? visibles.map(card).join('') + (L.length > limite
      ? `<div class="acts mas"><button type="button" data-a="mas">Ver ${Math.min(PAGINA, L.length - limite)} más · ${visibles.length} de ${L.length}</button></div>` : '')
    : '<div class="empty">No hay órdenes para mostrar. Creá una con “+ Nueva orden”.</div>';
  if (abierta) { if ($('list').querySelector('.ord[data-id="' + CSS.escape(abierta) + '"]')) expandir(abierta, true); else abierta = null; }
  $('ordCount').textContent = `(${L.length}${L.length !== DB.ordenes.length ? ' de ' + DB.ordenes.length : ''})`;
  llenarDL();
}
/* Acordeón: una orden abierta a la vez. Al tocar la línea se despliega el detalle completo. */
function expandir(id, on) {
  const c = $('list').querySelector('.ord[data-id="' + CSS.escape(id) + '"]'); if (!c) return;
  c.classList.toggle('abierta', on);
  const body = c.querySelector('.ord-body'); if (body) body.hidden = !on;
  const linea = c.querySelector('.ord-line'); if (linea) linea.setAttribute('aria-expanded', on ? 'true' : 'false');
}
function toggleOrd(id) {
  if (abierta === id) { expandir(id, false); abierta = null; return; }
  if (abierta) expandir(abierta, false);
  abierta = id; expandir(id, true);
}
function llenarDL() {
  const m = new Map(); DB.ordenes.forEach(o => { if (o.tel && !m.has(normTel(o.tel))) m.set(normTel(o.tel), o); });
  $('dlTel').innerHTML = [...m.values()].map(o => `<option value="${esc(o.tel)}">${esc(o.cliente)}</option>`).join('');
  $('dlCli').innerHTML = [...new Set(DB.ordenes.map(o => o.cliente).filter(Boolean))].map(c => `<option value="${esc(c)}">`).join('');
}
$('list').onclick = async e => {
  const t = e.target, an = t.closest('a[data-log]');
  if (an) { const o = find(an.dataset.id); if (o) { await log(o, LOGT[an.dataset.log]); render(); } return; }
  const b = t.closest('[data-a]');
  if (b) {
    if (b.dataset.a === 'mas') { limite += PAGINA; return render(); }
    if (b.dataset.a === 'toggle') return toggleOrd(b.dataset.id);
    const o = find(b.dataset.id), a = b.dataset.a;
    if (a === 'falta') return alert('Para enviar el presupuesto cargá el diagnóstico y el monto (botón Editar).');
    if (a === 'pdf') return enviarPDF(o);
    if (a === 'pdfe') return enviarPDF(o, 'entrega');
    if (a === 'printe') return imprimir(o, 'entrega');
    if (a === 'print') return imprimir(o);
    if (a === 'label') return etiquetar(o);
    if (a === 'edit') return openOrd(o);
    if (a === 'seg') return copiarLink(o);
    if (a === 'cli') return fichaCliente(o);
    if (a === 'del') return aPapelera(o);
    return;
  }
};
$('chips').onclick = e => { const b = e.target.closest('[data-q]'); if (b) { quick = b.dataset.q; limite = PAGINA; render(); } };
$('q').oninput = () => { limite = PAGINA; render(); };
$('fs').onchange = () => { limite = PAGINA; render(); };
$('fT').onchange = () => { limite = PAGINA; render(); };
$('orden').onchange = () => { limite = PAGINA; render(); };
export function drawTec() {
  const v = $('fT').value;
  $('fT').innerHTML = '<option value="">Todos los técnicos</option><option value="@yo">Mis órdenes</option>' + DB.tecnicos.map(n => `<option>${esc(n)}</option>`).join('');
  $('fT').value = v; $('fT').style.display = DB.tecnicos.length > 1 ? '' : 'none';
}

/* ============ FICHA DE CLIENTE ============
   Todo el historial de una persona: sus equipos, lo que debe y lo que ya pagó. Se abre desde el botón
   "👤 Cliente" de una orden y agrupa por teléfono (o por nombre si no hay teléfono). */
let fichaActual = [], fichaEq = {};
const claveCli = o => { const t = normTel(o.tel); return t ? 't:' + t : 'n:' + String(o.cliente || '').trim().toLowerCase(); };
function fichaCliente(o) {
  const k = claveCli(o), L = DB.ordenes.filter(x => claveCli(x) === k).sort((a, b) => String(b.creada).localeCompare(String(a.creada)));
  const deuda = L.reduce((a, x) => a + saldo(x), 0);
  const cob = L.reduce((a, x) => a + num(x.sena) + (x.pagos || []).reduce((s, p) => s + num(p.monto), 0), 0);
  const fact = L.filter(x => x.estado === 'Entregado').reduce((a, x) => a + num(x.monto), 0);
  const eq = [...new Set(L.map(nombreEq).filter(Boolean))];
  const grupos = {}; L.forEach(x => { const n = nombreEq(x) || '(sin equipo)'; (grupos[n] = grupos[n] || []).push(x); });
  fichaEq = Object.fromEntries(Object.entries(grupos).map(([n, xs]) => [n, xs[0]]));
  $('dCliTit').textContent = '👤 ' + (o.cliente || 'Cliente');
  $('dCliBody').innerHTML = `
    <div class="caja-tot">
      <div class="kpi"><span class="kpi-t">Órdenes</span><b class="kpi-v">${L.length}</b></div>
      <div class="kpi ok"><span class="kpi-t">Total cobrado</span><b class="kpi-v">${money(cob)}</b></div>
      <div class="kpi ${deuda > 0 ? 'warn' : ''}"><span class="kpi-t">Deuda pendiente</span><b class="kpi-v">${money(deuda)}</b></div>
      <div class="kpi"><span class="kpi-t">Facturado entregado</span><b class="kpi-v">${money(fact)}</b></div>
    </div>
    ${o.tel ? `<div class="mut ln">📱 ${esc(o.tel)}${o.direccion ? ' · ' + esc(o.direccion) : ''}</div>` : ''}
    ${eq.length ? `<div class="mut ln">Equipos: ${eq.map(esc).join(', ')}</div>` : ''}
    <div style="margin-top:10px"><b>Equipos de este cliente</b><span class="mut"> · tocá para repetir la orden con el mismo equipo</span></div>
    <div class="movs">${Object.entries(grupos).map(([n, xs]) => `<div class="kv"><span>${esc(n)}<span class="mut"> · ${xs.length} orden${xs.length > 1 ? 'es' : ''} · última ${esc(fmtD(String(xs[0].creada).slice(0, 10)))}</span></span><button type="button" data-neweq="${esc(n)}">+ Orden de este equipo</button></div>`).join('')}</div>
    <div style="margin-top:10px" class="movs">${L.map(x => {
      const s = saldo(x);
      return `<div class="kv"><span>${esc(numOrden(x))} · ${esc(nombreEq(x))}<span class="mut"> · ${esc(fmtD(String(x.creada).slice(0, 10)))} · ${esc(x.estado)}</span></span>
        <span>${num(x.monto) ? (x.pagado === '1' || s <= 0 ? '<b style="color:var(--wa)">pagado</b>' : '<span class="mut">debe </span>' + money(s)) : ''}</span></div>`;
    }).join('')}</div>`;
  fichaActual = L;
  $('dCli').showModal();
}
$('dCliCan').onclick = () => $('dCli').close();
$('dCli').onclick = e => {
  const b = e.target.closest('[data-neweq]'); if (!b) return;
  const x = fichaEq[b.dataset.neweq]; if (!x) return;
  $('dCli').close();
  nuevaOrden({ cliente: x.cliente, tel: x.tel, direccion: x.direccion, equipo: x.equipo, equipo_tipo: x.equipo_tipo, marca: x.marca, serie: x.serie });
};
$('dCliCsv').onclick = () => {
  const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  const cab = ['N° orden', 'Fecha', 'Cliente', 'Equipo', 'Estado', 'Presupuesto', 'Seña', 'Pagos', 'Total cobrado', 'Deuda'];
  const filas = fichaActual.map(x => {
    const tot = num(x.sena) + (x.pagos || []).reduce((a, p) => a + num(p.monto), 0);
    return [numOrden(x), fmtD(String(x.creada).slice(0, 10)), x.cliente, nombreEq(x), x.estado, num(x.monto), num(x.sena),
      (x.pagos || []).reduce((a, p) => a + num(p.monto), 0), tot, x.pagado ? 0 : Math.max(num(x.monto) - tot, 0)];
  });
  const csv = '\ufeff' + [cab.map(q).join(';'), ...filas.map(f => f.map(q).join(';'))].join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = 'cliente-' + (fichaActual[0]?.cliente || 'ficha').replace(/[^\w]+/g, '-') + '.csv'; a.click(); URL.revokeObjectURL(a.href);
};

/* ============ EQUIPOS SIN RETIRAR ============
   Los que están listos y el cliente todavía no vino a buscar: de un vistazo, con el aviso a mano. */
const listos = () => DB.ordenes.filter(o => o.estado === 'Listo para retirar')
  .sort((a, b) => diasDesde(b.estado_fecha || b.creada) - diasDesde(a.estado_fecha || a.creada));
const listosViejos = () => listos().filter(esViejo);
function drawSinRet() {
  const L = listos(), v = listosViejos();
  $('srSub').textContent = L.length ? `${L.length} equipo${L.length > 1 ? 's' : ''} esperando retiro`
    + (v.length ? ` · ${v.length} hace más de ${alertaDias()} días` : ' · ninguno atrasado') : '';
  $('srList').innerHTML = L.length ? L.map(o => {
    const d = diasDesde(o.estado_fecha || o.creada), u = segLink(o);
    return `<div class="sinret"><div>
      <div><span class="num">${esc(numOrden(o))}</span> · ${esc(o.cliente)}</div>
      <div class="mut">${esc(nombreEq(o))} · listo hace ${d} día${d === 1 ? '' : 's'}${d > alertaDias() ? ' ⚠️ avisale' : ''}</div></div>
      <div class="acts">${o.tel ? `<a class="wa" href="${esc(waLink(o))}" target="_blank" rel="noopener" data-aviso="${esc(o.id)}">📲 Avisar</a>` : '<span class="mut">sin teléfono</span>'}
      ${u ? `<button type="button" data-seg="${esc(o.id)}" title="Copiar el link de seguimiento">🔗 Link</button>` : ''}
      <button type="button" data-ver="${esc(o.id)}">Ver orden</button></div></div>`;
  }).join('') : '<div class="mut">No hay equipos esperando retiro. 👌</div>';
}
$('bSinRet').onclick = () => { drawSinRet(); $('dSinRet').showModal(); };
$('srCan').onclick = () => $('dSinRet').close();
$('srList').onclick = async e => {
  const s = e.target.closest('[data-seg]'), v = e.target.closest('[data-ver]'), a = e.target.closest('[data-aviso]');
  if (s) return copiarLink(find(s.dataset.seg));
  if (v) { $('dSinRet').close(); return openOrd(find(v.dataset.ver)); }
  if (a) { await log(find(a.dataset.aviso), LOGT.listo); render(); drawSinRet(); }   // queda anotado que se avisó
};
