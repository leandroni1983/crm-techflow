/* Clientes y equipos: ficha con el historial de reparaciones de cada equipo */
let vista = 'ord', paginaCli = 1; const PAGE_CLI = 40, abiertosCli = new Set();
const fechaCorta = iso => iso ? new Date(iso).toLocaleDateString('es-AR') : '';
const nomEq = e => [e.tipo, e.marca].filter(Boolean).join(' ') || 'Equipo sin nombre';

function irVista(v) {
  vista = v;
  $('vistaOrd').hidden = v !== 'ord'; $('vistaCli').hidden = v !== 'cli';
  $('vOrd').classList.toggle('on', v === 'ord'); $('vCli').classList.toggle('on', v === 'cli');
  $('q').value = ''; $('q').placeholder = v === 'ord' ? 'Buscar por número, cliente, equipo o teléfono' : 'Buscar cliente por nombre, teléfono o número de serie';
  try { history.replaceState(null, '', v === 'cli' ? '#clientes' : location.pathname); } catch (e) {}
  v === 'cli' ? renderClientes() : renderLista();
}
$('vOrd').onclick = () => irVista('ord'); $('vCli').onclick = () => irVista('cli');

/* una ficha por cliente, con sus órdenes y equipos y los totales */
function fichas() {
  const ords = new Map(), eqs = new Map();
  for (const o of DB.data.ordenes) if (o.cliente_id) { if (!ords.has(o.cliente_id)) ords.set(o.cliente_id, []); ords.get(o.cliente_id).push(o); }
  for (const e of DB.data.equipos) { if (!eqs.has(e.cliente_id)) eqs.set(e.cliente_id, []); eqs.get(e.cliente_id).push(e); }
  return DB.data.clientes.map(c => {
    const L = (ords.get(c.id) || []).sort((a, b) => String(a.creada).localeCompare(String(b.creada)) || a.seq - b.seq), ent = L.filter(o => o.estado === 'Entregado');
    return { c, L, eqs: eqs.get(c.id) || [], activas: L.filter(o => o.estado !== 'Entregado').length, facturado: suma(ent, o => num(o.monto)),
             ultima: L.length ? L[L.length - 1].creada : (c.creado || ''), gar: L.filter(enGarantia).length, debe: suma(L, saldo) };
  });
}
const waCli = c => 'https://wa.me/' + normTel(c.tel) + '?text=' + encodeURIComponent(`Hola ${c.nombre}! Te escribimos de ${cfg().taller}.`);

