/* Arranque, menú de cuenta, exportación a Excel y app instalable */

/* ---------- exportar a Excel (CSV con punto y coma, abre directo en Excel) ---------- */
$('bCsv').onclick = () => {
  const cols = [['N° orden', numOrden], ['Fecha ingreso', fechaOrd], ['Cliente', o => o.cliente], ['Teléfono', o => o.tel], ['Equipo', o => o.equipo],
    ['Marca', o => o.marca], ['N° de serie', o => o.serie], ['Estado', o => o.estado], ['Técnico', o => o.tecnico], ['Fallas', o => (o.fallas || []).join(', ')], ['Detalle de la falla', o => o.problema], ['Diagnóstico', o => o.diagnostico],
    ['Presupuesto', o => num(o.monto)], ['Seña', o => num(o.sena)], ['Pagado', o => o.pagado ? 'Sí' : 'No'], ['Costo repuestos', costoRep],
    ['Ganancia', o => num(o.monto) - costoRep(o)], ['Fecha entrega', o => fmtD(o.entrega_fecha)], ['Garantía hasta', o => { const g = garantiaHasta(o); return g ? g.toLocaleDateString('es-AR') : ''; }]];
  const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  const csv = '\ufeff' + [cols.map(c => q(c[0])).join(';'), ...DB.data.ordenes.map(o => cols.map(c => q(c[1](o))).join(';'))].join('\r\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  a.download = 'ordenes-' + hoy() + '.csv'; a.click();
};

/* ---------- menú de la cuenta y atajos ---------- */
const cerrarMenu = () => { $('userMenu').hidden = true; $('bUser').setAttribute('aria-expanded', 'false'); };
$('bUser').onclick = e => { e.stopPropagation(); const m = $('userMenu'); m.hidden = !m.hidden; $('bUser').setAttribute('aria-expanded', String(!m.hidden)); };
document.addEventListener('click', e => { if (!e.target.closest('.user')) cerrarMenu(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') cerrarMenu();
  const campo = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if (e.key === '/' && !campo && !document.querySelector('dialog[open]')) { e.preventDefault(); $('q').focus(); }
});
$('bOut').onclick = async () => {
  try { await fetch('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch (x) {}
  location.href = '/login';
};

/* ---------- inicio ---------- */
(async () => {
  $('fSt').innerHTML = ESTADOS.map(s => `<option>${s}</option>`).join('');
  $('fs').innerHTML = '<option value="">Todos los estados</option>' + ESTADOS.map(s => `<option>${s}</option>`).join('');
  if (await DB.load() === 'login') return;
  drawTec(); render(); drawModo();
  if (location.hash === '#clientes') irVista('cli');
})();

/* ---------- app instalable (PWA) ---------- */
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
let instalar = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); instalar = e; $('bInst').hidden = false; });
$('bInst').onclick = async () => { cerrarMenu(); if (!instalar) return; instalar.prompt(); await instalar.userChoice; instalar = null; $('bInst').hidden = true; };
window.addEventListener('appinstalled', () => { $('bInst').hidden = true; });
