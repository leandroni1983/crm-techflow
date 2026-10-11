/* ============ HELPERS ============ */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const p2 = n => String(n).padStart(2, '0');
const num = x => parseFloat(String(x ?? '').replace(',', '.')) || 0;
const money = x => '$ ' + Math.round(x).toLocaleString('es-AR');
const hoy = () => { const d = new Date(); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`; };
const ahora = () => new Date().toISOString();
const fmtD = s => s ? s.split('-').reverse().join('/') : '';
const cfg = () => DB.data.config;
const find = id => DB.data.ordenes.find(x => x.id === id);
const ESTADOS = ['Recibido', 'En diagnóstico', 'Presupuesto', 'Esperando repuesto', 'En reparación', 'Listo para retirar', 'Entregado'];
const nombreEq = o => [o.equipo, o.marca].filter(Boolean).join(' ');
const costoRep = o => o.repuestos.reduce((a, r) => a + num(r.costo), 0);
const diasDesde = iso => iso ? (Date.now() - new Date(iso).getTime()) / 864e5 : 0;

/* ============ NÚMERO DE ORDEN, TELÉFONO, MENSAJES ============ */
const numOrden = o => {
  const d = new Date(o.creada || Date.now());
  return cfg().prefijo + String(o.seq).padStart(4, '0') + p2(d.getDate()) + p2(d.getMonth() + 1) + p2(d.getFullYear() % 100);
};
function normTel(t) {
  let d = String(t || '').replace(/\D/g, '').replace(/^0+/, '');
  if (!d) return '';
  const p = cfg().pais;
  return (d.startsWith(p) || d.startsWith('54')) ? d : p + d;
}
const fill = (t, m) => t.replace(/{(\w+)}/g, (x, k) => k in m ? (m[k] || '-') : x);
const fechaOrd = o => new Date(o.creada || Date.now()).toLocaleDateString('es-AR');
const saldo = o => o.pagado ? 0 : Math.max(num(o.monto) - num(o.sena), 0);

function garantiaHasta(o) {
  const dias = parseInt(cfg().garantia_dias) || 0;
  if (!o.entrega_fecha || !dias) return null;
  const d = new Date(o.entrega_fecha + 'T12:00:00'); d.setDate(d.getDate() + dias); return d;
}
const enGarantia = o => { const g = garantiaHasta(o); return !!g && g >= new Date(); };
const garTxt = o => { const g = garantiaHasta(o); return g ? (g >= new Date() ? 'Garantía vigente hasta ' : 'Garantía vencida el ') + g.toLocaleDateString('es-AR') : ''; };

function vars(o) {
  const c = cfg();
  return { cliente: o.cliente, numero: numOrden(o), equipo: nombreEq(o), estado: o.estado, taller: c.taller, diagnostico: o.diagnostico,
    presupuesto: o.monto, saldo: money(saldo(o)), garantia: garTxt(o) || ' ', fecha: fechaOrd(o), serie: o.serie,
    accesorios: o.accesorios, fisico: o.fisico, falla: o.problema, condiciones: c.condiciones };
}
const wa = (o, txt) => 'https://wa.me/' + normTel(o.tel) + '?text=' + encodeURIComponent(txt);
const tipoMsg = o => o.estado === 'Presupuesto' ? 'presupuesto' : o.estado === 'Listo para retirar' ? 'listo' : 'mensaje';
const LBL = { presupuesto: 'Enviar presupuesto por WhatsApp', listo: 'Avisar: listo para retirar', mensaje: 'Enviar por WhatsApp' };
const LOGT = { presupuesto: 'Presupuesto enviado por WhatsApp', listo: 'Aviso "listo para retirar" enviado', mensaje: 'Mensaje enviado por WhatsApp', texto: 'Comprobante (texto) enviado por WhatsApp', pdf: 'Comprobante PDF enviado por WhatsApp', entrega: 'Comprobante de entrega enviado por WhatsApp' };
const plantilla = o => ({ presupuesto: cfg().msgP, listo: cfg().msgListo, mensaje: cfg().msg })[tipoMsg(o)];
const waLink = o => wa(o, fill(plantilla(o), vars(o)));
const waComp = o => wa(o, fill(cfg().msgC, vars(o)));
const faltaPresu = o => o.estado === 'Presupuesto' && (!num(o.monto) || !o.diagnostico.trim());
const yo = () => DB.usuario?.nombre || '';
async function log(o, t) { o.historial.push({ f: ahora(), t, n: true }); await DB.upsert(o); }

/* ============ COMPROBANTE: datos, QR, impresión, PDF ============ */
const chkItems = () => cfg().checklist_items.split(',').map(s => s.trim()).filter(Boolean);
function checklistTxt(o) {
  const items = [...new Set([...chkItems(), ...o.checklist])];
  return items.map(i => (o.checklist.includes(i) ? '[X] ' : '[  ] ') + i).join('   ');
}
function filasComp(o) {
  const v = vars(o), f = [];
  f.push(['Fecha', v.fecha + (o.hora ? ' ' + o.hora : '')], ['Cliente', o.cliente], ['Teléfono', o.tel]);
  if (o.direccion) f.push(['Dirección', o.direccion]);
  f.push(['Equipo', nombreEq(o)]);
  if (o.color) f.push(['Color', o.color]);
  f.push(['N° de serie', o.serie], ['Accesorios', o.accesorios],
    ['Estado físico', [o.fisico, o.deteriorado && 'Deteriorado: ' + o.deteriorado].filter(Boolean).join(' · ')]);
  if (o.garantia_fab) f.push(['Garantía de fábrica', o.garantia_fab]);
  f.push(['Falla informada', o.problema, true]);
  const ck = checklistTxt(o); if (ck) f.push(['Checklist de ingreso', ck, true]);
  if (o.observ) f.push(['Observaciones', o.observ, true]);
  if (o.entrega_est) f.push(['Entrega estimada', fmtD(o.entrega_est)]);
  if (num(o.autoriza)) f.push(['Reparación directa hasta', money(num(o.autoriza))]);
  if (num(o.monto)) f.push(['Presupuesto', money(num(o.monto))]);
  return f;
}
function filasEntrega(o) {
  const v = vars(o), f = [];
  f.push(['Fecha de entrega', o.entrega_fecha ? fmtD(o.entrega_fecha) : new Date().toLocaleDateString('es-AR')], ['Orden N°', v.numero]);
  f.push(['Cliente', o.cliente], ['Teléfono', o.tel], ['Equipo', nombreEq(o)], ['N° de serie', o.serie]);
  f.push(['Falla informada', o.problema, true], ['Trabajo realizado', o.diagnostico, true]);
  const reps = o.repuestos.map(r => r.desc).filter(Boolean).join(', '); if (reps) f.push(['Repuestos colocados', reps, true]);
  if (num(o.monto)) f.push(['Importe total', money(num(o.monto))]);
  if (num(o.sena)) f.push(['Seña abonada', money(num(o.sena))]);
  f.push(['Estado de pago', o.pagado ? 'Abonado en su totalidad' : (num(o.monto) ? 'Saldo pendiente: ' + money(saldo(o)) : '-')]);
  const dias = parseInt(cfg().garantia_dias) || 0, g = garantiaHasta({ ...o, entrega_fecha: o.entrega_fecha || hoy() });
  f.push(['Garantía', dias && g ? `${dias} días · vence el ${g.toLocaleDateString('es-AR')}` : 'Sin garantía', true]);
  return f;
}
async function qrSvg(text, px) {
  if (!DB.api) return '';
  try {
    const r = await DB.req('/api/qr?t=' + encodeURIComponent(text)); if (!r.ok) return '';
    const { n, rows } = await r.json(); let d = '';
    rows.forEach((row, y) => [...row].forEach((c, x) => { if (c === '1') d += `M${x + 2} ${y + 2}h1v1h-1z`; }));
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 ${n + 4} ${n + 4}" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="${d}"/></svg>`;
  } catch (e) { return ''; }
}
function printHTML(html, w, h, m = 8) {
  $('comp').innerHTML = html;
  let st = $('pgsize'); if (!st) { st = document.createElement('style'); st.id = 'pgsize'; document.head.appendChild(st); }
  st.textContent = `@page{size:${w}mm ${h}mm;margin:${m}mm}`;
  window.print();
}
async function imprimir(o, tipo = 'ingreso') {
  const c = cfg(), v = vars(o), q = await qrSvg(v.numero, 52), ent = tipo === 'entrega';
  const celdas = (ent ? filasEntrega(o) : filasComp(o)).map(([k, x, f]) => `<div class="${f || String(x || '').length > 38 ? 'f' : ''}"><small>${esc(k)}</small>${esc(x || '-')}</div>`).join('');
  const logo = c.logo ? `<img class="logo" src="${c.logo}">` : '';
  const nombre = c.logo && c.logo_solo === '1' ? '' : `<h1>${esc(c.taller)}</h1>`;
  const firma = ent ? o.firma_entrega : o.firma;
  printHTML(`<div class="hd"><div class="l">${logo}<div>${nombre}<div class="s">${ent ? 'Comprobante de entrega' : 'Comprobante de ingreso de equipo'}\n${esc(c.taller_datos)}</div></div></div>
    <div class="nb"><div><small>N° DE ORDEN</small><b>${esc(v.numero)}</b></div>${q}</div></div><div class="cg">${celdas}</div>
    <div class="ft"><p>${esc(ent ? c.condiciones_entrega : c.condiciones)}</p><div class="fm">${firma ? `<img src="${firma}">` : ''}${ent ? 'Recibí conforme' : 'Firma del cliente'}</div><div class="fm">Firma del taller</div></div>`,
    c.pdfAncho || 210, c.pdfAlto || 148);
}
async function etiquetar(o) {
  const c = cfg(), q = await qrSvg(numOrden(o), 80);
  printHTML(`<div class="et">${q}<div><b>${esc(numOrden(o))}</b><br>${esc(o.cliente)}<br>${esc(nombreEq(o))}<br>${esc(o.tel)}</div></div>`, c.et_ancho || 70, c.et_alto || 40, 2);
}
/* Genera el PDF en el servidor (queda también en comprobantes/), lo descarga y abre el chat del cliente. */
async function enviarPDF(o, tipo = 'ingreso') {
  const ent = tipo === 'entrega';
  if (!DB.api) { alert('El PDF se genera con el servidor (server.py). Por ahora se abre la hoja para imprimir / guardar como PDF.'); return imprimir(o, tipo); }
  const c = cfg(), v = vars(o), w = window.open('', '_blank');
  try {
    const r = await DB.req('/api/comprobante', { method: 'POST', body: JSON.stringify({
      numero: v.numero, taller: c.taller, taller_datos: c.taller_datos, logo: c.logo, logo_solo: c.logo_solo,
      filas: ent ? filasEntrega(o) : filasComp(o), titulo: ent ? 'Comprobante de entrega' : 'Comprobante de ingreso de equipo',
      sufijo: ent ? '-entrega' : '', firma_label: ent ? 'Recibí conforme' : 'Firma del cliente',
      condiciones: ent ? c.condiciones_entrega : c.condiciones, firma: ent ? o.firma_entrega : o.firma, fotos: ent ? [] : o.imagenes,
      ancho_mm: c.pdfAncho, alto_mm: c.pdfAlto }) });
    if (!r.ok) throw new Error('http ' + r.status);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await r.blob()); a.download = 'Orden-' + v.numero + (ent ? '-entrega' : '') + '.pdf'; a.click();
    if (w) w.location = wa(o, fill(ent ? c.msgEntrega : c.msgPDF, v));
    await log(o, ent ? LOGT.entrega : LOGT.pdf); render();
    alert('El PDF se descargó (y quedó en la carpeta "comprobantes").\nEn el chat de WhatsApp tocá el clip 📎 > Documento y adjuntalo.');
  } catch (e) { if (w) w.close(); alert('No se pudo generar el PDF. ¿Está corriendo server.py?'); }
}