/* ---------- una línea de la historia de un equipo ---------- */
function lineaOrden(o, reinc) {
  const i = Math.max(0, ESTADOS.indexOf(o.estado)), imp = num(o.monto);
  return `<li><button class="lnk" data-ca="orden" data-id="${o.id}" title="Abrir la orden">${esc(numOrden(o))}</button><span>${esc(fechaOrd(o))}</span>
    <span class="est" style="--c:var(--e${i + 1})">${esc(o.estado)}</span>
    <span class="fl">${esc(fallaTxt(o) || 'Sin falla cargada')}${reinc ? ' <span class="tag warn">Volvió dentro de la garantía</span>' : ''}</span>
    <span class="imp r">${imp ? money(imp) : ''}</span></li>`;
}
function bloqueEquipo(e, f) {
  const L = f.L.filter(o => o.equipo_id === e.id), dias = parseInt(cfg().garantia_dias) || 0, reinc = new Set();
  L.forEach((o, k) => { const p = L[k - 1]; if (p && p.entrega_fecha && dias && (new Date(o.creada) - new Date(p.entrega_fecha + 'T12:00:00')) / 864e5 <= dias) reinc.add(o.id); });
  const ent = L.filter(o => o.estado === 'Entregado'), ult = ent[ent.length - 1], g = ult && enGarantia(ult) ? garantiaHasta(ult) : null, fal = topN(L.flatMap(fallasDe), 4);
  const datos = [e.serie && 'Serie ' + e.serie, e.color, e.notas].filter(Boolean).map(esc).join(', ');
  return `<div class="eq">
    <div class="eq-h"><div><b>${esc(nomEq(e))}</b>${datos ? `<small>${datos}</small>` : ''}</div>
      <div class="acts"><button data-ca="neworden-eq" data-eq="${e.id}">${ic('plus', 'Nueva orden')}</button><button data-ca="edit-eq" data-eq="${e.id}">${ic('edit', 'Editar')}</button>${L.length ? '' : `<button class="dg" data-ca="del-eq" data-eq="${e.id}">${ic('trash', 'Borrar')}</button>`}</div></div>
    <div class="eq-r">${L.length} ${pl(L.length, 'reparación', 'reparaciones')}${ent.length ? `, facturado ${money(suma(ent, o => num(o.monto)))}` : ''}
      ${g ? `<span class="tag ok">En garantía hasta ${esc(g.toLocaleDateString('es-AR'))}</span>` : ''}${reinc.size ? `<span class="tag warn">${reinc.size} ${pl(reinc.size, 'vuelta', 'vueltas')} dentro de la garantía</span>` : ''}</div>
    ${fal.length ? `<div class="eq-f">${fal.map(([x, n]) => `<span class="tag">${esc(x)}${n > 1 ? ' ×' + n : ''}</span>`).join('')}</div>` : ''}
    <ol class="linea">${L.length ? [...L].reverse().map(o => lineaOrden(o, reinc.has(o.id))).join('') : '<li class="mut">Todavía no tiene reparaciones.</li>'}</ol></div>`;
}
function detalleCli(f) {
  const { c } = f, sueltas = f.L.filter(o => !f.eqs.some(e => e.id === o.equipo_id));
  return `<div class="det-g cli-g">
    <div><h4>Datos</h4><dl class="dl">${fila_d('Teléfono', esc(c.tel))}${fila_d('Dirección', esc(c.direccion))}${fila_d('Correo', esc(c.email))}${fila_d('Cliente desde', esc(fechaCorta(c.creado)))}
      ${f.debe ? fila_d('Saldo pendiente', `<span class="fig">${money(f.debe)}</span>`) : ''}${fila_d('Notas', esc(c.notas))}</dl>
      <div class="acts"><button data-ca="nueva" data-id="${c.id}">${ic('plus', 'Nueva orden')}</button><button data-ca="edit" data-id="${c.id}">${ic('edit', 'Editar cliente')}</button>
        <button data-ca="neweq" data-id="${c.id}">${ic('plus', 'Agregar equipo')}</button>${f.L.length ? '' : `<button class="dg" data-ca="del" data-id="${c.id}">${ic('trash', 'Borrar')}</button>`}</div></div>
    <div><h4>Equipos y reparaciones</h4>${f.eqs.map(e => bloqueEquipo(e, f)).join('') || '<div class="vacio">Todavía no tiene equipos registrados.</div>'}
      ${sueltas.length ? `<div class="eq"><div class="eq-h"><div><b>Órdenes sin equipo registrado</b></div></div><ol class="linea">${[...sueltas].reverse().map(o => lineaOrden(o, false)).join('')}</ol></div>` : ''}</div></div>`;
}
function filaCli(f) {
  const { c } = f, abierta = abiertosCli.has(c.id), nombres = f.eqs.slice(0, 2).map(nomEq).join(', ') + (f.eqs.length > 2 ? ` y ${f.eqs.length - 2} más` : '');
  return `<div class="orden${abierta ? ' abierta' : ''}"><div class="fila" data-id="${c.id}" role="button" tabindex="0" aria-expanded="${abierta}">
      <div class="c-cl celda"><b>${esc(c.nombre)}</b><small>${esc(c.tel)}</small></div>
      <div class="c-eq celda"><b>${f.eqs.length} ${pl(f.eqs.length, 'equipo', 'equipos')}</b><small>${esc(nombres) || 'Sin equipos registrados'}</small></div>
      <div class="c-or celda r"><span class="imp" data-u="${pl(f.L.length, 'orden', 'órdenes')}">${f.L.length}</span>${f.activas ? `<span class="imp-s">${f.activas} ${pl(f.activas, 'activa', 'activas')}</span>` : ''}</div>
      <div class="c-fa celda r"><span class="imp">${money(f.facturado)}</span>${f.debe ? `<span class="imp-s deb">Debe ${money(f.debe)}</span>` : ''}</div>
      <div class="c-ul celda"><b>${esc(fechaCorta(f.ultima)) || '–'}</b>${f.gar ? `<small>${f.gar} en garantía</small>` : ''}</div>
      <div class="c-ac acc">${normTel(c.tel) ? `<a class="wa" href="${waCli(c)}" target="_blank" rel="noopener" title="Escribirle por WhatsApp">${ic('chat', 'WhatsApp')}</a>` : ''}<button class="exp" aria-label="Ver ficha">${ic('chev')}</button></div>
    </div><div class="det">${detalleCli(f)}</div></div>`;
}

function renderClientes() {
  if (!DB.api) { $('listCli').innerHTML = '<div class="empty"><b>Clientes necesita el servidor</b>En modo navegador no se guardan clientes. Abrí el CRM desde el servidor.</div>'; return; }
  const q = sinAcentos($('q').value).trim(), by = {
    nombre: (a, b) => (a.c.nombre || '').localeCompare(b.c.nombre || '', 'es'), ultima: (a, b) => String(b.ultima).localeCompare(String(a.ultima)),
    ordenes: (a, b) => b.L.length - a.L.length, facturado: (a, b) => b.facturado - a.facturado };
  const todos = fichas().filter(f => !q || sinAcentos([f.c.nombre, f.c.tel, f.c.email, ...f.eqs.map(e => [e.tipo, e.marca, e.serie].join(' '))].join(' ')).includes(q)).sort(by[$('fCO').value] || by.nombre);
  const vistos = todos.slice(0, paginaCli * PAGE_CLI), total = DB.data.clientes.length;
  $('listCli').innerHTML = vistos.length ? vistos.map(filaCli).join('')
    : total ? '<div class="empty"><b>Ningún cliente coincide</b>Probá con otro nombre, teléfono o número de serie.</div>'
      : '<div class="empty"><b>Todavía no hay clientes</b>Se crean solos al cargar una orden, o con “Nuevo cliente”.</div>';
  $('cuentaCli').textContent = total ? (todos.length === total ? `(${total})` : `(${todos.length} de ${total})`) : '';
  $('masCliWrap').hidden = todos.length <= vistos.length; $('bMasCli').textContent = `Mostrar más (${todos.length - vistos.length} ${pl(todos.length - vistos.length, 'restante', 'restantes')})`;
}

