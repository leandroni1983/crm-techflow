/* ============ ÓRDENES: MENSAJES, COMPROBANTES, FORMULARIO Y PAPELERA ============
   Todo lo que gira alrededor de una orden: armar los mensajes de WhatsApp, imprimir/exportar comprobantes,
   el diálogo de alta y edición, y el borrado recuperable (papelera). */
import { $, esc, p2, num, money, hoy, ahora, fmtD, fmtDT, cantR, ESTADOS, fill, compress } from './util.js';
import { DB, ordenVacia } from './db.js';
import { cfg, yo, nombreEq, fechaOrd, saldo, numOrden, normTel, opcTec, log, repCat, repDisp, segLink, refrescar } from './comun.js';
import { fallas, equipos, detectarFalla, detectarEquipo } from './cat.js';

/* ---- garantía ---- */
export function garantiaHasta(o) {
  const dias = parseInt(cfg().garantia_dias) || 0;
  if (!o.entrega_fecha || !dias) return null;
  const d = new Date(o.entrega_fecha + 'T12:00:00'); d.setDate(d.getDate() + dias); return d;
}
export const enGarantia = o => { const g = garantiaHasta(o); return !!g && g >= new Date(); };
export const garTxt = o => { const g = garantiaHasta(o); return g ? (g >= new Date() ? 'Garantía vigente hasta ' : 'Garantía vencida el ') + g.toLocaleDateString('es-AR') : ''; };

/* ---- mensajes de WhatsApp ---- */
function vars(o) {
  const c = cfg();
  return { cliente: o.cliente, numero: numOrden(o), equipo: nombreEq(o), estado: o.estado, taller: c.taller, diagnostico: o.diagnostico,
    presupuesto: o.monto, saldo: money(saldo(o)), garantia: garTxt(o) || ' ', fecha: fechaOrd(o), serie: o.serie,
    accesorios: o.accesorios, fisico: o.fisico, falla: o.problema, condiciones: c.condiciones, seguimiento: segLink(o) || ' ' };
}
const wa = (o, txt) => 'https://wa.me/' + normTel(o.tel) + '?text=' + encodeURIComponent(txt);
export const tipoMsg = o => o.estado === 'Presupuesto' ? 'presupuesto' : o.estado === 'Listo para retirar' ? 'listo' : 'mensaje';
export const LBL = { presupuesto: 'Enviar presupuesto por WhatsApp', listo: 'Avisar: listo para retirar', mensaje: 'Enviar por WhatsApp' };
export const LOGT = { presupuesto: 'Presupuesto enviado por WhatsApp', listo: 'Aviso "listo para retirar" enviado', mensaje: 'Mensaje enviado por WhatsApp', texto: 'Comprobante (texto) enviado por WhatsApp', pdf: 'Comprobante PDF enviado por WhatsApp', entrega: 'Comprobante de entrega enviado por WhatsApp' };
const plantilla = o => ({ presupuesto: cfg().msgP, listo: cfg().msgListo, mensaje: cfg().msg })[tipoMsg(o)];
export const waLink = o => wa(o, fill(plantilla(o), vars(o)));
export const waComp = o => wa(o, fill(cfg().msgC, vars(o)));
export const faltaPresu = o => o.estado === 'Presupuesto' && (!num(o.monto) || !o.diagnostico.trim());

/* ---- comprobante: datos, QR, impresión, PDF ---- */
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
export async function imprimir(o, tipo = 'ingreso') {
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
export async function etiquetar(o) {
  const c = cfg(), q = await qrSvg(numOrden(o), 80);
  printHTML(`<div class="et">${q}<div><b>${esc(numOrden(o))}</b><br>${esc(o.cliente)}<br>${esc(nombreEq(o))}<br>${esc(o.tel)}</div></div>`, c.et_ancho || 70, c.et_alto || 40, 2);
}
/* Genera el PDF en el servidor (queda también en comprobantes/), lo descarga y abre el chat del cliente. */
export async function enviarPDF(o, tipo = 'ingreso') {
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
    await log(o, ent ? LOGT.entrega : LOGT.pdf); refrescar();
    alert('El PDF se descargó (y quedó en la carpeta "comprobantes").\nEn el chat de WhatsApp tocá el clip 📎 > Documento y adjuntalo.');
  } catch (e) { if (w) w.close(); alert('No se pudo generar el PDF. ¿Está corriendo server.py?'); }
}

