/* Comprobantes: filas, QR, impresión, etiqueta y PDF */
const chkItems = () => cfg().checklist_items.split(',').map(s => s.trim()).filter(Boolean);
function checklistTxt(o) {
  const items = [...new Set([...chkItems(), ...o.checklist])];
  return items.map(i => (o.checklist.includes(i) ? '[X] ' : '[  ] ') + i).join('   ');
}
function filasComp(o) {
  const v = vars(o), f = [];
  f.push(['Fecha', v.fecha + (o.hora ? ' ' + o.hora : '')], ['Cliente', o.cliente], ['Teléfono', o.tel]);
  if (o.direccion) f.push(['Dirección', o.direccion]);
  f.push(['Equipo', nombreEq(o)]);
  if (o.color) f.push(['Color', o.color]);
  f.push(['N° de serie', o.serie], ['Accesorios', o.accesorios],
    ['Estado físico', [o.fisico, o.deteriorado && 'Deteriorado: ' + o.deteriorado].filter(Boolean).join(' · ')]);
  if (o.garantia_fab) f.push(['Garantía de fábrica', o.garantia_fab]);
  f.push(['Falla informada', fallaTxt(o), true]);
  const ck = checklistTxt(o); if (ck) f.push(['Checklist de ingreso', ck, true]);
  if (o.observ) f.push(['Observaciones', o.observ, true]);
  if (o.entrega_est) f.push(['Entrega estimada', fmtD(o.entrega_est)]);
  if (num(o.autoriza)) f.push(['Reparación directa hasta', money(num(o.autoriza))]);
  if (num(o.monto)) f.push(['Presupuesto', money(num(o.monto))]);
  return f;
}
function filasEntrega(o) {
  const v = vars(o), f = [];
  f.push(['Fecha de entrega', o.entrega_fecha ? fmtD(o.entrega_fecha) : new Date().toLocaleDateString('es-AR')], ['Orden N°', v.numero]);
  f.push(['Cliente', o.cliente], ['Teléfono', o.tel], ['Equipo', nombreEq(o)], ['N° de serie', o.serie]);
  f.push(['Falla informada', fallaTxt(o), true], ['Trabajo realizado', o.diagnostico, true]);
  const reps = o.repuestos.map(r => r.desc).filter(Boolean).join(', '); if (reps) f.push(['Repuestos colocados', reps, true]);
  if (num(o.monto)) f.push(['Importe total', money(num(o.monto))]);
  if (num(o.sena)) f.push(['Seña abonada', money(num(o.sena))]);
  f.push(['Estado de pago', o.pagado ? 'Abonado en su totalidad' : (num(o.monto) ? 'Saldo pendiente: ' + money(saldo(o)) : '-')]);
  const dias = parseInt(cfg().garantia_dias) || 0, g = garantiaHasta({ ...o, entrega_fecha: o.entrega_fecha || hoy() });
  f.push(['Garantía', dias && g ? `${dias} días · vence el ${g.toLocaleDateString('es-AR')}` : 'Sin garantía', true]);
  return f;
}
async function qrSvg(text, px) {
  if (!DB.api) return '';
  try {
    const r = await DB.req('/api/qr?t=' + encodeURIComponent(text)); if (!r.ok) return '';
    const { n, rows } = await r.json(); let d = '';
    rows.forEach((row, y) => [...row].forEach((c, x) => { if (c === '1') d += `M${x + 2} ${y + 2}h1v1h-1z`; }));
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 ${n + 4} ${n + 4}" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="${d}"/></svg>`;
  } catch (e) { return ''; }
}
function printHTML(html, w, h, m = 8) {
  $('comp').innerHTML = html;
  let st = $('pgsize'); if (!st) { st = document.createElement('style'); st.id = 'pgsize'; document.head.appendChild(st); }
  st.textContent = `@page{size:${w}mm ${h}mm;margin:${m}mm}`;
  window.print();
}
async function imprimir(o, tipo = 'ingreso') {
  const c = cfg(), v = vars(o), q = await qrSvg(v.numero, 52), ent = tipo === 'entrega';
  const celdas = (ent ? filasEntrega(o) : filasComp(o)).map(([k, x, f]) => `<div class="${f || String(x || '').length > 38 ? 'f' : ''}"><small>${esc(k)}</small>${esc(x || '-')}</div>`).join('');
  const logo = c.logo ? `<img class="logo" src="${c.logo}">` : '';
  const nombre = c.logo && c.logo_solo === '1' ? '' : `<h1>${esc(c.taller)}</h1>`;
  const firma = ent ? o.firma_entrega : o.firma;
  printHTML(`<div class="hd"><div class="l">${logo}<div>${nombre}<div class="s">${ent ? 'Comprobante de entrega' : 'Comprobante de ingreso de equipo'}\n${esc(c.taller_datos)}</div></div></div>
    <div class="nb"><div><small>N° DE ORDEN</small><b>${esc(v.numero)}</b></div>${q}</div></div><div class="cg">${celdas}</div>
    <div class="ft"><p>${esc(ent ? c.condiciones_entrega : c.condiciones)}</p><div class="fm">${firma ? `<img src="${firma}">` : ''}${ent ? 'Recibí conforme' : 'Firma del cliente'}</div><div class="fm">Firma del taller</div></div>`,
    c.pdfAncho || 210, c.pdfAlto || 148);
}
async function etiquetar(o) {
  const c = cfg(), q = await qrSvg(numOrden(o), 80);
  printHTML(`<div class="et">${q}<div><b>${esc(numOrden(o))}</b><br>${esc(o.cliente)}<br>${esc(nombreEq(o))}<br>${esc(o.tel)}</div></div>`, c.et_ancho || 70, c.et_alto || 40, 2);
}
/* Genera el PDF en el servidor (queda también en comprobantes/), lo descarga y abre el chat del cliente. */
async function enviarPDF(o, tipo = 'ingreso') {
  const ent = tipo === 'entrega';
  if (!DB.api) { alert('El PDF se genera con el servidor (server.py). Por ahora se abre la hoja para imprimir / guardar como PDF.'); return imprimir(o, tipo); }
  const c = cfg(), v = vars(o), w = window.open('', '_blank');
  try {
    const r = await DB.req('/api/comprobante', { method: 'POST', body: JSON.stringify({
      numero: v.numero, taller: c.taller, taller_datos: c.taller_datos, logo: c.logo, logo_solo: c.logo_solo,
      filas: ent ? filasEntrega(o) : filasComp(o), titulo: ent ? 'Comprobante de entrega' : 'Comprobante de ingreso de equipo',
      sufijo: ent ? '-entrega' : '', firma_label: ent ? 'Recibí conforme' : 'Firma del cliente',
      condiciones: ent ? c.condiciones_entrega : c.condiciones, firma: ent ? o.firma_entrega : o.firma, fotos: [],  // las fotos del equipo quedan en la orden; no van en el PDF que se le envía al cliente
      
      ancho_mm: c.pdfAncho, alto_mm: c.pdfAlto }) });
    if (!r.ok) throw new Error('http ' + r.status);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await r.blob()); a.download = 'Orden-' + v.numero + (ent ? '-entrega' : '') + '.pdf'; a.click();
    if (w) w.location = wa(o, fill(ent ? c.msgEntrega : c.msgPDF, v));
    await log(o, ent ? LOGT.entrega : LOGT.pdf); render();
    alert('El PDF se descargó (y quedó en la carpeta "comprobantes").\nEn el chat de WhatsApp tocá el clip 📎 > Documento y adjuntalo.');
  } catch (e) { if (w) w.close(); alert('No se pudo generar el PDF. ¿Está corriendo server.py?'); }
}

