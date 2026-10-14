/* ============ HELPERS GENERALES ============
   Sin dependencias de la app: los usa todo el resto de los módulos. Al ser módulos ES, cada archivo declara
   únicamente lo que necesita y nada queda suelto en el ámbito global (era el problema de tener un solo archivo). */
export const $ = id => document.getElementById(id);
export const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
export const p2 = n => String(n).padStart(2, '0');
export const num = x => parseFloat(String(x ?? '').replace(',', '.')) || 0;
export const money = x => '$ ' + Math.round(x).toLocaleString('es-AR');
export const hoy = () => { const d = new Date(); return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`; };
export const ahora = () => new Date().toISOString();
export const fmtD = s => s ? s.split('-').reverse().join('/') : '';
/* Fecha y hora legible para las marcas de tiempo completas (por ejemplo, cuándo se mandó algo a la papelera). */
export const fmtDT = s => { const d = s ? new Date(s) : null; return d && !isNaN(d) ? `${p2(d.getDate())}/${p2(d.getMonth() + 1)}/${d.getFullYear()} ${p2(d.getHours())}:${p2(d.getMinutes())}` : fmtD(s); };
export const diasDesde = iso => iso ? (Date.now() - new Date(iso).getTime()) / 864e5 : 0;
export const cantR = r => Math.max(1, Math.round(num(r.cant) || 1));
export const fill = (t, m) => t.replace(/{(\w+)}/g, (x, k) => k in m ? (m[k] || '-') : x);

export const ESTADOS = ['Recibido', 'En diagnóstico', 'Presupuesto', 'Esperando repuesto', 'En reparación', 'Listo para retirar', 'Entregado'];
export const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
export const PALETA = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#ea580c', '#0d9488'];
export function topN(arr, n = 8) { const m = {}; arr.forEach(x => m[x] = (m[x] || 0) + 1); return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n); }

/* Achica las fotos antes de guardarlas (el navegador no debería subir 5 MB por foto). */
export function compress(file, max = 800, q = .6) {
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