/* ============ DIÁLOGO DE ORDEN ============ */
const CAMPOS = { cliente: 'fCli', tel: 'fTel', direccion: 'fDir', equipo: 'fEq', equipo_tipo: 'fEt', marca: 'fMa', color: 'fCo', serie: 'fSe', accesorios: 'fAc',
  fisico: 'fFi', deteriorado: 'fDe', tecnico: 'fTe', clave: 'fCl', falla_tipo: 'fFt', garantia_fab: 'fGf', problema: 'fPr', observ: 'fOb', estado: 'fSt', hora: 'fHo',
  entrega_est: 'fEe', autoriza: 'fAu', diagnostico: 'fDx', monto: 'fMo', sena: 'fSn', entrega_fecha: 'fEf' };
let editing = null, tmpImgs = [], tmpRep = [];

function drawImgs() { $('fImgs').innerHTML = tmpImgs.map((s, i) => `<div class="x"><img src="${s}"><b data-x="${i}">×</b></div>`).join(''); }
function drawChk(sel) {
  const items = [...new Set([...chkItems(), ...sel])];
  $('fChk').innerHTML = items.length ? items.map(i => `<label><input type="checkbox" value="${esc(i)}" ${sel.includes(i) ? 'checked' : ''}> ${esc(i)}</label>`).join('') : '<span class="mut">Definí la lista en ⚙️</span>';
}
function totRep() {
  const t = tmpRep.reduce((a, r) => a + num(r.costo) * cantR(r), 0), m = num($('fMo').value);
  $('fRepTot').textContent = t ? `Costo repuestos: ${money(t)}` + (m ? ` · Ganancia: ${money(m - t)}` : '') : '';
}
function drawRep() {
  $('fRep').innerHTML = tmpRep.map((r, i) => `<div class="rep"><input data-ri="${i}" data-k="desc" placeholder="Repuesto" value="${esc(r.desc)}"><input data-ri="${i}" data-k="cant" type="number" min="1" placeholder="Cant." value="${cantR(r)}"><input data-ri="${i}" data-k="costo" type="number" min="0" placeholder="Costo" value="${esc(r.costo)}"><button type="button" data-rd="${i}">×</button></div>`).join('');
  totRep();
}
/* Desplegable del inventario dentro de la orden (descuenta lo que ya está puesto en otras órdenes). */
function drawRepCat() {
  const L = repCat();
  $('fRepCat').style.display = L.length ? '' : 'none';
  $('fRepCat').innerHTML = '<option value="">— del inventario —</option>' +
    L.map(it => `<option value="${esc(it.id)}">${esc(it.nombre)} (disp. ${repDisp(it, editing, tmpRep)})</option>`).join('');
}
const plantillas = () => cfg().plantillas.split('\n').map(l => l.split('|').map(s => s.trim())).filter(a => a[0]);
function relacionados(tel, id) { const k = normTel(tel); return k ? DB.ordenes.filter(x => x.id !== id && normTel(x.tel) === k) : []; }
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

