const $ = id => document.getElementById(id);
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
$('f').onsubmit = async e => {
  e.preventDefault(); $('err').textContent = ''; $('go').disabled = true;
  try {
    const r = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario: $('u').value, password: $('p').value }) });
    const d = await r.json().catch(() => ({}));
    if (r.ok) {
      const chk = await fetch('/api/data', { credentials: 'same-origin' });
      if (chk.ok) { location.href = '/'; return; }
      $('err').textContent = 'La clave es correcta pero el navegador no guardó la sesión. Probá entrar por la dirección https o revisá que no bloquees cookies.';
      $('go').disabled = false; return;
    }
    $('err').textContent = d.error || 'No se pudo iniciar sesión'; $('p').value = ''; $('p').focus();
  } catch (x) { $('err').textContent = 'No se pudo conectar con el servidor'; }
  $('go').disabled = false;
};
