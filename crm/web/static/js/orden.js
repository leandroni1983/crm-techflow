/* Formulario de orden: campos, repuestos, fotos, firmas, clientes y guardado */
const CAMPOS = { cliente: 'fCli', tel: 'fTel', direccion: 'fDir', equipo: 'fEq', marca: 'fMa', color: 'fCo', serie: 'fSe', accesorios: 'fAc',
  fisico: 'fFi', deteriorado: 'fDe', tecnico: 'fTe', cliente_id: 'fCliId', equipo_id: 'fEqId', clave: 'fCl', garantia_fab: 'fGf', problema: 'fPr', observ: 'fOb', estado: 'fSt', hora: 'fHo',
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
function drawFal(sel) {
  const items = [...new Set([...catalogoFallas(), ...sel])];
  $('fFal').innerHTML = items.length ? items.map(i => `<label><input type="checkbox" value="${esc(i)}" ${sel.includes(i) ? 'checked' : ''}> ${esc(i)}</label>`).join('') : '<span class="mut">Definí el catálogo de fallas en ⚙️</span>';
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
function relacionados(tel, id) { const cid = $('fCliId').value, k = telKey(tel); return DB.data.ordenes.filter(x => x.id !== id && ((cid && x.cliente_id === cid) || (k && telKey(x.tel) === k))); }
function showCliHist() {
  const L = relacionados($('fTel').value, editing?.id);
  $('fCliHist').innerHTML = L.length ? `<b>${L.length} reparación(es) anterior(es):</b><br>` + L.slice(0, 5).map(x =>
    `${esc(numOrden(x))}, ${esc(nombreEq(x)) || 'sin equipo'}, ${esc(x.estado)}${enGarantia(x) ? ' <b style="color:var(--placa)">(en garantía hasta ' + garantiaHasta(x).toLocaleDateString('es-AR') + ')</b>' : ''}`).join('<br>') : '';
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

function openOrd(o, pre) {
  editing = o || null;
  const c = pre?.cliente, e = pre?.equipo;  // "Nueva orden" desde la ficha de un cliente o de uno de sus equipos
  const b = o || { ...ordenVacia(), tecnico: yo(), hora: `${p2(new Date().getHours())}:${p2(new Date().getMinutes())}`,
    ...(c ? { cliente: c.nombre, tel: c.tel, direccion: c.direccion || '', cliente_id: c.id } : {}),
    ...(e ? { equipo: e.tipo, marca: e.marca, serie: e.serie, color: e.color, equipo_id: e.id } : {}) };
  $('dTitle').textContent = o ? 'Editar ' + numOrden(o) : 'Nueva orden';
  $('fTe').innerHTML = opcTec(b.tecnico);
  for (const [k, id] of Object.entries(CAMPOS)) $(id).value = b[k] || '';
  $('fSt').value = b.estado || ESTADOS[0]; $('fPg').checked = !!b.pagado;
  tmpImgs = [...b.imagenes]; tmpRep = b.repuestos.map(r => ({ ...r }));
  drawChk(b.checklist); drawFal(b.fallas); dibujarEquipos(b.cliente_id, b.equipo_id); drawRep(); drawImgs(); $('fImg').value = '';
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
/* ---- vínculo con el cliente y con su equipo: al escribir un teléfono conocido se completan sus datos y se ofrecen sus equipos ---- */
const clientePorTel = tel => { const k = telKey(tel); return k ? DB.data.clientes.find(c => telKey(c.tel) === k) : null; };
let eqPrevio = '';  // equipo elegido en el selector (para saber si hay que limpiar los campos al pasar a "Equipo nuevo")
function dibujarEquipos(cid, selId) {
  const L = cid ? DB.data.equipos.filter(e => e.cliente_id === cid) : [];
  $('fEqWrap').hidden = !L.length;
  $('fEqSel').innerHTML = '<option value="">Equipo nuevo</option>' + L.map(e => `<option value="${esc(e.id)}">${esc([e.tipo, e.marca].filter(Boolean).join(' ') || 'Equipo')}${e.serie ? ' (serie ' + esc(e.serie) + ')' : ''}</option>`).join('');
  $('fEqSel').value = L.some(e => e.id === selId) ? selId : ''; eqPrevio = $('fEqSel').value;
}
function vincularCliente(c) {
  $('fCliId').value = c ? c.id : ''; $('fEqId').value = '';
  if (c) { if (!$('fCli').value) $('fCli').value = c.nombre; if (!$('fDir').value) $('fDir').value = c.direccion || ''; }
  dibujarEquipos(c ? c.id : '', '');
}
$('fEqSel').onchange = () => {
  const e = DB.data.equipos.find(x => x.id === $('fEqSel').value);
  if (e) { $('fEqId').value = e.id; $('fEq').value = e.tipo; $('fMa').value = e.marca; $('fSe').value = e.serie; $('fCo').value = e.color; }
  else { $('fEqId').value = ''; if (eqPrevio) for (const id of ['fEq', 'fMa', 'fSe', 'fCo']) $(id).value = ''; }
  eqPrevio = $('fEqSel').value;
};
$('fTel').onchange = () => {
  const c = clientePorTel($('fTel').value);
  if ((c ? c.id : '') !== $('fCliId').value) vincularCliente(c);  // cambió de cliente (o el número ya no coincide con ninguno)
  showCliHist();
};
$('fCli').onchange = () => {
  if (!$('fCliId').value && !$('fTel').value) {
    const v = $('fCli').value.trim().toLowerCase(), c = DB.data.clientes.find(x => (x.nombre || '').toLowerCase() === v);
    if (c) { $('fTel').value = c.tel; vincularCliente(c); }
  }
  showCliHist();
};
$('bSave').onclick = async () => {
  if (!$('fCli').value.trim() || !$('fTel').value.trim()) return alert('Cliente y WhatsApp son obligatorios.');
  const o = { ...(editing || { id: 'o' + Date.now(), creada: ahora() }), historial: [...(editing?.historial || [])] };
  for (const [k, id] of Object.entries(CAMPOS)) o[k] = $(id).value.trim();
  o.pagado = $('fPg').checked ? '1' : '';
  o.checklist = [...$('fChk').querySelectorAll('input:checked')].map(i => i.value);
  o.fallas = [...$('fFal').querySelectorAll('input:checked')].map(i => i.value);
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