/* ============ MODO DE GUARDADO / IMPORTAR DEL NAVEGADOR ============ */
function localOrders() { try { return (JSON.parse(localStorage.getItem(DB.K)) || {}).ordenes || []; } catch (e) { return []; } }
function drawModo() {
  const n = DB.api ? localOrders().length : 0, s = DB.sync || { online: true, pendientes: 0, errores: 0, motor: 'la base de datos' };
  const cola = s.pendientes ? ` · ${s.pendientes} cambio${s.pendientes > 1 ? 's' : ''} ${s.online ? 'sincronizándose…' : 'pendiente' + (s.pendientes > 1 ? 's' : '') + ' (se envían solos al volver la conexión)'}` : '';
  const err = s.errores ? ` · ✖ ${s.errores} cambio${s.errores > 1 ? 's' : ''} con error (avisá al administrador)` : '';
  $('modo').className = 'modo ' + (DB.api && s.online && !s.errores ? 'ok' : 'warn');
  $('modo').innerHTML = DB.api
    ? `<span>${s.online ? '●' : '⚠️'} ${s.online ? 'Base de datos: ' + esc(s.motor) : 'Sin conexión con la base de datos: trabajando en modo local'}${cola}${err} · 👤 ${esc(DB.usuario?.nombre || '')}</span>` + (n ? `<button id="bImp">Importar ${n} órdenes que quedaron en el navegador</button>` : '') + '<button id="bOut">Salir</button>'
    : '<span>⚠️ Modo navegador: los datos NO se guardan en la base. Ejecutá server.py y abrí http://localhost:8000 (el PDF y el QR necesitan el servidor)</span>';
}
/* Estado de sincronización: se consulta cada 10 s; si volvió la conexión y se vació la cola, se recarga la lista */
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
$('modo').onclick = async e => {
  if (e.target.id === 'bImp') importarLocal();
  if (e.target.id === 'bOut') { try { await fetch('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch (x) {} location.href = '/login'; }
};

/* ============ LISTA, FILTROS Y ACCESOS RÁPIDOS ============ */
let quick = '';
const alertaDias = () => parseInt(cfg().dias_alerta) || 7;
const QUICK = {
  dx: ['Para diagnosticar', o => o.estado === 'En diagnóstico'],
  pre: ['Presupuesto', o => o.estado === 'Presupuesto'],
  rep: ['Esperando repuesto', o => o.estado === 'Esperando repuesto'],
  listo: ['Listos para retirar', o => o.estado === 'Listo para retirar'],
  viejos: ['Sin retirar +días', o => o.estado === 'Listo para retirar' && diasDesde(o.estado_fecha || o.creada) > alertaDias()],
  gar: ['En garantía', enGarantia]
};
function drawChips() {
  const L = DB.data.ordenes;
  $('chips').innerHTML = `<button class="chip ${quick ? '' : 'on'}" data-q="">Todos (${L.length})</button>` + Object.entries(QUICK).map(([k, [t, fn]]) => {
    const n = L.filter(fn).length;
    return n || quick === k ? `<button class="chip ${quick === k ? 'on' : ''}" data-q="${k}">${k === 'viejos' ? `Sin retirar +${alertaDias()} días` : t} (${n})</button>` : '';
  }).join('');
}
function card(o) {
  const g = garantiaHasta(o), tipo = tipoMsg(o), costos = costoRep(o), viejo = QUICK.viejos[1](o);
  const dinero = [num(o.monto) && 'Presupuesto: ' + money(num(o.monto)), num(o.sena) && 'Seña: ' + money(num(o.sena)),
    num(o.monto) && (o.pagado ? '✅ Pagado' : 'Saldo: ' + money(saldo(o)))].filter(Boolean).join(' · ');
  const datos = [o.serie && 'S/N ' + esc(o.serie), o.color && esc(o.color), o.accesorios && 'Accesorios: ' + esc(o.accesorios), o.fisico && 'Físico: ' + esc(o.fisico)].filter(Boolean).join(' · ');
  return `<div class="card">
    <div class="row">
      <div><span class="num">${esc(numOrden(o))}</span> · ${esc(o.cliente)}<div class="mut">${esc(nombreEq(o))} · 📱 ${esc(o.tel)} · ${esc(fechaOrd(o))}${o.hora ? ' ' + esc(o.hora) : ''}${o.tecnico ? ' · 👷 ' + esc(o.tecnico) : ''}</div></div>
      <div><span class="tag ${viejo ? 'warn' : ''}">${esc(o.estado)}${viejo ? ' · +' + Math.floor(diasDesde(o.estado_fecha || o.creada)) + ' días' : ''}</span></div>
    </div>
    ${datos ? `<div class="mut ln">${datos}</div>` : ''}
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
      <button data-a="edit" data-id="${o.id}">Editar</button>
      <button class="dg" data-a="del" data-id="${o.id}">Borrar</button>
    </div></div>`;
}
function render() {
  drawChips();
  const q = $('q').value.toLowerCase(), f = $('fs').value, tf = $('fT').value, qf = quick ? QUICK[quick][1] : () => true;
  const L = DB.data.ordenes.filter(o => (!f || o.estado === f) && (!tf || o.tecnico === (tf === '@yo' ? yo() : tf)) && qf(o) &&
    (numOrden(o) + o.cliente + nombreEq(o) + o.tel + o.serie).toLowerCase().includes(q));
  $('list').innerHTML = L.length ? L.map(card).join('') : '<div class="empty">No hay órdenes para mostrar. Creá una con “+ Nueva orden”.</div>';
  llenarDL();
}
function llenarDL() {
  const m = new Map(); DB.data.ordenes.forEach(o => { if (o.tel && !m.has(normTel(o.tel))) m.set(normTel(o.tel), o); });
  $('dlTel').innerHTML = [...m.values()].map(o => `<option value="${esc(o.tel)}">${esc(o.cliente)}</option>`).join('');
  $('dlCli').innerHTML = [...new Set(DB.data.ordenes.map(o => o.cliente).filter(Boolean))].map(c => `<option value="${esc(c)}">`).join('');
}
$('list').onclick = async e => {
  const t = e.target, an = t.closest('a[data-log]');
  if (an) { const o = find(an.dataset.id); if (o) { await log(o, LOGT[an.dataset.log]); render(); } return; }
  const b = t.closest('[data-a]'); if (!b) return;
  const o = find(b.dataset.id), a = b.dataset.a;
  if (a === 'falta') return alert('Para enviar el presupuesto cargá el diagnóstico y el monto (botón Editar).');
  if (a === 'pdf') return enviarPDF(o);
  if (a === 'pdfe') return enviarPDF(o, 'entrega');
  if (a === 'printe') return imprimir(o, 'entrega');
  if (a === 'print') return imprimir(o);
  if (a === 'label') return etiquetar(o);
  if (a === 'edit') return openOrd(o);
  if (a === 'del' && confirm('¿Borrar esta orden?')) { await DB.remove(o.id); render(); }
};
$('chips').onclick = e => { const b = e.target.closest('[data-q]'); if (b) { quick = b.dataset.q; render(); } };
$('q').oninput = render; $('fs').onchange = render; $('fT').onchange = render;
const opcTec = sel => '<option value=""></option>' + [...new Set([...DB.tecnicos, sel].filter(Boolean))].map(n => `<option>${esc(n)}</option>`).join('');
function drawTec() {
  const v = $('fT').value;
  $('fT').innerHTML = '<option value="">Todos los técnicos</option><option value="@yo">Mis órdenes</option>' + DB.tecnicos.map(n => `<option>${esc(n)}</option>`).join('');
  $('fT').value = v; $('fT').style.display = DB.tecnicos.length > 1 ? '' : 'none';
}

/* ============ DIÁLOGO DE ORDEN ============ */
const CAMPOS = { cliente: 'fCli', tel: 'fTel', direccion: 'fDir', equipo: 'fEq', marca: 'fMa', color: 'fCo', serie: 'fSe', accesorios: 'fAc',
  fisico: 'fFi', deteriorado: 'fDe', tecnico: 'fTe', clave: 'fCl', garantia_fab: 'fGf', problema: 'fPr', observ: 'fOb', estado: 'fSt', hora: 'fHo',
  entrega_est: 'fEe', autoriza: 'fAu', diagnostico: 'fDx', monto: 'fMo', sena: 'fSn', entrega_fecha: 'fEf' };
let editing = null, tmpImgs = [], tmpRep = [], tmpLogo = '';

function compress(file, max = 800, q = .6) {
  return new Promise(res => {
    const r = new FileReader();
    r.onload = () => { const im = new Image(); im.onload = () => {
      const k = Math.min(1, max / Math.max(im.width, im.height)), c = document.createElement('canvas');
      c.width = Math.round(im.width * k); c.height = Math.round(im.height * k);
      const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height); x.drawImage(im, 0, 0, c.width, c.height);
      res(c.toDataURL('image/jpeg', q)); }; im.src = r.result; };
    r.readAsDataURL(file);
  });
}
function drawImgs() { $('fImgs').innerHTML = tmpImgs.map((s, i) => `<div class="x"><img src="${s}"><b data-x="${i}">×</b></div>`).join(''); }
function drawChk(sel) {
  const items = [...new Set([...chkItems(), ...sel])];
  $('fChk').innerHTML = items.length ? items.map(i => `<label><input type="checkbox" value="${esc(i)}" ${sel.includes(i) ? 'checked' : ''}> ${esc(i)}</label>`).join('') : '<span class="mut">Definí la lista en ⚙️</span>';
}
function totRep() {
  const t = tmpRep.reduce((a, r) => a + num(r.costo), 0), m = num($('fMo').value);
  $('fRepTot').textContent = t ? `Costo repuestos: ${money(t)}` + (m ? ` · Ganancia: ${money(m - t)}` : '') : '';
}
function drawRep() {
  $('fRep').innerHTML = tmpRep.map((r, i) => `<div class="rep"><input data-ri="${i}" data-k="desc" placeholder="Repuesto" value="${esc(r.desc)}"><input data-ri="${i}" data-k="costo" type="number" min="0" placeholder="Costo" value="${esc(r.costo)}"><button type="button" data-rd="${i}">×</button></div>`).join('');
  totRep();
}
const plantillas = () => cfg().plantillas.split('\n').map(l => l.split('|').map(s => s.trim())).filter(a => a[0]);
function relacionados(tel, id) { const k = normTel(tel); return k ? DB.data.ordenes.filter(x => x.id !== id && normTel(x.tel) === k) : []; }
function showCliHist() {
  const L = relacionados($('fTel').value, editing?.id);
  $('fCliHist').innerHTML = L.length ? `<b>${L.length} reparación(es) anterior(es):</b><br>` + L.slice(0, 5).map(x =>
    `${esc(numOrden(x))} · ${esc(nombreEq(x))} · ${esc(x.estado)}${enGarantia(x) ? ' · <b style="color:var(--wa)">⚠️ en garantía hasta ' + garantiaHasta(x).toLocaleDateString('es-AR') + '</b>' : ''}`).join('<br>') : '';
}

/* firmas en pantalla (ingreso y retiro) */
function mkPad(id) {
  const cv = $(id), cx = cv.getContext('2d'); let dib = false, val = '';
  const limpiar = () => { cx.fillStyle = '#fff'; cx.fillRect(0, 0, cv.width, cv.height); val = ''; };
  const pos = e => { const r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) * cv.width / r.width, y: (e.clientY - r.top) * cv.height / r.height }; };
  cv.addEventListener('pointerdown', e => { dib = true; cv.setPointerCapture(e.pointerId); const p = pos(e); cx.beginPath(); cx.moveTo(p.x, p.y); });
  cv.addEventListener('pointermove', e => { if (!dib) return; const p = pos(e); cx.lineWidth = 2.5; cx.lineCap = 'round'; cx.strokeStyle = '#000'; cx.lineTo(p.x, p.y); cx.stroke(); });
  const fin = () => { if (dib) { dib = false; val = cv.toDataURL('image/jpeg', .7); } };
  cv.addEventListener('pointerup', fin); cv.addEventListener('pointercancel', fin);
  limpiar();
  return { limpiar, get: () => val,
    set(u) { limpiar(); if (u) { const im = new Image(); im.onload = () => cx.drawImage(im, 0, 0, cv.width, cv.height); im.src = u; val = u; } } };
}
const pad1 = mkPad('fFirma'), pad2 = mkPad('fFirma2');
$('bFirmaClr').onclick = () => pad1.limpiar(); $('bFirma2Clr').onclick = () => pad2.limpiar();

