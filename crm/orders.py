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
    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    imgs = [u for u in (app.media.save(oid, x) for x in (d.get("imagenes") or [])) if u]
    firma, firma_e = app.media.save(oid, d.get("firma", "")), app.media.save(oid, d.get("firma_entrega", ""))
    adjuntos = []
    for x in (d.get("adjuntos") or []):
        r = app.media.save_adjunto(oid, x)
        if r: adjuntos.append({**r, "f": (x.get("f") if isinstance(x, dict) else None) or ahora})
    d["id"], d["imagenes"], d["firma"], d["firma_entrega"], d["adjuntos"] = oid, imgs, firma, firma_e, adjuntos
    hist_new = [{"f": ahora, "t": str(h.get("t", ""))[:300], "u": user["nombre"]}
                for h in (d.get("historial") or []) if isinstance(h, dict) and h.get("n")]
    res = app.service.order_save(norm_order(d), hist_new)
    app.media.clean(oid, imgs + [firma, firma_e] + [a["u"] for a in adjuntos])
    return {"seq": res["seq"], "imagenes": imgs, "firma": firma, "firma_entrega": firma_e, "adjuntos": adjuntos, "historial": res["historial"]}


def delete_order(app, oid):
    app.service.order_del(oid)
    app.media.delete_order(oid)


def decidir_presupuesto(app, o, decision, motivo=""):
    """El cliente aprueba o rechaza el presupuesto desde el portal (sin usuario ni contraseña).
    Se anota en el historial con el usuario "cliente" y, si la orden estaba en Presupuesto, cambia de estado."""
    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    o = dict(o)
    ok = decision == "aprobar"
    o["presu_estado"] = "Aprobado" if ok else "Rechazado"
    o["presu_fecha"] = ahora
    o["presu_motivo"] = str(motivo or "")[:300]
    o["presu_quien"] = "cliente"
    if o.get("estado") in ("Recibido", "En diagnóstico", "Presupuesto"):
        o["estado"], o["estado_fecha"] = ("Aprobado" if ok else "Rechazado"), ahora
    t = "El cliente aprobó el presupuesto desde el portal de seguimiento" if ok else "El cliente rechazó el presupuesto desde el portal de seguimiento"
    if not ok and o["presu_motivo"]: t += f". Motivo: {o['presu_motivo']}"
    return app.service.order_save(norm_order(o), [{"f": ahora, "t": t, "u": "cliente"}])
