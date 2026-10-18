/* ============ CAPA DE DATOS ============
   Todo el acceso a datos pasa por el objeto DB. Con server.py guarda en crm.db (SQLite);
   sin servidor usa el navegador (localStorage). Para otra base de datos, reemplazá estos métodos. */
const DEFAULTS = {
  taller: 'Mi Taller', taller_datos: '', logo: '', logo_solo: '0', prefijo: '', pais: '549',
  pdfAncho: '210', pdfAlto: '148', et_ancho: '70', et_alto: '40', garantia_dias: '90', dias_alerta: '7',
  fallas_comunes: 'No enciende\nNo carga o no toma el cargador\nPantalla rota\nSin imagen\nMuy lenta\nSe apaga sola\nSe calienta o hace ruido el ventilador\nNo arranca el sistema operativo\nVirus o malware\nTeclado o touchpad no funciona\nBatería agotada\nNo conecta a Wi-Fi\nPuerto USB o de carga dañado\nDisco dañado\nDerrame de líquido\nGolpe o caída\nNo imprime\nAtasca papel',
  checklist_items: 'Enciende, Con batería, Con cargador, Pantalla rota, Golpes visibles, Con disco / memoria',
  plantillas: 'Limpieza y pasta térmica|Limpieza interna y cambio de pasta térmica|15000\nFormateo e instalación|Formateo e instalación del sistema operativo y programas|20000',
  msg: 'Hola {cliente}! Te escribimos de {taller}. Tu orden de servicio es la N° {numero} ({equipo}). Estado actual: {estado}.',
  msgP: 'Hola {cliente}! Te escribimos de {taller} por tu orden N° {numero} ({equipo}).\n\nDiagnóstico: {diagnostico}\n\nPresupuesto: ${presupuesto}\n\nSi estás de acuerdo, respondé este mensaje para avanzar con la reparación.',
  msgListo: 'Hola {cliente}! Tu equipo ({equipo}) ya está listo para retirar en {taller}. Orden N° {numero}. Saldo a abonar: {saldo}. {garantia}',
  msgPDF: 'Hola {cliente}! Te enviamos el comprobante de ingreso de tu equipo ({equipo}). Orden N° {numero}. Gracias por confiar en {taller}.',
  msgC: 'Hola {cliente}! Recibimos tu equipo en {taller}.\n\n📋 Orden N°: {numero}\n📅 Fecha: {fecha}\n💻 Equipo: {equipo}\n🔢 N° de serie: {serie}\n🎒 Accesorios: {accesorios}\n🔍 Estado físico: {fisico}\n⚠️ Falla informada: {falla}\n\n{condiciones}\n\nGuardá este mensaje: con tu número de orden podés consultarnos el estado del equipo.',
  msgEntrega: 'Hola {cliente}! Te enviamos el comprobante de entrega de tu equipo ({equipo}). Orden N° {numero}. Saldo: {saldo}. {garantia} Gracias por confiar en {taller}.',
  condiciones_entrega: 'Recibí el equipo en conformidad y en funcionamiento. La garantía cubre únicamente la reparación realizada y los repuestos colocados; no cubre golpes, humedad, mal uso ni intervenciones de terceros.',
  condiciones: 'Condiciones: el presupuesto puede variar si aparecen fallas adicionales. Pasados 90 días del aviso de reparación sin retirar el equipo, el taller no se responsabiliza por el mismo.'
};

const ordenVacia = () => ({
  cliente: '', tel: '', direccion: '', equipo: '', marca: '', color: '', serie: '', accesorios: '', fisico: '', deteriorado: '',
  clave: '', problema: '', diagnostico: '', monto: '', autoriza: '', sena: '', pagado: '', estado: 'Recibido', estado_fecha: '',
  hora: '', cliente_id: '', equipo_id: '', entrega_est: '', entrega_fecha: '', garantia_fab: '', observ: '', firma: '', firma_entrega: '', tecnico: '',
  checklist: [], repuestos: [], historial: [], imagenes: [], fallas: []
});
const norm = o => { const b = { ...ordenVacia(), ...o }; for (const k of ['checklist', 'repuestos', 'historial', 'imagenes', 'fallas']) if (!Array.isArray(b[k])) b[k] = []; return b; };

