/* Estado de la conexión, filtros y listado de órdenes */
let quick = '', pagina = 1; const PAGE = 40, abiertas = new Set();
const alertaDias = () => parseInt(cfg().dias_alerta) || 7;
const ahoraMs = () => Date.now();
const QUICK = {
  activas: ['Activas', o => o.estado !== 'Entregado'],
  dx: ['Para diagnosticar', o => o.estado === 'En diagnóstico'],
  pre: ['Presupuesto', o => o.estado === 'Presupuesto'],
  rep: ['Esperando repuesto', o => o.estado === 'Esperando repuesto'],
  listo: ['Listas para retirar', o => o.estado === 'Listo para retirar'],
  viejos: ['Sin retirar', o => o.estado === 'Listo para retirar' && diasDesde(o.estado_fecha || o.creada) > alertaDias()],
  presin: ['Presupuesto sin respuesta', o => o.estado === 'Presupuesto' && diasDesde(o.estado_fecha || o.creada) > alertaDias()],
  atras: ['Entrega atrasada', o => !!o.entrega_est && o.entrega_est < hoy() && !['Entregado', 'Listo para retirar'].includes(o.estado)],
  debe: ['Con saldo', o => o.estado === 'Entregado' && num(o.monto) > 0 && saldo(o) > 0],
  vence: ['Garantía por vencer', o => { const g = garantiaHasta(o); return !!g && g >= ahoraMs() && (g - ahoraMs()) / 864e5 <= 15; }],
  gar: ['En garantía', enGarantia]
};

/* ---------- estado de conexión, cuenta y marca ---------- */
function localOrders() { try { return (JSON.parse(localStorage.getItem(DB.K)) || {}).ordenes || []; } catch (e) { return []; } }
function drawModo() {
  const s = DB.sync || { online: true, pendientes: 0, errores: 0, motor: '' }, n = DB.api ? localOrders().length : 0, pill = $('modo');
  const camb = k => `${k} ${pl(k, 'cambio', 'cambios')}`, avisos = [];
  let cls = 'pill', txt = '', tip = '';
  if (!DB.api) { cls = 'pill warn'; txt = 'Modo navegador'; avisos.push('Estás en modo navegador: lo que cargues <b>no se guarda en la base</b>. Ejecutá <code>python -m crm</code> y abrí http://localhost:8000 (el PDF y el QR necesitan el servidor).'); }
  else if (s.errores) { cls = 'pill err'; txt = `${camb(s.errores)} con error`; avisos.push(`${camb(s.errores)} no se pudieron enviar a la base y quedaron apartados. Avisá al administrador.`); }
  else if (!s.online) { cls = 'pill warn'; txt = 'Sin conexión' + (s.pendientes ? `, ${camb(s.pendientes)} ${pl(s.pendientes, 'pendiente', 'pendientes')}` : ''); avisos.push(`Sin conexión con la base de datos: seguís trabajando en modo local${s.pendientes ? `. ${camb(s.pendientes)} ${pl(s.pendientes, 'espera', 'esperan')} y se ${pl(s.pendientes, 'envía', 'envían')} solos al volver la conexión` : ''}.`); }
  else if (s.pendientes) { txt = `Sincronizando ${camb(s.pendientes)}`; }
  else { txt = 'Conectado' + (s.motor ? ' a ' + s.motor : ''); }
  tip = DB.api ? 'Estado de la conexión con la base de datos' : 'Sin servidor: los datos quedan solo en este navegador';
  pill.className = cls; pill.title = tip; pill.innerHTML = `<span>${esc(txt)}</span>`;
  if (n) avisos.push(`Hay ${n} ${pl(n, 'orden guardada', 'órdenes guardadas')} en este navegador. <button id="bImp">Importar a la base</button>`);
  const av = $('aviso'); av.hidden = !avisos.length;
  av.innerHTML = avisos.length ? avisos.map(a => `<div><svg class="i"><use href="#i-alert"/></svg><span>${a}</span></div>`).join('') : '';
  const nom = yo(); $('bUser').textContent = (nom[0] || '?').toUpperCase(); $('uName').textContent = nom || 'Sin sesión';
  $('uRolTxt').textContent = DB.usuario ? (DB.usuario.rol === 'admin' ? 'Administrador' : 'Técnico') : '';
}
function drawMarca() {
  const c = cfg(), img = $('brandImg'), src = c.logo || '/static/img/icon-192.png';
  if (img.getAttribute('src') !== src) img.setAttribute('src', src);
  img.style.objectFit = c.logo ? 'contain' : ''; $('brandName').textContent = c.taller || 'CRM Técnico';
  document.title = (c.taller || 'CRM Técnico') + ' · Órdenes';
}
/* se consulta cada 10 s; si volvió la conexión y se vació la cola, se recarga la lista */
setInterval(async () => {
  if (!DB.api) return;
  try {
    const prev = DB.sync, r = await DB.req('/api/estado'); DB.sync = await r.json();
    const cambio = prev && (!prev.online || prev.pendientes > 0) && DB.sync.online && DB.sync.pendientes === 0;
    if (cambio && !$('dOrd').open) { await DB.load(); render(); }
    drawModo();
  } catch (e) { /* sin servidor del CRM: se verá al intentar guardar */ }
}, 10000);
async function importarLocal() {
  const L = localOrders().sort((a, b) => (a.seq || 0) - (b.seq || 0));
  if (!confirm(`Se van a pasar ${L.length} órdenes a la base de datos. Reciben un número nuevo de secuencia. ¿Continuar?`)) return;
  for (const o of L) await DB.upsert({ ...norm(o), seq: undefined });
  try { localStorage.removeItem(DB.K); } catch (e) {}
  await DB.load(); render(); drawModo();
}
$('aviso').onclick = e => { if (e.target.id === 'bImp') importarLocal(); };

