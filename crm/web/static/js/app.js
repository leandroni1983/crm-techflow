/* ============ ARRANQUE DE LA APP ============
   La app está dividida en módulos ES (sin empaquetador ni CDN): este archivo los engancha y arranca.
     util.js    helpers generales, sin dependencias
     db.js      capa de datos (servidor o navegador)
     comun.js   configuración, números de orden, inventario, link de seguimiento y enganche de refresco
     cat.js     tipos de falla y de equipo
     orden.js   mensajes de WhatsApp, comprobantes, formulario y papelera
     lista.js   lista de órdenes, filtros, paginación y equipos sin retirar
     config.js  configuración, usuarios, inventario, renombrado y respaldo
     panel.js   panel de estadísticas y exportar a CSV
     modo.js    estado de conexión, modo local e importar
   Al importar 'orden.js' y 'config.js' queda enganchada su parte de la pantalla (sin exportar nada). */
import { $, p2, ESTADOS } from './util.js';
import { DB } from './db.js';
import { setRefresco } from './comun.js';
import { drawFallas, drawEquipos } from './cat.js';
import { render, drawTec } from './lista.js';
import { resumen } from './panel.js';
import { drawModo } from './modo.js';
import './orden.js';
import './config.js';

/* Cambió algo: se vuelve a dibujar la lista, el panel y la barra de estado. */
setRefresco(() => { render(); resumen(); }, drawModo);

/* ============ INICIO ============ */
(async () => {
  $('fSt').innerHTML = ESTADOS.map(s => `<option>${s}</option>`).join('');
  $('fs').innerHTML = '<option value="">Todos los estados</option>' + ESTADOS.map(s => `<option>${s}</option>`).join('');
  const d = new Date(); $('rMes').value = `${d.getFullYear()}-${p2(d.getMonth() + 1)}`;
  $('rMesW').style.display = $('rPer').value === 'mes' ? '' : 'none';
  if (await DB.load() === 'login') return;
  drawFallas(); drawEquipos(); drawTec(); render(); resumen(); drawModo();
})();

/* ============ PWA ============ */
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
let instalar = null;
const yaInstalada = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const esIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); instalar = e; $('bInst').hidden = false; });
window.addEventListener('appinstalled', () => { $('bInst').hidden = true; });
$('bInst').onclick = async () => {
  if (instalar) { instalar.prompt(); await instalar.userChoice; instalar = null; $('bInst').hidden = true; return; }
  alert('Para instalar la app en iPhone/iPad:\n\n1) Tocá el botón Compartir (el cuadrito con la flecha).\n2) Elegí “Agregar a inicio”.\n3) Confirmá con “Agregar”.');
};
// En iPhone/iPad el navegador no ofrece el aviso automático: mostramos el botón con las instrucciones.
if (esIOS && !yaInstalada()) $('bInst').hidden = false;
