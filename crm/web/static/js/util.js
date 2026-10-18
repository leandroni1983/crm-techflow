/* Utilidades generales (sin dependencias de pantalla) */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const p2 = n => String(n).padStart(2, '0');
const num = x => parseFloat(String(x ?? '').replace(',', '.')) || 0;
const money = x => '$ ' + Math.round(x).toLocaleString('es-AR');
const hoy = () => { const d = new Date(); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`; };
const ahora = () => new Date().toISOString();
const fmtD = s => s ? s.split('-').reverse().join('/') : '';
const cfg = () => DB.data.config;
const find = id => DB.data.ordenes.find(x => x.id === id);
const ESTADOS = ['Recibido', 'En diagnóstico', 'Presupuesto', 'Esperando repuesto', 'En reparación', 'Listo para retirar', 'Entregado'];
const nombreEq = o => [o.equipo, o.marca].filter(Boolean).join(' ');
const costoRep = o => o.repuestos.reduce((a, r) => a + num(r.costo), 0);
const diasDesde = iso => iso ? (Date.now() - new Date(iso).getTime()) / 864e5 : 0;

const ym = iso => { const d = new Date(iso); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}`; };
const telKey = t => { const d = String(t || '').replace(/\D/g, '').replace(/^0+/, ''); return d.length >= 10 ? d.slice(-10) : d; };  // igual que en el servidor
const sinAcentos = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
function topCI(arr, n = 5) { const m = new Map(); arr.forEach(x => { const k = x.toLowerCase(), e = m.get(k) || { t: x, n: 0 }; e.n++; m.set(k, e); }); return [...m.values()].sort((a, b) => b.n - a.n).slice(0, n).map(e => [e.t, e.n]); }
function topN(arr, n = 5) { const m = {}; arr.forEach(x => m[x] = (m[x] || 0) + 1); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n); }
