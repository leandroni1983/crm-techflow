"""Casos de uso de órdenes (lógica de aplicación, independiente del protocolo HTTP)."""
import time

from .db import norm_order


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
    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    hist_new = [{"f": ahora, "t": str(h.get("t", ""))[:300], "u": user["nombre"]}
                for h in (d.get("historial") or []) if isinstance(h, dict) and h.get("n")]
    res = app.service.order_save(norm_order(d), hist_new)
    app.media.clean(oid, imgs + [firma, firma_e])
    return {"seq": res["seq"], "imagenes": imgs, "firma": firma, "firma_entrega": firma_e, "historial": res["historial"]}


def delete_order(app, oid):
    app.service.order_del(oid)
    app.media.delete_order(oid)
