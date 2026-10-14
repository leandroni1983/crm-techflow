/* ============ ESTADO, MODO LOCAL E IMPORTAR DEL NAVEGADOR ============
   La barra superior cuenta si la base está conectada, si hay cambios en cola y si hay repuestos para reponer.
   Además, si quedaron órdenes guardadas en el navegador (modo sin servidor), ofrece pasarlas a la base. */
import { $, esc } from './util.js';
import { DB, norm } from './db.js';
import { repBajos, refrescar } from './comun.js';

function localOrders() { try { return (JSON.parse(localStorage.getItem(DB.K)) || {}).ordenes || []; } catch (e) { return []; } }
export function drawModo() {
  const n = DB.api ? localOrders().length : 0, s = DB.sync || { online: true, pendientes: 0, errores: 0, motor: 'la base de datos' };
  const cola = s.pendientes ? ` · ${s.pendientes} cambio${s.pendientes > 1 ? 's' : ''} ${s.online ? 'sincronizándose…' : 'pendiente' + (s.pendientes > 1 ? 's' : '') + ' (se envían solos al volver la conexión)'}` : '';
  const err = s.errores ? ` · ✖ ${s.errores} cambio${s.errores > 1 ? 's' : ''} con error (avisá al administrador)` : '';
  const rep = repBajos();
  $('modo').className = 'modo ' + (DB.api && s.online && !s.errores ? 'ok' : 'warn');
  $('modo').innerHTML = DB.api
    ? `<span>${s.online ? '●' : '⚠️'} ${s.online ? 'Base de datos: ' + esc(s.motor) : 'Sin conexión con la base de datos: trabajando en modo local'}${cola}${err}${rep.length ? ` · ⚠️ ${rep.length} repuesto${rep.length > 1 ? 's' : ''} para reponer` : ''} · 👤 ${esc(DB.usuario?.nombre || '')}</span>` + (n ? `<button id="bImp">Importar ${n} órdenes que quedaron en el navegador</button>` : '') + '<button id="bOut">Salir</button>'
    : '<span>⚠️ Modo navegador: los datos NO se guardan en la base. Ejecutá `python -m crm` y abrí http://localhost:8000 (el PDF y el QR necesitan el servidor)</span>';
}
/* Estado de sincronización y "tiempo real": se consulta cada 5 s. Además de detectar que volvió la conexión,
   si otro usuario cambió algo (el servidor lo resume en un "sello"), se recarga la lista sola. No se recarga
   si hay un diálogo abierto o cambios locales sin subir, para no pisar lo que estás escribiendo. */
async function palpar() {
  if (!DB.api) return;
  try {
    const prev = DB.sync, r = await DB.req('/api/estado'), s = await r.json();
    DB.sync = s;
    const antes = prev && (!prev.online || prev.pendientes > 0);
    const reconectado = antes && s.online && s.pendientes === 0;
    const remoto = s.online && s.pendientes === 0 && !s.errores && prev && prev.sello && s.sello && s.sello !== prev.sello;
    const ocupado = $('dOrd').open || $('dCfg').open || $('dCli').open || $('dCaja').open || $('dMov').open;
    if ((reconectado || remoto) && !ocupado) { await DB.load(); refrescar(); }
    drawModo();
  } catch (e) { /* sin servidor del CRM: se verá al intentar guardar */ }
}
setInterval(palpar, 5000);
/* Al volver a la pestaña, se consulta enseguida (así se ve lo último sin esperar al intervalo). */
document.addEventListener('visibilitychange', () => { if (!document.hidden) palpar(); });
async function importarLocal() {
  const L = localOrders().sort((a, b) => (a.seq || 0) - (b.seq || 0));
  if (!confirm(`Se van a pasar ${L.length} órdenes a la base de datos. Reciben un número nuevo de secuencia. ¿Continuar?`)) return;
  for (const o of L) await DB.upsert({ ...norm(o), seq: undefined });
  try { localStorage.removeItem(DB.K); } catch (e) {}
  await DB.load(); refrescar(); drawModo();
}
$('modo').onclick = async e => {
  if (e.target.id === 'bImp') importarLocal();
  if (e.target.id === 'bOut') { try { await fetch('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); } catch (x) {} location.href = '/login'; }
};
