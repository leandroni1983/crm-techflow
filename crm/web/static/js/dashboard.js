/* Tablero de indicadores del mes, gráficos y listas.
   Definiciones (las mismas columnas que el CSV que se exporta a Excel):
   - Facturado: suma del presupuesto de las órdenes ENTREGADAS en el mes.
   - Ganancia: facturado menos el costo de repuestos de esas órdenes.
   - Por cobrar: saldo (presupuesto menos seña) de todas las órdenes con importe que no están pagadas. */
const mesActual = () => { const d = new Date(); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}`; };
let dashMes = mesActual();
const mesMas = (mes, n) => { const [y, m] = mes.split('-').map(Number), d = new Date(y, m - 1 + n, 1); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}`; };
const mesFecha = mes => { const [y, m] = mes.split('-').map(Number); return new Date(y, m - 1, 1); };
const mesTxt = mes => { const t = mesFecha(mes).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' }); return t.charAt(0).toUpperCase() + t.slice(1); };
const mesNom = mes => mesFecha(mes).toLocaleDateString('es-AR', { month: 'long' });
const mesCorto = mes => mesFecha(mes).toLocaleDateString('es-AR', { month: 'short' }).replace('.', '');
const suma = (a, f) => a.reduce((t, x) => t + f(x), 0);
const pl = (n, uno, varios) => n === 1 ? uno : varios;
const mayus = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;

function metricas(mes) {
  const L = DB.data.ordenes;
  const ing = L.filter(o => ym(o.creada) === mes), ent = L.filter(o => (o.entrega_fecha || '').slice(0, 7) === mes);
  const fact = suma(ent, o => num(o.monto)), cost = suma(ent, costoRep);
  const dias = ent.length ? suma(ent, o => Math.max(0, (new Date(o.entrega_fecha + 'T12:00:00') - new Date(o.creada)) / 864e5)) / ent.length : null;
  return { ing, ent, fact, cost, gan: fact - cost, ticket: ent.length ? fact / ent.length : 0, dias };
}
function compara(cur, prev, mesPrev) {
  if (!prev) return cur ? { t: `sin entregas en ${mesCorto(mesPrev)}`, c: '' } : { t: '', c: '' };
  const p = Math.round((cur - prev) / prev * 100);
  if (p === 0) return { t: `igual que en ${mesCorto(mesPrev)}`, c: '' };
  return { t: `${Math.abs(p)}% ${p > 0 ? 'más' : 'menos'} que en ${mesCorto(mesPrev)}`, c: p > 0 ? 'up' : 'down' };
}
const niceMax = v => { const e = Math.pow(10, Math.floor(Math.log10(v))), f = v / e; return ([1, 1.2, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10].find(s => f <= s)) * e; };
const corto = n => n >= 1e6 ? (n / 1e6).toFixed(1).replace('.', ',') + ' M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(Math.round(n));
const compacto = n => n >= 1e6 ? '$ ' + (n / 1e6).toFixed(n % 1e6 ? 1 : 0).replace('.', ',') + ' M' : n >= 1e3 ? '$ ' + Math.round(n / 1e3) + ' mil' : '$ ' + Math.round(n);

function chartFact(mes) {
  const meses = [5, 4, 3, 2, 1, 0].map(n => mesMas(mes, -n)), datos = meses.map(m => { const t = metricas(m); return { m, f: t.fact, g: t.gan }; });
  if (!datos.some(d => d.f || d.g)) return '<div class="vacio">Todavía no hay entregas con presupuesto en estos seis meses. Cuando entregues una orden con importe, aparece acá.</div>';
  const max = niceMax(Math.max(...datos.map(d => Math.max(d.f, d.g)), 1));
  const W = 640, H = 236, L = 62, R = 6, T = 16, B = 30, pw = W - L - R, ph = H - T - B, gw = pw / 6, bw = Math.min(30, gw * .32);
  const y = v => T + ph - Math.max(0, v) / max * ph; let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Facturación y ganancia de los últimos seis meses">`;
  for (let k = 0; k <= 4; k++) { const v = max * k / 4; s += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${compacto(v)}</text>`; }
  datos.forEach((d, i) => {
    const x0 = L + i * gw, cx = x0 + gw / 2, xf = cx - bw - 2, xg = cx + 2;
    if (d.m === mes) s += `<rect class="sel" x="${x0 + 4}" y="${T}" width="${gw - 8}" height="${ph}" rx="4"/>`;
    s += `<g><title>${mesTxt(d.m)}: facturado ${money(d.f)}, ganancia ${money(d.g)}</title>`;
    s += `<rect class="b1" x="${xf}" y="${y(d.f)}" width="${bw}" height="${T + ph - y(d.f)}" rx="2"/><rect class="b2" x="${xg}" y="${y(d.g)}" width="${bw}" height="${T + ph - y(d.g)}" rx="2"/>`;
    if (d.f) s += `<text class="vl" x="${xf + bw / 2}" y="${y(d.f) - 4}" text-anchor="middle">${corto(d.f)}</text>`;
    if (d.g > 0) s += `<text class="vl" x="${xg + bw / 2}" y="${y(d.g) - 4}" text-anchor="middle">${corto(d.g)}</text>`;
    s += `</g><text class="mx" x="${cx}" y="${H - 9}" text-anchor="middle">${mayus(mesCorto(d.m))}</text>`;
  });
  return s + '</svg>';
}

const barras = (pares, vacio, tag = 'div', attr = () => '', color = () => '') => {
  if (!pares.length) return `<div class="vacio">${vacio}</div>`;
  const max = Math.max(...pares.map(p => p[1]), 1);
  return pares.map(p => `<${tag} class="bar" ${attr(p)}><span class="t"><span>${esc(p[0])}</span></span><span class="n">${p[1]}</span><span class="c"><i style="width:${Math.max(4, p[1] / max * 100)}%;${color(p)}"></i></span></${tag}>`).join('');
};

const ATENCION = [
  ['viejos', n => `${n} ${pl(n, 'equipo listo', 'equipos listos')} sin retirar hace más de ${alertaDias()} días`],
  ['presin', n => `${n} ${pl(n, 'presupuesto', 'presupuestos')} sin respuesta hace más de ${alertaDias()} días`],
  ['atras', n => `${n} ${pl(n, 'entrega atrasada', 'entregas atrasadas')}`],
  ['debe', n => `${n} ${pl(n, 'orden entregada', 'órdenes entregadas')} con saldo pendiente`],
  ['vence', n => `${n} ${pl(n, 'garantía vence', 'garantías vencen')} en los próximos 15 días`]
];

function drawDashboard() {
  const L = DB.data.ordenes, mt = metricas(dashMes), pm = metricas(mesMas(dashMes, -1)), pmes = mesMas(dashMes, -1);
  $('mesLbl').textContent = mesTxt(dashMes); $('mesNext').disabled = dashMes >= mesActual(); $('mesHoy').hidden = dashMes === mesActual();
  const cobrar = L.filter(o => num(o.monto) > 0 && saldo(o) > 0), presup = L.filter(o => o.estado === 'Presupuesto');
  const activas = L.filter(o => o.estado !== 'Entregado'), listas = activas.filter(o => o.estado === 'Listo para retirar');
  const dF = compara(mt.fact, pm.fact, pmes), dI = compara(mt.ing.length, pm.ing.length, pmes);
  const m = (cls, l, v, s = '', sc = '', tip = '') => `<div class="m ${cls}" title="${esc(tip)}"><span class="l">${l}</span><span class="v">${v}</span><span class="s ${sc}${s ? '' : ' vac'}">${s || '&nbsp;'}</span></div>`;
  $('tablero').innerHTML =
    `<div class="grp g1">` +
      m('big', 'Facturado', money(mt.fact), dF.t, dF.c, 'Suma del presupuesto de las órdenes entregadas en el mes') +
      m('', 'Ganancia', money(mt.gan), mt.fact ? `repuestos ${money(mt.cost)}` : '', '', 'Facturado menos el costo de los repuestos') +
      m('', 'Ticket promedio', money(mt.ticket), mt.ent.length ? `en ${mt.ent.length} ${pl(mt.ent.length, 'entrega', 'entregas')}` : '', '', 'Facturado dividido la cantidad de órdenes entregadas') +
      m('', 'Margen', mt.fact ? Math.round(mt.gan / mt.fact * 100) + ' %' : '–', '', '', 'Ganancia sobre facturado') +
    `</div><div class="grp g2">` +
      m('', 'Activas', activas.length, listas.length ? `${listas.length} ${pl(listas.length, 'lista', 'listas')} para retirar` : 'en el taller ahora', '', 'Órdenes que todavía no se entregaron') +
      m('', 'Entregadas', mt.ent.length, '', '', 'Órdenes con fecha de entrega en este mes') +
      m('', 'Ingresadas', mt.ing.length, dI.t, dI.c, 'Órdenes recibidas en este mes') +
      m('', 'Tiempo medio', mt.dias == null ? '–' : (mt.dias < 10 ? mt.dias.toFixed(1).replace('.', ',') : Math.round(mt.dias)) + ' días', 'del ingreso a la entrega', '', 'Promedio entre ingreso y entrega de lo entregado en el mes') +
    `</div><div class="grp g3">` +
      m(cobrar.length ? 'warn' : '', 'Por cobrar', money(suma(cobrar, saldo)), `${cobrar.length} ${pl(cobrar.length, 'orden', 'órdenes')} con saldo`, '', 'Saldo (presupuesto menos seña) de las órdenes no pagadas') +
      m('', 'Presupuestos pendientes', presup.length, presup.length ? `por ${money(suma(presup, o => num(o.monto)))} en total` : 'ninguno esperando respuesta', '', 'Órdenes en estado Presupuesto') +
    `</div>`;

  $('chFact').innerHTML = chartFact(dashMes);
  const etapas = ESTADOS.slice(0, 6).map(e => [e, L.filter(o => o.estado === e).length]);
  $('chEtapas').innerHTML = etapas.some(e => e[1])
    ? barras(etapas, '', 'button', p => `data-estado="${esc(p[0])}" title="Ver las órdenes en ${esc(p[0])}"`, p => `background:var(--e${ESTADOS.indexOf(p[0]) + 1})`)
    : '<div class="vacio">No hay órdenes activas.</div>';
  const items = ATENCION.map(([k, txt]) => [k, txt, L.filter(QUICK[k][1]).length]).filter(x => x[2]);
  $('atn').innerHTML = items.length ? items.map(([k, txt, n]) => `<li><button data-q="${k}"><span>${txt(n)}</span><span class="k">${n}</span></button></li>`).join('')
    : '<li class="ok"><svg class="i"><use href="#i-check"/></svg>Todo al día</li>';
  $('lsEq').innerHTML = barras(topCI(mt.ing.map(nombreEq).filter(Boolean)), 'Sin órdenes ingresadas este mes');
  $('lsFa').innerHTML = barras(topN(mt.ing.flatMap(fallasDe)), 'Sin fallas cargadas este mes');
  $('lsTe').innerHTML = barras(topN(mt.ing.map(o => o.tecnico || 'Sin asignar')), 'Sin órdenes ingresadas este mes');
}

/* navegación por mes y panel plegable */
$('mesPrev').onclick = () => { dashMes = mesMas(dashMes, -1); drawDashboard(); };
$('mesNext').onclick = () => { dashMes = mesMas(dashMes, 1); drawDashboard(); };
$('mesHoy').onclick = () => { dashMes = mesActual(); drawDashboard(); };
function panelAbierto(v, guardar = true) {
  $('dash').hidden = !v; $('bPanel').innerHTML = '<span>' + (v ? 'Ocultar' : 'Mostrar') + '<span class="d"> indicadores</span></span>'; $('panel').classList.toggle('cerrado', !v); $('bPanel').setAttribute('aria-expanded', v);
  if (guardar) try { localStorage.setItem('crm_panel', v ? '1' : '0'); } catch (e) {}
}
$('bPanel').onclick = () => panelAbierto($('dash').hidden);
$('chEtapas').onclick = e => { const b = e.target.closest('[data-estado]'); if (b) { $('fs').value = b.dataset.estado; quick = ''; irALista(); } };
$('atn').onclick = e => { const b = e.target.closest('[data-q]'); if (b) { quick = b.dataset.q; $('fs').value = ''; irALista(); } };
function irALista() { pagina = 1; renderLista(); $('ordenes').scrollIntoView({ behavior: 'smooth', block: 'start' }); }
try { const v = localStorage.getItem('crm_panel'); if (v === '0') panelAbierto(false); else if (v === null && matchMedia('(max-width:720px)').matches) panelAbierto(false, false); } catch (e) {}
