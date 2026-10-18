"""Casos de uso de órdenes (lógica de aplicación, independiente del protocolo HTTP)."""
import time

from .db import id_cliente, id_equipo, norm_order


def save_order(app, user, d):
    """Guarda una orden enviada por el cliente.
    - fotos/firmas (dataURL) pasan a archivos y la base guarda solo la ruta;
    - el historial NO se acepta tal cual: solo se agregan las entradas nuevas (marcadas n) y el servidor pone
      la fecha y el usuario, así nadie puede falsear ni reescribir lo anterior;
    - el número de orden lo decide el servidor, nunca el cliente."""
    oid = str(d["id"])
    d.pop("seq", None); d.pop("actualizada", None)
    imgs = [u for u in (app.media.save(oid, x) for x in (d.get("imagenes") or [])) if u]
    firma, firma_e = app.media.save(oid, d.get("firma", "")), app.media.save(oid, d.get("firma_entrega", ""))
    d["id"], d["imagenes"], d["firma"], d["firma_entrega"] = oid, imgs, firma, firma_e
    d["fallas"] = [str(x).strip()[:80] for x in (d.get("fallas") or []) if str(x).strip()] if isinstance(d.get("fallas"), list) else []
    cliente, equipo = _cliente_y_equipo(app, d)
    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    hist_new = [{"f": ahora, "t": str(h.get("t", ""))[:300], "u": user["nombre"]}
                for h in (d.get("historial") or []) if isinstance(h, dict) and h.get("n")]
    res = app.service.order_save(norm_order(d), hist_new, cliente=cliente, equipo=equipo)
    app.media.clean(oid, imgs + [firma, firma_e])
    return {"seq": res["seq"], "imagenes": imgs, "firma": firma, "firma_entrega": firma_e, "historial": res["historial"],
            "cliente_id": d["cliente_id"], "equipo_id": d["equipo_id"],
            "cliente": app.service.get_cliente(d["cliente_id"]), "equipo": app.service.get_equipo(d["equipo_id"])}


def _cliente_y_equipo(app, d):
    """Vincula la orden con su cliente y su equipo. Si todavía no existen se crean junto con la orden (nunca se pisan los existentes:
    para cambiar sus datos se edita el cliente o el equipo). Los ids salen del teléfono y del número de serie, así el mismo
    cliente o equipo no se duplica aunque se cargue desde dos dispositivos o sin conexión."""
    svc = app.service
    cid = str(d.get("cliente_id") or "").strip()
    if not cid:
        existente = svc.cliente_por_tel(d.get("tel"))
        cid = existente["id"] if existente else id_cliente(d.get("tel"), d.get("cliente"))
    d["cliente_id"] = cid
    if not cid: d["equipo_id"] = ""; return None, None
    cliente = None if svc.get_cliente(cid) else {"id": cid, "nombre": d.get("cliente", ""), "tel": d.get("tel", ""), "direccion": d.get("direccion", ""), "creado": d.get("creada")}
    eid = str(d.get("equipo_id") or "").strip()
    prev = svc.get_equipo(eid) if eid else None
    if not eid or (prev and prev["cliente_id"] != cid):
        existente = svc.equipo_por_clave(cid, d.get("serie"), d.get("equipo"), d.get("marca"))
        eid = existente["id"] if existente else id_equipo(cid, d.get("serie"), d.get("equipo"), d.get("marca"))
    d["equipo_id"] = eid
    equipo = None
    if eid and not svc.get_equipo(eid):
        equipo = {"id": eid, "cliente_id": cid, "tipo": d.get("equipo", ""), "marca": d.get("marca", ""), "serie": d.get("serie", ""), "color": d.get("color", ""), "creado": d.get("creada")}
    return cliente, equipo


def delete_order(app, oid):
    app.service.order_del(oid)
    app.media.delete_order(oid)