/* ---------- filtros ---------- */
function drawChips() {
  const L = DB.data.ordenes;
  $('chips').innerHTML = `<button class="chip ${quick ? '' : 'on'}" data-q="">Todas <b>${L.length}</b></button>` + Object.entries(QUICK).map(([k, [t, fn]]) => {
    const n = L.filter(fn).length;
    return n || quick === k ? `<button class="chip ${quick === k ? 'on' : ''}" data-q="${k}">${k === 'viejos' ? `Sin retirar más de ${alertaDias()} días` : t} <b>${n}</b></button>` : '';
  }).join('');
}
function filtrar() {
  const q = $('q').value.toLowerCase().trim(), f = $('fs').value, tf = $('fT').value, qf = quick ? QUICK[quick][1] : () => true;
  return DB.data.ordenes.filter(o => (!f || o.estado === f) && (!tf || o.tecnico === (tf === '@yo' ? yo() : tf)) && qf(o) &&
    (!q || sinAcentos(numOrden(o) + ' ' + o.cliente + ' ' + nombreEq(o) + ' ' + o.tel + ' ' + o.serie + ' ' + fallaTxt(o)).includes(sinAcentos(q))));
}
function ordenar(L) {
  const k = $('fO').value, by = {
    recientes: (a, b) => b.seq - a.seq, antiguas: (a, b) => a.seq - b.seq, saldo: (a, b) => saldo(b) - saldo(a),
    entrega: (a, b) => (a.entrega_est || '9999').localeCompare(b.entrega_est || '9999')
  };
  return [...L].sort(by[k] || by.recientes);
}
const opcTec = sel => '<option value=""></option>' + [...new Set([...DB.tecnicos, sel].filter(Boolean))].map(n => `<option>${esc(n)}</option>`).join('');
function drawTec() {
  const v = $('fT').value;
  $('fT').innerHTML = '<option value="">Todos los técnicos</option><option value="@yo">Mis órdenes</option>' + DB.tecnicos.map(n => `<option>${esc(n)}</option>`).join('');
  $('fT').value = v; $('fT').style.display = DB.tecnicos.length > 1 ? '' : 'none';
}
function llenarDL() {
  const m = new Map(); DB.data.ordenes.forEach(o => { if (o.tel && !m.has(normTel(o.tel))) m.set(normTel(o.tel), o); });
  $('dlTel').innerHTML = [...m.values()].map(o => `<option value="${esc(o.tel)}">${esc(o.cliente)}</option>`).join('');
  $('dlCli').innerHTML = [...new Set(DB.data.ordenes.map(o => o.cliente).filter(Boolean))].map(c => `<option value="${esc(c)}">`).join('');
}