let ftManual = false, etManual = false;   // el técnico eligió el tipo a mano: no lo pisamos con la sugerencia
export function openOrd(o) {
  editing = o || null;
  const b = o || { ...ordenVacia(), tecnico: yo(), hora: `${p2(new Date().getHours())}:${p2(new Date().getMinutes())}` };
  $('dTitle').textContent = o ? 'Editar ' + numOrden(o) : 'Nueva orden';
  $('fTe').innerHTML = opcTec(b.tecnico);
  for (const [k, id] of Object.entries(CAMPOS)) $(id).value = b[k] || '';
  ftManual = !!b.falla_tipo; etManual = !!b.equipo_tipo;
  $('fSt').value = b.estado || ESTADOS[0]; $('fPg').checked = !!b.pagado;
  tmpImgs = [...b.imagenes]; tmpRep = b.repuestos.map(r => ({ ...r }));
  drawChk(b.checklist); drawRep(); drawRepCat(); drawImgs(); $('fImg').value = '';
  $('fPl').innerHTML = '<option value="">— elegir plantilla —</option>' + plantillas().map((p, i) => `<option value="${i}">${esc(p[0])}</option>`).join('');
  pad1.set(b.firma); pad2.set(b.firma_entrega);
  $('fsHist').style.display = o ? '' : 'none';
  $('fHist').innerHTML = [...b.historial].reverse().map(h => `${new Date(h.f).toLocaleString('es-AR')} — ${h.u ? '<b>' + esc(h.u) + '</b>: ' : ''}${esc(h.t)}`).join('<br>') || 'Sin movimientos';
  showCliHist(); $('dOrd').showModal();
}
$('bNew').onclick = () => openOrd();
$('bNew2').onclick = () => openOrd();
$('fFt').onchange = () => { ftManual = true; };
$('fPr').oninput = () => { if (ftManual) return; const c = detectarFalla($('fPr').value); if (c && fallas().includes(c)) $('fFt').value = c; };
$('fEt').onchange = () => { etManual = true; };
$('fEq').oninput = () => { if (etManual) return; const c = detectarEquipo($('fEq').value); if (c && equipos().includes(c)) $('fEt').value = c; };
$('bCan').onclick = () => $('dOrd').close();
$('fImg').onchange = async e => { for (const f of e.target.files) tmpImgs.push(await compress(f)); drawImgs(); };
$('fImgs').onclick = e => { if (e.target.dataset.x) { tmpImgs.splice(+e.target.dataset.x, 1); drawImgs(); } };
$('bRep').onclick = () => { tmpRep.push({ desc: '', cant: '1', costo: '' }); drawRep(); };
$('fRep').oninput = e => { const i = e.target.dataset.ri; if (i !== undefined) { tmpRep[i][e.target.dataset.k] = e.target.value; totRep(); } };
$('fRep').onclick = e => { if (e.target.dataset.rd !== undefined) { tmpRep.splice(+e.target.dataset.rd, 1); drawRep(); } };
$('fMo').oninput = totRep;
$('fRepCat').onchange = () => {
  const it = repCat().find(x => x.id === $('fRepCat').value); $('fRepCat').value = '';
  if (!it) return;
  tmpRep.push({ desc: it.nombre, cant: '1', costo: it.costo || '', rid: it.id }); drawRep();
};
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
  const v = $('fCli').value.trim().toLowerCase(), m = DB.ordenes.find(x => x.cliente.toLowerCase() === v);
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
  if (await DB.upsert(o)) { $('dOrd').close(); refrescar(); }
};

/* ---- papelera (borrado recuperable) ---- */
export function drawPapelera() {
  const L = DB.data.ordenes.filter(o => o.borrada).sort((a, b) => String(b.borrada).localeCompare(String(a.borrada)));
  $('cPapelList').innerHTML = L.length
    ? L.map(o => `<div class="kv">
        <span>${esc(numOrden(o))} · ${esc(o.cliente)}<span class="mut"> · ${esc(fmtDT(o.borrada))}</span></span>
        <span><button type="button" data-res="${esc(o.id)}">Recuperar</button> <button type="button" class="dg" data-pur="${esc(o.id)}">Borrar definitivo</button></span>
      </div>`).join('')
    : '<div class="mut">Vacía. Acá aparecen las órdenes borradas, para recuperarlas si fue un error.</div>';
  $('bVaciar').disabled = !L.length;
}
export async function aPapelera(o) {
  if (!confirm(`¿Mandar la orden ${numOrden(o)} a la papelera? Se puede recuperar desde Configuración.`)) return;
  o.borrada = ahora();
  o.historial.push({ f: ahora(), t: 'Enviada a la papelera', n: true });
  if (await DB.upsert(o)) { refrescar(); drawPapelera(); }
}
async function recuperarOrden(o) {
  o.borrada = '';
  o.historial.push({ f: ahora(), t: 'Recuperada de la papelera', n: true });
  if (await DB.upsert(o)) { refrescar(); drawPapelera(); }
}
export async function purgarOrden(o) {
  if (!confirm(`¿Borrar PARA SIEMPRE la orden ${numOrden(o)} y sus fotos? No se puede deshacer.`)) return;
  if (await DB.remove(o.id)) { refrescar(); drawPapelera(); }
}
$('cPapelList').onclick = async e => {
  const r = e.target.closest('[data-res]'), p = e.target.closest('[data-pur]');
  if (r) return recuperarOrden(DB.data.ordenes.find(o => o.id === r.dataset.res));
  if (p) return purgarOrden(DB.data.ordenes.find(o => o.id === p.dataset.pur));
};
