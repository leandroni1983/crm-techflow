/* ============ DOMINIO COMPARTIDO ============
   Lo que usan varios módulos: configuración, números de orden, teléfonos, mensajes de WhatsApp, historial,
   inventario de repuestos y el enganche para volver a pintar la pantalla. El enganche (refrescar) evita que
   los módulos se importen entre sí en círculo: cada uno avisa "cambió algo" y app.js decide qué redibujar. */
import { DB } from './db.js';
import { num, p2, esc, cantR, diasDesde, ahora, hoy } from './util.js';

export const cfg = () => DB.data.config;
export const find = id => DB.data.ordenes.find(x => x.id === id);   // incluye las de la papelera (se usan al recuperarlas)
export const yo = () => DB.usuario?.nombre || '';
export const nombreEq = o => [o.equipo, o.marca].filter(Boolean).join(' ');
export const fechaOrd = o => new Date(o.creada || Date.now()).toLocaleDateString('es-AR');
export const saldo = o => {
  let pagado = num(o.sena);
  if (Array.isArray(o.pagos)) pagado += o.pagos.reduce((a,p)=>a + num(p.monto), 0);
  return (o.pagado === '1' || o.pagado === true) ? 0 : Math.max(num(o.monto) - pagado, 0);
};
export const costoRep = o => o.repuestos.reduce((a, r) => a + num(r.costo) * cantR(r), 0);
export const alertaDias = () => parseInt(cfg().dias_alerta) || 7;
/* Tareas/recordatorios de una orden: las pendientes y las que ya vencieron (para la lista y los avisos). */
export const tareasPend = o => (o.tareas || []).filter(t => !t.hecho);
export const tareasVencidas = o => { const h = hoy(); return tareasPend(o).filter(t => t.f && t.f < h); };
/* Listo para retirar y el cliente todavía no vino: se usa en la lista, el contador y las estadísticas. */
export const esViejo = o => o.estado === 'Listo para retirar' && diasDesde(o.estado_fecha || o.creada) > alertaDias();

export const numOrden = o => {
  const d = new Date(o.creada || Date.now());
  return cfg().prefijo + String(o.seq).padStart(4, '0') + p2(d.getDate()) + p2(d.getMonth() + 1) + p2(d.getFullYear() % 100);
};
export function normTel(t) {
  let d = String(t || '').replace(/\D/g, '').replace(/^0+/, '');
  if (!d) return '';
  const p = cfg().pais;
  return (d.startsWith(p) || d.startsWith('54')) ? d : p + d;
}
/* Deja anotado el movimiento en la orden (quién y cuándo), sin duplicar el historial del servidor. */
export async function log(o, t) { o.historial.push({ f: ahora(), t, n: true }); await DB.upsert(o); }
/* Opciones de técnico para el formulario y el filtro (incluye el valor actual aunque el usuario ya no exista). */
export const opcTec = (sel = '') => '<option value=""></option>' + [...new Set([...DB.tecnicos, sel].filter(Boolean))].map(n => `<option>${esc(n)}</option>`).join('');

/* ============ INVENTARIO DE REPUESTOS ============
   El catálogo (nombre, stock y mínimo de cada repuesto) vive en la configuración: lo edita el administrador
   desde Configuración, así que no hace falta ninguna tabla nueva. La disponibilidad no se guarda: se calcula
   como stock menos las unidades que están usando las órdenes activas, así nunca queda desfasada. */
export function repCat() { try { const L = JSON.parse(cfg().repuestos || '[]'); return Array.isArray(L) ? L : []; } catch (e) { return []; } }
export const mismoRep = (r, it) => r.rid ? r.rid === it.id : String(r.desc || '').trim().toLowerCase() === String(it.nombre || '').trim().toLowerCase();
/* Unidades puestas en órdenes. Si estamos editando una orden, sus filas guardadas no se cuentan: cuenta el borrador. */
export function repUsados(it, editando, filas = []) {
  let n = 0;
  for (const o of DB.ordenes) if (!editando || o.id !== editando.id) n += (o.repuestos || []).filter(r => mismoRep(r, it)).reduce((m, r) => m + cantR(r), 0);
  if (editando) n += filas.filter(r => mismoRep(r, it)).reduce((m, r) => m + cantR(r), 0);
  return n;
}
export const repDisp = (it, editando, filas = []) => num(it.stock) - repUsados(it, editando, filas);
export const repBajos = () => repCat().filter(it => repDisp(it) <= num(it.minimo));
export const repAlerta = () => { const b = repBajos(); return b.length ? `⚠️ Para reponer: ${b.map(x => x.nombre).join(', ')}` : ''; };

/* ============ LINK DE SEGUIMIENTO DEL CLIENTE ============
   Cada orden tiene un link privado (firmado por el servidor) que el cliente puede abrir sin usuario ni
   contraseña para ver cómo va. Sirve para escribir menos por WhatsApp: se manda una vez y el cliente consulta
   solo. Si cargaste una dirección pública en ⚙️, los links la usan; si no, se arma con la dirección actual. */
export const basePublica = () => String(cfg().url_publica || location.origin).replace(/\/+$/, '');
export const segLink = o => (o && o.seg ? `${basePublica()}/seguimiento/${o.seq}/${o.seg}` : '');
export async function copiarLink(o) {
  const u = segLink(o);
  if (!u) return alert('El link se genera al guardar la orden en la base de datos: probá de nuevo en unos segundos.');
  try { await navigator.clipboard.writeText(u); alert('Link de seguimiento copiado.\n\nPegalo en WhatsApp: el cliente ve el estado de su orden sin que le escribas.\n\n' + u); }
  catch (e) { prompt('Link de seguimiento (copialo y mandáselo al cliente):', u); }
}

/* ============ ENGANCHE DE REFRESCO (evita dependencias circulares) ============ */
let pintar = () => {}, pintarModo = () => {};
export const refrescar = () => pintar();
export const refrescarModo = () => pintarModo();
export const setRefresco = (f, m) => { pintar = f; if (m) pintarModo = m; };