/* ---------- una orden ---------- */
const ic = (n, t = '') => `<svg class="i"><use href="#i-${n}"/></svg>${t}`;
const fila_d = (k, v) => v ? `<dt>${k}</dt><dd>${v}</dd>` : '';
function detalle(o) {
  const g = garantiaHasta(o), costos = costoRep(o), imp = num(o.monto), tipo = tipoMsg(o);
  const esc_ = esc, hist = o.historial.slice(-4).reverse().map(h => `<div class="mut">${esc_(new Date(h.f).toLocaleDateString('es-AR'))}${h.u ? ', ' + esc_(h.u) : ''}: ${esc_(h.t)}</div>`).join('');
  const fotos = o.imagenes.length ? `<div class="imgs">${o.imagenes.map(s => s.startsWith('data:') ? `<img src="${s}" alt="foto">` : `<a href="${s}" target="_blank" rel="noopener"><img loading="lazy" decoding="async" src="${s}" alt="foto"></a>`).join('')}</div>` : '';
  const ent = ['Listo para retirar', 'Entregado'].includes(o.estado);
  return `<div class="det-g">
      <div><h4>Equipo y falla</h4><dl class="dl">${fila_d('Falla', esc_(fallaTxt(o)))}${fila_d('Diagnóstico', esc_(o.diagnostico))}${fila_d('Observaciones', esc_(o.observ))}
        ${fila_d('Checklist', o.checklist.map(esc_).join(', '))}${fila_d('Accesorios', esc_(o.accesorios))}${fila_d('Estado físico', esc_(o.fisico))}${fila_d('Serie', esc_(o.serie))}
        ${fila_d('Color', esc_(o.color))}${fila_d('Dirección', esc_(o.direccion))}${fila_d('Clave', esc_(o.clave))}</dl></div>
      <div><h4>Dinero y plazos</h4><dl class="dl">${imp ? fila_d('Presupuesto', `<span class="fig">${money(imp)}</span>`) : ''}${num(o.sena) ? fila_d('Seña', `<span class="fig">${money(num(o.sena))}</span>`) : ''}
        ${imp ? fila_d('Saldo', o.pagado ? '<span class="tag ok">Pagado</span>' : `<span class="fig">${money(saldo(o))}</span>`) : ''}
        ${costos ? fila_d('Repuestos', `<span class="fig">${money(costos)}</span>`) + (imp ? fila_d('Ganancia', `<span class="fig">${money(imp - costos)}</span>`) : '') : ''}
        ${o.entrega_est && o.estado !== 'Entregado' ? fila_d('Entrega estimada', fmtD(o.entrega_est)) : ''}${o.entrega_fecha ? fila_d('Entregada', fmtD(o.entrega_fecha)) : ''}
        ${g ? fila_d('Garantía', `<span class="tag ${g >= new Date() ? 'ok' : 'warn'}">${esc_(garTxt(o))}</span>`) : ''}</dl></div>
      <div><h4>Fotos e historial</h4>${fotos}<div style="margin-top:8px">${hist || '<span class="mut">Sin movimientos</span>'}</div></div>
    </div>
    <div class="acts">
      <button class="wa2" data-a="pdf" data-id="${o.id}">${ic('file', 'Comprobante PDF')}</button>
      ${ent ? `<button class="wa2" data-a="pdfe" data-id="${o.id}">${ic('file', 'Entrega PDF')}</button><button data-a="printe" data-id="${o.id}">${ic('print', 'Imprimir entrega')}</button>` : ''}
      <a class="wa wa2" data-log="texto" data-id="${o.id}" href="${waComp(o)}" target="_blank" rel="noopener">${ic('chat', 'Comprobante por texto')}</a>
      <button data-a="print" data-id="${o.id}">${ic('print', 'Imprimir')}</button>
      <button data-a="label" data-id="${o.id}">${ic('tag', 'Etiqueta')}</button>
      <button data-a="edit" data-id="${o.id}">${ic('edit', 'Editar')}</button>
      <button class="dg" data-a="del" data-id="${o.id}">${ic('trash', 'Borrar')}</button>
    </div>`;
}
function fila(o) {
  const i = Math.max(0, ESTADOS.indexOf(o.estado)), c = `var(--e${i + 1})`, tipo = tipoMsg(o), abierta = abiertas.has(o.id);
  const imp = num(o.monto), viejo = QUICK.viejos[1](o), dias = Math.floor(diasDesde(o.estado_fecha || o.creada));
  const sub = !imp ? '' : o.pagado ? '<span class="imp-s pag">Pagado</span>' : saldo(o) ? `<span class="imp-s deb">Debe ${money(saldo(o))}</span>` : '';
  const corto = { presupuesto: 'Presupuesto', listo: 'Avisar retiro', mensaje: 'WhatsApp' }[tipo];
  const wa_ = faltaPresu(o) ? `<button class="wa" data-a="falta" title="${LBL.presupuesto}">${ic('chat', 'Presupuesto')}</button>`
    : `<a class="wa" data-log="${tipo}" data-id="${o.id}" href="${waLink(o)}" target="_blank" rel="noopener" title="${LBL[tipo]}">${ic('chat', corto)}</a>`;
  return `<div class="orden${abierta ? ' abierta' : ''}">
    <div class="fila" data-id="${o.id}" role="button" tabindex="0" aria-expanded="${abierta}">
      <div class="c-n celda"><span class="num">${esc(numOrden(o))}</span><span class="avance" style="--c:${c}" title="Etapa ${i + 1} de ${ESTADOS.length}">${ESTADOS.map((_, k) => `<i class="${k <= i ? 'on' : ''}"></i>`).join('')}</span></div>
      <div class="c-c celda"><b>${esc(o.cliente)}</b><small>${esc(o.tel)}</small></div>
      <div class="c-q celda"><b>${esc(nombreEq(o)) || 'Sin equipo'}</b><small>${esc(o.serie ? 'Serie ' + o.serie : fallaTxt(o))}</small></div>
      <div class="c-e celda"><span class="est" style="--c:${c}">${esc(o.estado)}</span>${viejo ? `<span class="est-d">hace ${dias} días</span>` : ''}</div>
      <div class="c-f celda"><b>${esc(fechaOrd(o))}</b><small>${esc(o.tecnico)}</small></div>
      <div class="c-i celda r">${imp ? `<span class="imp">${money(imp)}</span>${sub}` : '<span class="imp-s">Sin presupuesto</span>'}</div>
      <div class="c-a acc">${wa_}<button class="exp" data-exp="1" aria-label="Ver detalle">${ic('chev')}</button></div>
    </div>
    <div class="det">${detalle(o)}</div>
  </div>`;
}

