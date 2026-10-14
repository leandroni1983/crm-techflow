/* ============ CONFIGURACIÓN ============
   Datos del taller, usuarios, inventario de repuestos, renombre de categorías y respaldo.
   Lo que solo puede tocar el administrador (fallas, equipos, repuestos, papelera, respaldo) se oculta al técnico
   en la pantalla y además el servidor lo rechaza. */
import { $, esc, num, money, hoy, ahora, fmtDT, compress } from './util.js';
import { DB, DEFAULTS } from './db.js';
import { cfg, yo, repCat, repDisp, repAlerta, refrescar, refrescarModo } from './comun.js';
import { listaFallas, listaEquipos, drawFallas, drawEquipos } from './cat.js';
import { drawPapelera, purgarOrden } from './orden.js';
import { drawTec } from './lista.js';

const CFG = { taller: 'cNom', taller_datos: 'cDat', prefijo: 'cPre', pais: 'cPais', pdfAncho: 'cAncho', pdfAlto: 'cAlto', et_ancho: 'cEtA',
  et_alto: 'cEtH', garantia_dias: 'cGar', dias_alerta: 'cAle', checklist_items: 'cChk', plantillas: 'cPla', msg: 'cMsg', msgP: 'cMsgP',
  msgListo: 'cMsgL', msgPDF: 'cMsgPDF', msgC: 'cMsgC', condiciones: 'cCond', msgEntrega: 'cMsgE', condiciones_entrega: 'cCondE', fallas: 'cFallas',
  equipos: 'cEquipos', url_publica: 'cUrlPub' };
const ADMIN_CFG = ['fallas', 'equipos', 'repuestos', 'ocultar_importes', 'perm_borrar_admin'];   // claves de configuración que solo puede cambiar el administrador
const esAdmin = () => DB.api && DB.usuario?.rol === 'admin';
let tmpLogo = '';
function prevLogo() { const i = $('cLogoPrev'); i.style.display = tmpLogo ? 'block' : 'none'; i.src = tmpLogo || ''; }
$('bCfg').onclick = () => {
  const c = cfg(); for (const [k, id] of Object.entries(CFG)) $(id).value = c[k] ?? '';
  $('cLogoSolo').checked = c.logo_solo === '1';
  $('cOcultarImp').checked = c.ocultar_importes === '1';
  $('cPermBorrar').checked = c.perm_borrar_admin === '1' || c.perm_borrar_admin === '' || c.perm_borrar_admin === undefined;
  tmpLogo = c.logo || ''; prevLogo();
  $('cLogo').value = ''; $('cPwA').value = ''; $('cPwN').value = ''; cuentas(); drawRenombres(); drawPapelera();
  if (esAdmin()) { abrirInv(); verAuditoria(); } $('dCfg').showModal();
};
$('cLogo').onchange = async e => { if (e.target.files[0]) { tmpLogo = await compress(e.target.files[0], 400, .85); prevLogo(); } };
$('cLogoDel').onclick = () => { tmpLogo = ''; $('cLogo').value = ''; prevLogo(); };
$('cCan').onclick = () => $('dCfg').close();
$('cSave').onclick = async () => {
  const nc = { ...cfg() };
  for (const [k, id] of Object.entries(CFG)) nc[k] = $(id).value;
  if (nc.fallas) nc.fallas = listaFallas(nc.fallas).join('\n');
  if (nc.equipos) nc.equipos = listaEquipos(nc.equipos).join('\n');
  if (invDibujada) nc.repuestos = JSON.stringify(leerInv());
  for (const k of ADMIN_CFG) if (!esAdmin()) delete nc[k];   // el técnico no manda las claves de administrador
  nc.pais = nc.pais.replace(/\D/g, '') || '549';
  for (const k of ['pdfAncho', 'pdfAlto', 'et_ancho', 'et_alto', 'garantia_dias', 'dias_alerta']) nc[k] = nc[k] || DEFAULTS[k];
  nc.logo = tmpLogo; nc.logo_solo = $('cLogoSolo').checked ? '1' : '0';
  nc.ocultar_importes = $('cOcultarImp').checked ? '1' : '0';
  nc.perm_borrar_admin = $('cPermBorrar').checked ? '1' : '0';
  if (await DB.saveConfig(nc)) { $('dCfg').close(); invDibujada = false; drawFallas(); drawEquipos(); refrescar(); refrescarModo(); }
};

