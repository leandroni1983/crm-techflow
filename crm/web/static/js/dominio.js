/* Reglas del negocio en el navegador: número de orden, teléfono, mensajes de WhatsApp, garantía */
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

/* Fallas: catálogo configurable (⚙️). Cada orden guarda las fallas marcadas y, aparte, el detalle que cuenta el cliente. */
const catalogoFallas = () => (cfg().fallas_comunes || '').split('\n').map(s => s.trim()).filter(Boolean);
const fallaTxt = o => [(o.fallas || []).join(', '), o.problema].filter(Boolean).join('. ');
/* Fallas de una orden para las estadísticas: las marcadas; si no hay, las del catálogo que aparecen en el texto; si no, "Sin clasificar". */
function fallasDe(o) {
  if ((o.fallas || []).length) return o.fallas;
  const t = sinAcentos(o.problema); if (!t.trim()) return [];
  const hit = catalogoFallas().filter(f => t.includes(sinAcentos(f)));
  return hit.length ? hit : ['Sin clasificar'];
}
function vars(o) {
  const c = cfg();
  return { cliente: o.cliente, numero: numOrden(o), equipo: nombreEq(o), estado: o.estado, taller: c.taller, diagnostico: o.diagnostico,
    presupuesto: o.monto, saldo: money(saldo(o)), garantia: garTxt(o) || ' ', fecha: fechaOrd(o), serie: o.serie,
    accesorios: o.accesorios, fisico: o.fisico, falla: fallaTxt(o), condiciones: c.condiciones };
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

