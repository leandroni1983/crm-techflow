/* ============ LISTA, FILTROS, SIN RETIRAR ============
   La pantalla de órdenes: accesos rápidos, buscador, acordeón y el aviso de equipos sin retirar.
   La lista se dibuja de a 50 para que con miles de órdenes el celular siga andando rápido. */
import { $, esc, num, money, fmtD, diasDesde } from './util.js';
import { DB } from './db.js';
import { find, yo, nombreEq, fechaOrd, saldo, costoRep, numOrden, normTel, esViejo, alertaDias, segLink, copiarLink, log } from './comun.js';
import { tipoMsg, LBL, LOGT, waLink, waComp, faltaPresu, garTxt, garantiaHasta, imprimir, etiquetar, enviarPDF, openOrd, aPapelera, enGarantia } from './orden.js';

const PAGINA = 50;                       // órdenes que se dibujan de una vez
let quick = '', abierta = null, limite = PAGINA;

const QUICK = {
  dx: ['Para diagnosticar', o => o.estado === 'En diagnóstico'],
  pre: ['Presupuesto', o => o.estado === 'Presupuesto'],
  rep: ['Esperando repuesto', o => o.estado === 'Esperando repuesto'],
  listo: ['Listos para retirar', o => o.estado === 'Listo para retirar'],
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
  const g = garantiaHasta(o), tipo = tipoMsg(o), costos = costoRep(o), viejo = esViejo(o);
  const dinero = [num(o.monto) && 'Presupuesto: ' + money(num(o.monto)), num(o.sena) && 'Seña: ' + money(num(o.sena)),
    num(o.monto) && (o.pagado ? '✅ Pagado' : 'Saldo: ' + money(saldo(o)))].filter(Boolean).join(' · ');
  const datos = [o.equipo_tipo && 'Tipo: ' + esc(o.equipo_tipo), o.serie && 'S/N ' + esc(o.serie), o.color && esc(o.color), o.accesorios && 'Accesorios: ' + esc(o.accesorios), o.fisico && 'Físico: ' + esc(o.fisico)].filter(Boolean).join(' · ');
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
    if (a === 'del') return aPapelera(o);
    return;
  }
};
$('chips').onclick = e => { const b = e.target.closest('[data-q]'); if (b) { quick = b.dataset.q; limite = PAGINA; render(); } };
$('q').oninput = () => { limite = PAGINA; render(); };
$('fs').onchange = () => { limite = PAGINA; render(); };
$('fT').onchange = () => { limite = PAGINA; render(); };
export function drawTec() {
  const v = $('fT').value;
  $('fT').innerHTML = '<option value="">Todos los técnicos</option><option value="@yo">Mis órdenes</option>' + DB.tecnicos.map(n => `<option>${esc(n)}</option>`).join('');
  $('fT').value = v; $('fT').style.display = DB.tecnicos.length > 1 ? '' : 'none';
}

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