const DB = {
  K: 'crm-tecnico-v1', api: false, usuario: null, tecnicos: [], sync: null,
  data: { ordenes: [], clientes: [], equipos: [], config: { ...DEFAULTS }, seq: 0 },
  /* La sesión viaja en una cookie HttpOnly; si el servidor responde 401 volvemos al login. */
  async req(path, opt = {}) {
    const r = await fetch(path, { ...opt, headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' });
    if (r.status === 401) { location.href = '/login'; throw new Error('sesión vencida'); }
    return r;
  },
  async load() {
    try {
      const r = await this.req('/api/data');
      if (r.ok) {
        const d = await r.json(); this.api = true; this.usuario = d.usuario || null; this.tecnicos = d.tecnicos || []; this.sync = d.sync || null;
        this.data.ordenes = d.ordenes.map(norm); this.data.clientes = d.clientes || []; this.data.equipos = d.equipos || [];
        this.data.config = { ...DEFAULTS, ...(d.config || {}) };
        return this.data;
      }
    } catch (e) { if (e.message === 'sesión vencida') return 'login'; /* sin servidor: se usa el navegador */ }
    try {
      const r = localStorage.getItem(this.K);
      if (r) { const d = JSON.parse(r); this.data = { ...this.data, ...d, config: { ...DEFAULTS, ...d.config } }; this.data.ordenes = this.data.ordenes.map(norm); }
    } catch (e) { console.warn(e); }
    return this.data;
  },
  /* Clientes y equipos (necesitan el servidor). Después de guardar se recarga todo: el servidor también actualiza los datos de sus órdenes. */
  async _enviar(path, method, body) {
    const r = await this.req(path, { method, body: body ? JSON.stringify(body) : undefined });
    const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.error || 'No se pudo completar la acción');
    await this.load(); return d;
  },
  saveCliente(c) { return this._enviar('/api/cliente', 'POST', c); },
  saveEquipo(e) { return this._enviar('/api/equipo', 'POST', e); },
  delCliente(id) { return this._enviar('/api/cliente/' + encodeURIComponent(id), 'DELETE'); },
  delEquipo(id) { return this._enviar('/api/equipo/' + encodeURIComponent(id), 'DELETE'); },
  async save() {
    if (this.api) return true;
    try { localStorage.setItem(this.K, JSON.stringify(this.data)); return true; }
    catch (e) { alert('No se pudo guardar en el navegador (¿demasiadas fotos?).'); return false; }
  },
  async upsert(o) {
    const L = this.data.ordenes, i = L.findIndex(x => x.id === o.id);
    if (this.api) {
      try {
        const r = await this.req('/api/orden', { method: 'POST', body: JSON.stringify(o) });
        if (!r.ok) { const e = await r.json().catch(() => ({})); alert(e.error || 'No se pudo guardar la orden.'); return false; }
        const d = await r.json(); o.seq = d.seq;
        if (d.imagenes) o.imagenes = d.imagenes;
        if (d.firma !== undefined) o.firma = d.firma;
        if (d.firma_entrega !== undefined) o.firma_entrega = d.firma_entrega;
        if (d.historial) o.historial = d.historial;
        o.cliente_id = d.cliente_id || ''; o.equipo_id = d.equipo_id || '';
        for (const [lista, reg] of [[this.data.clientes, d.cliente], [this.data.equipos, d.equipo]]) {  // el cliente y el equipo nuevos ya aparecen sin recargar
          if (!reg) continue; const k = lista.findIndex(x => x.id === reg.id); if (k >= 0) lista[k] = reg; else lista.push(reg);
        }
      } catch (e) { alert('No se pudo guardar: no hay conexión con el servidor del CRM.'); return false; }
      if (i >= 0) L[i] = o; else L.unshift(o);
      return true;
    }
    if (i >= 0) L[i] = o; else { this.data.seq++; o.seq = this.data.seq; L.unshift(o); }
    return this.save();
  },
  async remove(id) {
    this.data.ordenes = this.data.ordenes.filter(x => x.id !== id);
    if (this.api) { try { await this.req('/api/orden/' + id, { method: 'DELETE' }); } catch (e) { alert('No se pudo borrar en la base.'); return false; } return true; }
    return this.save();
  },
  async saveConfig(c) {
    this.data.config = c;
    if (this.api) {
      try { await this.req('/api/config', { method: 'POST', body: JSON.stringify(c) }); } catch (e) { alert('No se pudo guardar la configuración.'); return false; }
      return true;
    }
    return this.save();
  }
};