function openOrd(o) {
  editing = o || null;
  const b = o || { ...ordenVacia(), tecnico: yo(), hora: `${p2(new Date().getHours())}:${p2(new Date().getMinutes())}` };
  $('dTitle').textContent = o ? 'Editar ' + numOrden(o) : 'Nueva orden';
  $('fTe').innerHTML = opcTec(b.tecnico);
  for (const [k, id] of Object.entries(CAMPOS)) $(id).value = b[k] || '';
  $('fSt').value = b.estado || ESTADOS[0]; $('fPg').checked = !!b.pagado;
  tmpImgs = [...b.imagenes]; tmpRep = b.repuestos.map(r => ({ ...r }));
  drawChk(b.checklist); drawRep(); drawImgs(); $('fImg').value = '';
  $('fPl').innerHTML = '<option value="">— elegir plantilla —</option>' + plantillas().map((p, i) => `<option value="${i}">${esc(p[0])}</option>`).join('');
  pad1.set(b.firma); pad2.set(b.firma_entrega);
  $('fsHist').style.display = o ? '' : 'none';
  $('fHist').innerHTML = [...b.historial].reverse().map(h => `${new Date(h.f).toLocaleString('es-AR')} — ${h.u ? '<b>' + esc(h.u) + '</b>: ' : ''}${esc(h.t)}`).join('<br>') || 'Sin movimientos';
  showCliHist(); $('dOrd').showModal();
}
$('bNew').onclick = () => openOrd();
$('bCan').onclick = () => $('dOrd').close();
$('fImg').onchange = async e => { for (const f of e.target.files) tmpImgs.push(await compress(f)); drawImgs(); };
$('fImgs').onclick = e => { if (e.target.dataset.x) { tmpImgs.splice(+e.target.dataset.x, 1); drawImgs(); } };
$('bRep').onclick = () => { tmpRep.push({ desc: '', costo: '' }); drawRep(); };
$('fRep').oninput = e => { const i = e.target.dataset.ri; if (i !== undefined) { tmpRep[i][e.target.dataset.k] = e.target.value; totRep(); } };
$('fRep').onclick = e => { if (e.target.dataset.rd !== undefined) { tmpRep.splice(+e.target.dataset.rd, 1); drawRep(); } };
$('fMo').oninput = totRep;
$('fPl').onchange = () => {
  const p = plantillas()[$('fPl').value]; if (!p) return;
  $('fDx').value = ($('fDx').value ? $('fDx').value + '\n' : '') + (p[1] || p[0]);
  if (p[2] && !num($('fMo').value)) $('fMo').value = p[2];
  $('fPl').value = ''; totRep();
};
$('fTel').onchange = () => {
  const L = relacionados($('fTel').value, editing?.id);
  if (L.length) { if (!$('fCli').value) $('fCli').value = L[0].cliente; if (!$('fDir').value) $('fDir').value = L[0].direccion; }
  showCliHist();
};
$('fCli').onchange = () => {
  const v = $('fCli').value.trim().toLowerCase(), m = DB.data.ordenes.find(x => x.cliente.toLowerCase() === v);
  if (m && !$('fTel').value) { $('fTel').value = m.tel; if (!$('fDir').value) $('fDir').value = m.direccion; }
  showCliHist();
};
$('bSave').onclick = async () => {
  if (!$('fCli').value.trim() || !$('fTel').value.trim()) return alert('Cliente y WhatsApp son obligatorios.');
  const o = { ...(editing || { id: 'o' + Date.now(), creada: ahora() }), historial: [...(editing?.historial || [])] };
  for (const [k, id] of Object.entries(CAMPOS)) o[k] = $(id).value.trim();
  o.pagado = $('fPg').checked ? '1' : '';
  o.checklist = [...$('fChk').querySelectorAll('input:checked')].map(i => i.value);
  o.repuestos = tmpRep.filter(r => r.desc || r.costo); o.imagenes = tmpImgs; o.firma = pad1.get(); o.firma_entrega = pad2.get();
  const H = t => o.historial.push({ f: ahora(), t, n: true });
  if (!editing) { o.estado_fecha = ahora(); H('Orden creada'); }
  else {
    if (editing.estado !== o.estado) { o.estado_fecha = ahora(); H(`Estado: ${editing.estado} → ${o.estado}`); }
    if ((editing.tecnico || '') !== o.tecnico) H(`Técnico: ${editing.tecnico || '—'} → ${o.tecnico || '—'}`);
  }
  if (o.estado === 'Entregado' && !o.entrega_fecha) o.entrega_fecha = hoy();
  if (await DB.upsert(o)) { $('dOrd').close(); render(); }
};