/* ---------- acciones ---------- */
const clienteDe = id => DB.data.clientes.find(c => c.id === id), equipoDe = id => DB.data.equipos.find(e => e.id === id);
$('listCli').onclick = async e => {
  const t = e.target; if (t.closest('a.wa')) return;  // WhatsApp: sigue el enlace
  const b = t.closest('[data-ca]');
  if (b) {
    const a = b.dataset.ca, c = clienteDe(b.dataset.id), eq = equipoDe(b.dataset.eq);
    try {
      if (a === 'nueva') return openOrd(null, { cliente: c });
      if (a === 'neworden-eq') return openOrd(null, { cliente: clienteDe(eq.cliente_id), equipo: eq });
      if (a === 'edit') return abrirKc(c);
      if (a === 'neweq') return abrirKe(null, c);
      if (a === 'edit-eq') return abrirKe(eq, clienteDe(eq.cliente_id));
      if (a === 'orden') return openOrd(find(b.dataset.id));
      if (a === 'del' && confirm(`¿Borrar a ${c.nombre} y sus equipos? No tiene órdenes.`)) { await DB.delCliente(c.id); abiertosCli.delete(c.id); render(); }
      if (a === 'del-eq' && confirm('¿Borrar este equipo? No tiene reparaciones.')) { await DB.delEquipo(eq.id); render(); }
    } catch (err) { alert(err.message); }
    return;
  }
  const f = t.closest('.fila'); if (f) alternarCli(f);
};
$('listCli').onkeydown = e => { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('fila')) { e.preventDefault(); alternarCli(e.target); } };
function alternarCli(f) {
  const el = f.parentElement, ab = !el.classList.contains('abierta');
  el.classList.toggle('abierta', ab); f.setAttribute('aria-expanded', ab); ab ? abiertosCli.add(f.dataset.id) : abiertosCli.delete(f.dataset.id);
}
$('fCO').onchange = () => { paginaCli = 1; renderClientes(); };
$('bMasCli').onclick = () => { paginaCli++; renderClientes(); };
$('bNewCli').onclick = () => { if (!DB.api) return alert('Para cargar clientes hace falta el servidor.'); abrirKc(null); };

/* ---------- diálogos de cliente y de equipo ---------- */
let kcEd = null, keEd = null, keDe = null;
function abrirKc(c) {
  kcEd = c || null; $('dKcT').textContent = c ? 'Editar cliente' : 'Nuevo cliente';
  $('kcNom').value = c?.nombre || ''; $('kcTel').value = c?.tel || ''; $('kcMail').value = c?.email || ''; $('kcDir').value = c?.direccion || ''; $('kcNot').value = c?.notas || '';
  $('kcAviso').textContent = c ? 'Si cambiás el nombre, el teléfono o la dirección, también se actualizan en todas sus órdenes (los mensajes de WhatsApp usan el dato nuevo).' : '';
  $('dKc').showModal();
}
$('kcCan').onclick = () => $('dKc').close();
$('kcSave').onclick = async () => {
  if (!$('kcNom').value.trim()) return alert('El cliente necesita un nombre.');
  try {
    await DB.saveCliente({ id: kcEd?.id, nombre: $('kcNom').value, tel: $('kcTel').value, email: $('kcMail').value, direccion: $('kcDir').value, notas: $('kcNot').value });
    $('dKc').close(); render();
  } catch (e) { alert(e.message); }
};
function abrirKe(e, c) {
  keEd = e || null; keDe = c; $('dKeT').textContent = (e ? 'Editar equipo' : 'Nuevo equipo') + ' de ' + c.nombre;
  $('keTipo').value = e?.tipo || ''; $('keMarca').value = e?.marca || ''; $('keSerie').value = e?.serie || ''; $('keColor').value = e?.color || ''; $('keNot').value = e?.notas || '';
  $('dKe').showModal();
}
$('keCan').onclick = () => $('dKe').close();
$('keSave').onclick = async () => {
  try {
    await DB.saveEquipo({ id: keEd?.id, cliente_id: keDe.id, tipo: $('keTipo').value, marca: $('keMarca').value, serie: $('keSerie').value, color: $('keColor').value, notas: $('keNot').value });
    $('dKe').close(); render();
  } catch (e) { alert(e.message); }
};