/* ---------- dibujo ---------- */
function renderLista() {
  drawChips(); drawMarca();
  const todas = ordenar(filtrar()), vistas = todas.slice(0, pagina * PAGE), total = DB.data.ordenes.length;
  $('list').innerHTML = vistas.length ? vistas.map(fila).join('')
    : total ? '<div class="empty"><b>Ninguna orden coincide</b>Probá con otra búsqueda o quitá los filtros.</div>'
      : '<div class="empty"><b>Todavía no hay órdenes</b>Cargá la primera con “Nueva orden”.</div>';
  $('cuenta').textContent = total ? (todas.length === total ? `(${total})` : `(${todas.length} de ${total})`) : '';
  $('masWrap').hidden = todas.length <= vistas.length; $('bMas').textContent = `Mostrar más (${todas.length - vistas.length} ${pl(todas.length - vistas.length, 'restante', 'restantes')})`;
  llenarDL();
}
function render() { drawDashboard(); renderLista(); if (vista === 'cli') renderClientes(); }

/* ---------- eventos ---------- */
$('list').onclick = async e => {
  const t = e.target, an = t.closest('a[data-log]');
  if (an) { const o = find(an.dataset.id); if (o) { await log(o, LOGT[an.dataset.log]); render(); } return; }
  const b = t.closest('[data-a]');
  if (b) {
    const o = find(b.dataset.id), a = b.dataset.a;
    if (a === 'falta') return alert('Para enviar el presupuesto cargá el diagnóstico y el monto (abrí la orden y tocá Editar).');
    if (a === 'pdf') return enviarPDF(o);
    if (a === 'pdfe') return enviarPDF(o, 'entrega');
    if (a === 'printe') return imprimir(o, 'entrega');
    if (a === 'print') return imprimir(o);
    if (a === 'label') return etiquetar(o);
    if (a === 'edit') return openOrd(o);
    if (a === 'del' && confirm('¿Borrar esta orden?')) { await DB.remove(o.id); abiertas.delete(o.id); render(); }
    return;
  }
  const f = t.closest('.fila'); if (f) alternar(f);
};
$('list').onkeydown = e => { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('fila')) { e.preventDefault(); alternar(e.target); } };
function alternar(f) {
  const el = f.parentElement, id = f.dataset.id, ab = !el.classList.contains('abierta');
  el.classList.toggle('abierta', ab); f.setAttribute('aria-expanded', ab); ab ? abiertas.add(id) : abiertas.delete(id);
}
$('chips').onclick = e => { const b = e.target.closest('[data-q]'); if (b) { quick = b.dataset.q; pagina = 1; renderLista(); } };
$('q').oninput = () => { if (vista === 'cli') { paginaCli = 1; renderClientes(); } else { pagina = 1; renderLista(); } };
for (const id of ['fs', 'fT', 'fO']) $(id).onchange = () => { pagina = 1; renderLista(); };
$('bMas').onclick = () => { pagina++; renderLista(); };
