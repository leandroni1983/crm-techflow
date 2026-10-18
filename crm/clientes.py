"""Casos de uso de clientes y equipos (alta y edición desde la pantalla de Clientes)."""
import secrets

from .db import id_cliente, id_equipo


def _s(d, k, n=200): return str(d.get(k) or "").strip()[:n]


def save_cliente(app, d):
    nombre, tel = _s(d, "nombre", 120), _s(d, "tel", 40)
    if not nombre: raise ValueError("El cliente necesita un nombre")
    cid, nuevo = _s(d, "id"), id_cliente(tel, nombre)
    choque = app.service.cliente_por_tel(tel) or app.service.get_cliente(nuevo)  # ese teléfono (o ese nombre, si no hay teléfono) ya es de otro cliente
    if cid and choque and choque["id"] != cid: raise ValueError(f"Ese teléfono ya pertenece a {choque['nombre']}")
    if not cid:
        if choque: raise ValueError(f"Ya existe un cliente con ese teléfono: {choque['nombre']}")
        cid = nuevo
    previo = app.service.get_cliente(cid) or {}
    return app.service.cliente_save({"id": cid, "nombre": nombre, "tel": tel, "direccion": _s(d, "direccion"), "email": _s(d, "email", 120),
                                     "notas": _s(d, "notas", 1000), "creado": previo.get("creado")})


def save_equipo(app, d):
    cid = _s(d, "cliente_id")
    if not cid or not app.service.get_cliente(cid): raise ValueError("El equipo tiene que pertenecer a un cliente existente")
    tipo, marca, serie = _s(d, "tipo", 120), _s(d, "marca", 80), _s(d, "serie", 80)
    if not (tipo or marca or serie): raise ValueError("Cargá al menos el tipo, la marca o el número de serie")
    eid, nuevo = _s(d, "id"), id_equipo(cid, serie, tipo, marca)
    choque = app.service.equipo_por_clave(cid, serie, tipo, marca)
    igual = "Ya hay otro equipo igual de este cliente (mismo número de serie, o mismo tipo y marca). Agregá el número de serie para diferenciarlos."
    if eid and choque and choque["id"] != eid: raise ValueError(igual)
    if not eid:
        if choque: raise ValueError(igual)
        eid = nuevo or "e" + secrets.token_hex(6)
    previo = app.service.get_equipo(eid) or {}
    return app.service.equipo_save({"id": eid, "cliente_id": cid, "tipo": tipo, "marca": marca, "serie": serie, "color": _s(d, "color", 60),
                                    "notas": _s(d, "notas", 1000), "creado": previo.get("creado")})