/* ---- cuenta y usuarios ---- */
async function api(path, method, body) {
  const r = await DB.req(path, { method, body: body ? JSON.stringify(body) : undefined });
  const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || 'Error'); return d;
}
async function cuentas() {
  const u = DB.usuario; $('cQuien').textContent = DB.api ? `Sesión: ${u?.nombre} (${u?.rol === 'admin' ? 'administrador' : 'técnico'})` : 'Sin servidor: no hay usuarios.';
  const admin = DB.api && u?.rol === 'admin'; $('cUsr').style.display = admin ? '' : 'none'; $('cFall').style.display = admin ? '' : 'none';
  $('cEqu').style.display = admin ? '' : 'none';
  $('cPapel').style.display = admin ? '' : 'none';
  $('cInv').style.display = admin ? '' : 'none';
  $('cAud').style.display = admin ? '' : 'none';
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

/* ---- auditoría global (solo administrador): quién hizo qué y cuándo ---- */
async function verAuditoria() {
  if (!esAdmin()) return;
  $('cAudMsg').textContent = 'Cargando…';
  try { const d = await api('/api/auditoria?limit=300', 'GET'); dibujarAud(d.movimientos || []); $('cAudMsg').textContent = ''; }
  catch (e) { $('cAudList').innerHTML = ''; $('cAudMsg').textContent = e.message; }
}
function dibujarAud(L) {
  $('cAudList').innerHTML = L.length
    ? L.map(x => `<div class="kv"><span><span class="mut">${esc(x.fecha ? new Date(x.fecha).toLocaleString('es-AR') : '')}</span> · <b>${esc(x.usuario)}</b> · ${esc(x.accion)}${x.detalle ? ' <span class="mut">— ' + esc(x.detalle) + '</span>' : ''}</span></div>`).join('')
    : '<div class="mut">Sin movimientos registrados todavía.</div>';
}
$('bAudVer').onclick = verAuditoria;

/* ---- inventario: edición del catálogo (solo administrador) ---- */
let catTmp = [], invDibujada = false;
const nuevoIdRep = () => 'r' + Math.random().toString(36).slice(2, 8);
function invFila(it, i) {
  const d = repDisp(it), bajo = d <= num(it.minimo), nmov = (it.movs || []).length;
  return `<div class="rep inv" data-inv="${i}" data-inv-id="${esc(it.id)}">
    <input data-ik="nombre" placeholder="Repuesto" value="${esc(it.nombre)}">
    <input data-ik="stock" type="number" min="0" placeholder="Stock" value="${esc(it.stock)}">
    <input data-ik="minimo" type="number" min="0" placeholder="Mínimo" value="${esc(it.minimo)}">
    <input data-ik="costo" type="number" min="0" placeholder="Costo" value="${esc(it.costo)}">
    <span class="mut${bajo ? ' bajo' : ''}">disp. ${d}${bajo ? ' · reponer' : ''}</span>
    <button type="button" data-imov="${esc(it.id)}" title="Movimientos de inventario (kardex)">Movs${nmov ? ' (' + nmov + ')' : ''}</button>
    <button type="button" data-idel="${i}" title="Quitar del inventario">×</button></div>`;
}
function drawInv() {
  invDibujada = true;
  const L = catTmp;
  $('cInvList').innerHTML = L.length ? L.map(invFila).join('') : '<div class="mut">Todavía no cargaste repuestos. Los que agregues acá aparecen al cargar una orden y se descuentan solos al usarlos.</div>';
  $('cInvAlerta').textContent = repAlerta();
}
function abrirInv() { catTmp = repCat().map(x => ({ ...x })); drawInv(); }
const leerInv = () => [...$('cInvList').querySelectorAll('[data-inv]')].map(d => ({
  id: d.dataset.invId, nombre: d.querySelector('[data-ik="nombre"]').value.trim(), stock: d.querySelector('[data-ik="stock"]').value,
  minimo: d.querySelector('[data-ik="minimo"]').value, costo: d.querySelector('[data-ik="costo"]').value,
  movs: ((catTmp.find(x => x.id === d.dataset.invId) || {}).movs) || []
})).filter(it => it.nombre);
$('bInvAdd').onclick = () => { catTmp = leerInv(); catTmp.push({ id: nuevoIdRep(), nombre: '', stock: '', minimo: '', costo: '', movs: [] }); drawInv(); };
$('cInvList').onclick = e => {
  const b = e.target.closest('[data-idel]');
  if (b) { catTmp = leerInv().filter((_, i) => i !== +b.dataset.idel); drawInv(); return; }
  const m = e.target.closest('[data-imov]'); if (m) abrirMov(m.dataset.imov, leerInv());
};
$('cInvList').oninput = e => {
  const fila = e.target.closest('[data-inv]'); if (!fila) return;
  const it = leerInv()[+fila.dataset.inv]; if (!it) return;
  const d = repDisp(it), bajo = d <= num(it.minimo), sp = fila.querySelector('.mut');
  sp.textContent = `disp. ${d}` + (bajo ? ' · reponer' : ''); sp.className = 'mut' + (bajo ? ' bajo' : '');
  const bajos = leerInv().filter(x => repDisp(x) <= num(x.minimo));
  $('cInvAlerta').textContent = bajos.length ? `⚠️ Para reponer: ${bajos.map(x => x.nombre).join(', ')}` : '';
};

/* ---- kardex: entradas y ajustes de stock con historial (solo administrador) ---- */
let movId = null;
const movActual = () => catTmp.find(x => x.id === movId);
function drawMov() {
  const it = movActual(); if (!it) return;
  $('dMovNom').textContent = it.nombre || '(sin nombre)';
  $('dMovStock').textContent = `Stock actual: ${num(it.stock)} · mínimo ${num(it.minimo)} · la disponibilidad real descuenta lo usado en órdenes activas.`;
  const L = [...(it.movs || [])].reverse();
  $('mList').innerHTML = L.length
    ? L.map(m => `<div class="kv"><span><b>${m.tipo === 'entrada' ? '+' : '= '}${esc(m.cant)}</b> · ${m.tipo === 'entrada' ? 'entrada' : 'ajuste'}${m.nota ? ' · ' + esc(m.nota) : ''}<span class="mut"> · ${esc(fmtDT(m.f))}${m.u ? ' · ' + esc(m.u) : ''}</span></span></div>`).join('')
    : '<div class="mut">Sin movimientos. Las entradas suman stock (compras); los ajustes fijan el stock al valor contado.</div>';
}
function abrirMov(id, items) {
  catTmp = items; movId = id; $('mCant').value = ''; $('mNota').value = ''; $('mTipo').value = 'entrada';
  drawMov(); $('dMov').showModal();
}
$('bMovAdd').onclick = () => {
  const it = movActual(); if (!it) return;
  const tipo = $('mTipo').value, cant = num($('mCant').value);
  if (cant < 0 || (cant === 0 && tipo === 'entrada')) return alert('Ingresá una cantidad mayor a cero.');
  it.stock = String(tipo === 'entrada' ? num(it.stock) + cant : cant);
  it.movs = [...(it.movs || []), { f: ahora(), tipo, cant: String(cant), nota: $('mNota').value.trim(), u: yo() }];
  $('mCant').value = ''; $('mNota').value = '';
  drawInv(); drawMov();
};
$('mCan').onclick = () => { $('dMov').close(); drawInv(); };

/* ---- renombrar una categoría ya usada (actualiza también las órdenes viejas) ---- */
const CAT_KEY = { fallas: 'falla_tipo', equipos: 'equipo_tipo' };
const usadasCat = clave => [...new Set(DB.ordenes.map(o => (o[CAT_KEY[clave]] || '').trim()).filter(Boolean))];
function drawRenombres() {
  if (!esAdmin()) { $('cFallRen').innerHTML = ''; $('cEquRen').innerHTML = ''; return; }
  for (const [clave, id] of [['fallas', 'cFallRen'], ['equipos', 'cEquRen']]) {
    const L = usadasCat(clave);
    $(id).innerHTML = L.length
      ? '<div class="mut">Ya usados en órdenes: si le cambiás el nombre, se actualizan también esas órdenes.</div>' +
        L.map(x => `<div class="kv"><span>${esc(x)}</span><button type="button" data-ren="${esc(x)}" data-clave="${clave}">Renombrar</button></div>`).join('')
      : '';
  }
}
async function renombrarCat(clave, de) {
  const a = (prompt(`Nuevo nombre para “${de}”:`, de) || '').trim();
  if (!a || a === de) return;
  const ta = $(clave === 'fallas' ? 'cFallas' : 'cEquipos');
  ta.value = (clave === 'fallas' ? listaFallas : listaEquipos)(ta.value).map(x => x === de ? a : x).join('\n');
  try {
    const r = await api('/api/config/renombrar', 'POST', { clave, de, a, lista: ta.value });
    await DB.load(); drawFallas(); drawEquipos(); refrescar(); drawRenombres();
    alert(`Listo: se actualizaron ${r.cambiadas} orden(es).`);
  } catch (e) { alert(e.message); }
}
$('cFallRen').onclick = e => { const b = e.target.closest('[data-ren]'); if (b) renombrarCat(b.dataset.clave, b.dataset.ren); };
$('cEquRen').onclick = e => { const b = e.target.closest('[data-ren]'); if (b) renombrarCat(b.dataset.clave, b.dataset.ren); };

/* ---- vaciar la papelera y respaldo ---- */
$('bVaciar').onclick = async () => {
  const L = DB.data.ordenes.filter(o => o.borrada);
  if (!L.length || !confirm(`¿Borrar PARA SIEMPRE las ${L.length} órdenes de la papelera y sus fotos?`)) return;
  if (!confirm('Última confirmación: esta vez no se puede recuperar.')) return;
  for (const o of L) await purgarOrden(o);
  refrescar(); drawPapelera();
};
$('bResp').onclick = async () => {
  try {
    const r = await fetch('/api/respaldo');
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'No se pudo armar el respaldo.');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await r.blob()); a.download = `respaldo-${hoy()}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 8000);
  } catch (e) { alert(e.message + '\n\nHace falta conexión con el servidor para respaldar: probá de nuevo más tarde.'); }
};
