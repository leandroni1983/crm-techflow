/* ============ TIPOS DE FALLA Y DE EQUIPO ============
   Categorías fijas que se eligen en el formulario y se cuentan en el panel ("Fallas más comunes" y "Equipos más
   frecuentes"). El administrador puede editar las listas desde Configuración; esto es solo el valor por defecto. */
import { esc, $ } from './util.js';
import { cfg } from './comun.js';

export const FALLAS_DEF = ['No enciende', 'No da imagen / no arranca', 'No carga / batería', 'Líquido / mojado', 'Pantalla rota',
  'Teclado / botones', 'Lento / virus / sistema', 'No conecta (WiFi/red)', 'Limpieza / mantenimiento', 'Otro'];
export function listaFallas(txt) {
  const L = String(txt || '').split('\n').map(s => s.trim()).filter(Boolean);
  return L.length ? L : FALLAS_DEF;
}
export const fallas = () => listaFallas(cfg().fallas);
/* Sugiere el tipo de falla según lo escrito en "Falla reportada"; el primero que coincide gana (el técnico lo puede cambiar). */
export const FALLA_RX = [
  ['Líquido / mojado', /mojad|l[ií]quid|se moj|derram|humedad|\bagua\b/i],
  ['Pantalla rota', /pantalla (rota|quebrada|partida|astillada)|display roto|vidrio roto|t[aá]ctil/i],
  ['No da imagen / no arranca', /no da imagen|no da v[ií]deo|pantalla negra|no arranca|no inicia/i],
  ['No enciende', /no enciend|no prend/i],
  ['No carga / batería', /no carg|bater[ií]a|se descarga|cargador|puerto de carga/i],
  ['No conecta (WiFi/red)', /no conecta|wi-?fi|se[ñn]al|internet|\bred\b|datos m[oó]viles/i],
  ['Teclado / botones', /teclad|teclas?|bot[oó]n|botones/i],
  ['Lento / virus / sistema', /lento|se traba|cuelga|virus|reinstal|software|sistema operativo/i],
  ['Limpieza / mantenimiento', /limpiez|mantenimiento|pasta t[eé]rmica/i]
];
export function detectarFalla(txt) {
  const s = String(txt || '').toLowerCase();
  if (s.trim().length < 4) return '';
  const hit = FALLA_RX.find(([, rx]) => rx.test(s));
  return hit ? hit[0] : '';
}
/* Arma el desplegable de tipos de falla con la lista configurada (conserva lo que estaba elegido). */
export function drawFallas() {
  const cur = $('fFt').value, L = fallas();
  $('fFt').innerHTML = '<option value="">— sin clasificar —</option>' + L.map(f => `<option>${esc(f)}</option>`).join('');
  if (cur && L.includes(cur)) $('fFt').value = cur;
}

export const EQUIPOS_DEF = ['Celular', 'Notebook', 'PC de escritorio', 'Tablet', 'Impresora', 'Monitor', 'TV', 'Consola', 'Electrodoméstico', 'Otro'];
export function listaEquipos(txt) {
  const L = String(txt || '').split('\n').map(s => s.trim()).filter(Boolean);
  return L.length ? L : EQUIPOS_DEF;
}
export const equipos = () => listaEquipos(cfg().equipos);
/* Sugiere el tipo de equipo según lo escrito en "Equipo"; el primero que coincide gana (el técnico lo puede cambiar). */
export const EQUIPO_RX = [
  ['Notebook', /note|lap(top)?|macbook|ultrabook/i],
  ['Tablet', /tablet|\bipad\b|\btab\b/i],
  ['Celular', /celu|smart ?phone|\bphone\b|m[oó]vil|iphone|xiamo|samsung|moto [gez]/i],
  ['Impresora', /impres|printer|l[aá]ser|multifunci[oó]n/i],
  ['Monitor', /\bmonitor\b|pantalla led|pantalla lg/i],
  ['Consola', /play ?station|\bps[2-5]\b|xbox|nintendo|switch|consola/i],
  ['Electrodoméstico', /lavarrop|heladera|microondas|licuadora|ventilador|aire acond|electrodom/i],
  ['TV', /\btv\b|televisor|smart ?tv/i],
  ['PC de escritorio', /\bpc\b|escritorio|torre|all.?in.?one|\baio\b/i]
];
export function detectarEquipo(txt) {
  const s = String(txt || '').toLowerCase();
  if (s.trim().length < 3) return '';
  const hit = EQUIPO_RX.find(([, rx]) => rx.test(s));
  return hit ? hit[0] : '';
}
export function drawEquipos() {
  const cur = $('fEt').value, L = equipos();
  $('fEt').innerHTML = '<option value="">— sin clasificar —</option>' + L.map(e => `<option>${esc(e)}</option>`).join('');
  if (cur && L.includes(cur)) $('fEt').value = cur;
}
