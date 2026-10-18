/* Configuración del taller, cuenta propia y usuarios */
const CFG = { taller: 'cNom', taller_datos: 'cDat', prefijo: 'cPre', pais: 'cPais', pdfAncho: 'cAncho', pdfAlto: 'cAlto', et_ancho: 'cEtA',
  et_alto: 'cEtH', garantia_dias: 'cGar', dias_alerta: 'cAle', checklist_items: 'cChk', fallas_comunes: 'cFal', plantillas: 'cPla', msg: 'cMsg', msgP: 'cMsgP',
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