/* ============ CONFIGURACIÓN ============ */
const CFG = { taller: 'cNom', taller_datos: 'cDat', prefijo: 'cPre', pais: 'cPais', pdfAncho: 'cAncho', pdfAlto: 'cAlto', et_ancho: 'cEtA',
  et_alto: 'cEtH', garantia_dias: 'cGar', dias_alerta: 'cAle', checklist_items: 'cChk', plantillas: 'cPla', msg: 'cMsg', msgP: 'cMsgP',
  msgListo: 'cMsgL', msgPDF: 'cMsgPDF', msgC: 'cMsgC', condiciones: 'cCond', msgEntrega: 'cMsgE', condiciones_entrega: 'cCondE' };
function prevLogo() { const i = $('cLogoPrev'); i.style.display = tmpLogo ? 'block' : 'none'; i.src = tmpLogo || ''; }
$('bCfg').onclick = () => {
  const c = cfg(); for (const [k, id] of Object.entries(CFG)) $(id).value = c[k] ?? '';
  $('cLogoSolo').checked = c.logo_solo === '1'; tmpLogo = c.logo || ''; prevLogo();
  $('cLogo').value = ''; $('cPwA').value = ''; $('cPwN').value = ''; cuentas(); $('dCfg').showModal();
};
$('cLogo').onchange = async e => { if (e.target.files[0]) { tmpLogo = await compress(e.target.files[0], 400, .85); prevLogo(); } };
$('cLogoDel').onclick = () => { tmpLogo = ''; $('cLogo').value = ''; prevLogo(); };
$('cCan').onclick = () => $('dCfg').close();
$('cSave').onclick = async () => {
  const nc = { ...cfg() };
  for (const [k, id] of Object.entries(CFG)) nc[k] = $(id).value;
  nc.pais = nc.pais.replace(/\D/g, '') || '549';
  for (const k of ['pdfAncho', 'pdfAlto', 'et_ancho', 'et_alto', 'garantia_dias', 'dias_alerta']) nc[k] = nc[k] || DEFAULTS[k];
  nc.logo = tmpLogo; nc.logo_solo = $('cLogoSolo').checked ? '1' : '0';
  if (await DB.saveConfig(nc)) { $('dCfg').close(); render(); drawModo(); }
};

