/* Service worker del CRM: deja la app instalable y abre rápido.
   Solo guarda la "carcasa" (HTML, CSS, JS, íconos). Los datos (/api) y las fotos (/media) siempre van a la red,
   así nunca se muestran datos viejos ni se guardan datos de clientes en el caché del dispositivo. */
const CACHE = 'crm-shell-v4';
const SHELL = ['/', '/login', '/manifest.webmanifest', '/static/css/styles.css', '/static/js/login.js', ...['db', 'util', 'dominio', 'comprobantes', 'dashboard', 'lista', 'clientes', 'orden', 'config', 'app'].map(n => `/static/js/${n}.js`),
               '/static/img/icon-192.png', '/static/img/icon-512.png', '/static/img/favicon.png'];

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin || !SHELL.includes(u.pathname)) return;
  e.respondWith((async () => {
    try {                                   // primero la red: así las actualizaciones se ven enseguida
      const res = await fetch(r);
      if (res.ok && !res.redirected) (await caches.open(CACHE)).put(u.pathname, res.clone());
      return res;
    } catch (err) {                         // sin conexión: la última versión guardada
      const hit = await caches.match(u.pathname);
      if (hit) return hit;
      throw err;
    }
  })());
});
