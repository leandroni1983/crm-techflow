/* ============ PORTAL DE SEGUIMIENTO: APROBAR / RECHAZAR PRESUPUESTO ============
   El cliente, sin usuario ni contraseña, decide desde su link privado. Manda la decisión al servidor
   (que valida el token firmado) y recarga para ver el estado nuevo. Archivo público: lo usa la página
   de seguimiento, que no requiere sesión. */
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-decision]'); if (!b) return;
  const msg = document.getElementById('apMsg'), decision = b.dataset.decision;
  if (decision === 'rechazar' && !confirm('¿Seguro que querés rechazar el presupuesto?')) return;
  const motivo = decision === 'rechazar' ? (prompt('¿Querés contarnos el motivo? (opcional)') || '') : '';
  b.disabled = true; if (msg) msg.textContent = 'Enviando…';
  try {
    const r = await fetch(b.dataset.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, motivo }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || 'No se pudo enviar');
    location.reload();
  } catch (err) {
    if (msg) msg.textContent = 'No se pudo enviar. Revisá tu conexión y probá de nuevo.';
    b.disabled = false;
  }
});