/* ---- cuenta y usuarios ---- */
async function api(path, method, body) {
  const r = await DB.req(path, { method, body: body ? JSON.stringify(body) : undefined });
  const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || 'Error'); return d;
}
async function cuentas() {
  const u = DB.usuario; $('cQuien').textContent = DB.api ? `Sesión: ${u?.nombre} (${u?.rol === 'admin' ? 'administrador' : 'técnico'})` : 'Sin servidor: no hay usuarios.';
  const admin = DB.api && u?.rol === 'admin'; $('cUsr').style.display = admin ? '' : 'none';
  if (!admin) return;
  try {
    const L = await api('/api/usuarios', 'GET'); DB.tecnicos = L.map(x => x.nombre); drawTec();
    $('cUsrList').innerHTML = L.map(x => `<div class="kv"><span>${esc(x.nombre)} <span class="mut">· ${x.rol === 'admin' ? 'administrador' : 'técnico'}</span></span>${x.nombre === u.nombre ? '<span class="mut">(vos)</span>' : `<button type="button" class="dg" data-ud="${esc(x.nombre)}">Borrar</button>`}</div>`).join('');
  } catch (e) { $('cUsrList').textContent = e.message; }
}
$('bPw').onclick = async () => {
  try { await api('/api/password', 'POST', { actual: $('cPwA').value, nueva: $('cPwN').value }); $('cPwA').value = ''; $('cPwN').value = ''; alert('Contraseña actualizada. Se cerraron tus otras sesiones.'); }
  catch (e) { alert(e.message); }
};
$('bUAdd').onclick = async () => {
  try { await api('/api/usuarios', 'POST', { nombre: $('uNom').value, password: $('uPw').value, rol: $('uRol').value }); $('uNom').value = ''; $('uPw').value = ''; cuentas(); }
  catch (e) { alert(e.message); }
};
$('cUsrList').onclick = async e => {
  const n = e.target.dataset.ud; if (!n || !confirm(`¿Borrar el usuario ${n}?`)) return;
  try { await api('/api/usuarios/' + encodeURIComponent(n), 'DELETE'); cuentas(); } catch (x) { alert(x.message); }
};

/* ============ RESUMEN DEL MES Y EXPORTAR ============ */
const ym = iso => { const d = new Date(iso); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}`; };
const STOP = new Set(['para', 'pero', 'como', 'esta', 'este', 'tiene', 'cuando', 'desde', 'porque', 'sale', 'queda', 'solo', 'sino', 'algo', 'muy', 'con', 'sin', 'una', 'uno', 'que', 'los', 'las', 'del', 'por']);
function topN(arr, n = 5) { const m = {}; arr.forEach(x => m[x] = (m[x] || 0) + 1); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n); }
function resumen() {
  const m = $('rMes').value, L = DB.data.ordenes;
  const ing = L.filter(o => ym(o.creada) === m), ent = L.filter(o => (o.entrega_fecha || '').slice(0, 7) === m);
  const fact = ent.reduce((a, o) => a + num(o.monto), 0), cost = ent.reduce((a, o) => a + costoRep(o), 0);
  const kv = (k, v) => `<div class="kv"><span>${k}</span><b>${v}</b></div>`;
  const lista = a => a.length ? a.map(([k, n]) => kv(esc(k), n)).join('') : '<div class="mut">Sin datos</div>';
  const palabras = ing.flatMap(o => (o.problema + ' ' + o.diagnostico).toLowerCase().match(/[a-záéíóúñ]{4,}/g) || []).filter(w => !STOP.has(w));
  $('rOut').innerHTML = kv('Órdenes ingresadas', ing.length) + kv('Equipos entregados', ent.length) + kv('Facturado (entregados)', money(fact)) +
    kv('Costo de repuestos', money(cost)) + kv('Ganancia', money(fact - cost)) +
    '<h4 style="margin:14px 0 4px">Por estado (ingresadas)</h4>' + lista(topN(ing.map(o => o.estado), 7)) +
    '<h4 style="margin:14px 0 4px">Órdenes por técnico</h4>' + lista(topN(ing.map(o => o.tecnico || '(sin asignar)'))) +
    '<h4 style="margin:14px 0 4px">Equipos más frecuentes</h4>' + lista(topN(ing.map(nombreEq).filter(Boolean).map(s => s.toLowerCase())) ) +
    '<h4 style="margin:14px 0 4px">Fallas más comunes (palabras)</h4>' + lista(topN(palabras));
}
$('bRes').onclick = () => { if (!$('rMes').value) { const d = new Date(); $('rMes').value = `${d.getFullYear()}-${p2(d.getMonth() + 1)}`; } resumen(); $('dRes').showModal(); };
$('rMes').onchange = resumen; $('rCerrar').onclick = () => $('dRes').close();
$('bCsv').onclick = () => {
  const cols = [['N° orden', numOrden], ['Fecha ingreso', fechaOrd], ['Cliente', o => o.cliente], ['Teléfono', o => o.tel], ['Equipo', o => o.equipo],
    ['Marca', o => o.marca], ['N° de serie', o => o.serie], ['Estado', o => o.estado], ['Técnico', o => o.tecnico], ['Falla', o => o.problema], ['Diagnóstico', o => o.diagnostico],
    ['Presupuesto', o => num(o.monto)], ['Seña', o => num(o.sena)], ['Pagado', o => o.pagado ? 'Sí' : 'No'], ['Costo repuestos', costoRep],
    ['Ganancia', o => num(o.monto) - costoRep(o)], ['Fecha entrega', o => fmtD(o.entrega_fecha)], ['Garantía hasta', o => { const g = garantiaHasta(o); return g ? g.toLocaleDateString('es-AR') : ''; }]];
  const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  const csv = '\ufeff' + [cols.map(c => q(c[0])).join(';'), ...DB.data.ordenes.map(o => cols.map(c => q(c[1](o))).join(';'))].join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = 'ordenes-' + hoy() + '.csv'; a.click();
};

/* ============ INICIO ============ */
(async () => {
  $('fSt').innerHTML = ESTADOS.map(s => `<option>${s}</option>`).join('');
  $('fs').innerHTML = '<option value="">Todos los estados</option>' + ESTADOS.map(s => `<option>${s}</option>`).join('');
  if (await DB.load() === 'login') return;
  drawTec(); render(); drawModo();
})();

/* ============ PWA ============ */
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
let instalar = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); instalar = e; $('bInst').hidden = false; });
$('bInst').onclick = async () => { if (!instalar) return; instalar.prompt(); await instalar.userChoice; instalar = null; $('bInst').hidden = true; };
window.addEventListener('appinstalled', () => { $('bInst').hidden = true; });
