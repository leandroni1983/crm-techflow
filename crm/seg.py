"""Portal de seguimiento para el cliente: un link privado por orden, sin usuario ni contraseña.

El token no se guarda en ningún lado: se calcula con HMAC a partir de una clave secreta que vive en la
configuración y *nunca* se manda al navegador, más el número y el id de la orden. Como depende solo de eso,
el link es siempre el mismo (no vence) y no se puede adivinar ni cambiar por el de otra orden.

La página muestra únicamente lo que le sirve al cliente (estado, fechas, saldo): las notas internas del taller
y la contraseña del equipo no salen nunca de acá.
"""
import hashlib, hmac, os

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "templates")
PLANTILLA = os.path.join(WEB, "seguimiento.html")
ESTADOS = ["Recibido", "En diagnóstico", "Presupuesto", "Esperando repuesto", "En reparación", "Listo para retirar", "Entregado", "Aprobado", "Rechazado"]


def token(clave, seq, oid):
    """Token corto y estable de la orden. Sin la clave secreta no se puede calcular ni falsificar."""
    return hmac.new(str(clave).encode(), f"{seq}:{oid}".encode(), hashlib.sha256).hexdigest()[:12]


def valido(clave, seq, oid, tok):
    return bool(clave) and hmac.compare_digest(token(clave, seq, oid), str(tok or ""))


def _num(s):
    try: return float(str(s or "").replace(",", "."))
    except ValueError: return 0.0


def _esc(s): return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _fecha(s):
    """'2026-07-04' o '2026-07-04T10:20:30Z' -> '04/07/2026'."""
    s = str(s or "")
    return f"{s[8:10]}/{s[5:7]}/{s[0:4]}" if len(s) >= 10 and s[4] == "-" and s[7] == "-" else s


def _money(s):
    n = _num(s)
    return "" if not n else "$ " + f"{round(n):,.0f}".replace(",", ".")


def numero(cfg, o):
    """El mismo número que ve el taller en pantalla y en el comprobante (prefijo + número + fecha de ingreso)."""
    c = str(o.get("creada") or "")
    d = (c[8:10], c[5:7], c[2:4]) if len(c) >= 10 else ("", "", "")
    return f'{cfg.get("prefijo", "")}{int(o.get("seq") or 0):04d}{d[0]}{d[1]}{d[2]}'


def _pasos(estado):
    """Los estados del taller, marcando los que ya pasó: el cliente ve de un vistazo en qué anda."""
    try: i = ESTADOS.index(estado)
    except ValueError: return ""
    return "".join(f'<div class="paso{" hecho" if j < i else ""}{" ahora" if j == i else ""}"><span class="pt">{j + 1}</span>'
                   f'<span>{_esc(e)}</span></div>' for j, e in enumerate(ESTADOS))


def _historial(o):
    """Solo los cambios de estado; el resto de las anotaciones son internas del taller."""
    h = [x for x in (o.get("historial") or []) if str(x.get("t", "")).startswith("Estado:")]
    if not h: return ""
    return ('<h2 style="font-size:15px;margin:16px 0 4px">Movimientos</h2>'
            + "".join(f'<div class="kv"><span>{_esc(_fecha(x.get("f")))}</span><span class="mut">{_esc(x.get("t"))}</span></div>'
                      for x in h[-8:]))


def _acciones(o, token):
    """Que el cliente apruebe o rechace el presupuesto desde el mismo link, sin escribir por WhatsApp."""
    if not token: return ""
    est = str(o.get("estado") or "")
    decidido = str(o.get("presu_estado") or "")
    if decidido:
        txt = "Aprobaste el presupuesto" if decidido == "Aprobado" else "Rechazaste el presupuesto"
        return f'<div class="aprob"><b>{_esc(txt)}</b> el {_esc(_fecha(o.get("presu_fecha")))}. Gracias!</div>'
    if est != "Presupuesto": return ""
    url = f"/seguimiento/{int(o.get('seq') or 0)}/{_esc(token)}/estado"
    return ('<div class="aprob"><div style="margin-bottom:8px">¿Estás de acuerdo con el presupuesto?</div>'
            f'<div class="acts"><button type="button" id="bAprobar" data-decision="aprobar" data-url="{url}">✅ Aprobar</button>'
            f'<button type="button" class="dg" data-decision="rechazar" data-url="{url}">❌ Rechazar</button></div>'
            '<div id="apMsg" class="mut" style="margin-top:8px"></div></div>')


def pagina(cfg, o, token=""):
    """Arma la página del cliente. Es HTML propio y liviano: se puede abrir en cualquier celular."""
    with open(PLANTILLA, encoding="utf-8") as f: t = f.read()
    estado = str(o.get("estado") or "")
    saldo = 0 if o.get("pagado") else max(_num(o.get("monto")) - _num(o.get("sena")) - sum(_num(p.get("monto")) for p in (o.get("pagos") or [])), 0)
    entrega = o.get("entrega_est") or o.get("entrega_fecha")
    clase = "ok" if estado in ("Entregado", "Aprobado") else ("warn" if estado in ("Listo para retirar", "Rechazado") else "")
    reempl = {
        "taller": _esc(cfg.get("taller") or "Taller"), "numero": _esc(numero(cfg, o)), "cliente": _esc(o.get("cliente")),
        "equipo": _esc(" ".join(x for x in (o.get("equipo"), o.get("marca")) if x)) or "—", "estado": _esc(estado) or "—",
        "clase": clase, "ingreso": _esc(_fecha(o.get("creada"))), "pasos": _pasos(estado), "historial": _historial(o),
        "entrega": f'<div class="kv"><span>Entrega estimada</span><span>{_esc(_fecha(entrega))}</span></div>' if entrega else "",
        "saldo": f'<div class="kv"><span>Saldo a pagar</span><span>{_esc(_money(saldo))}</span></div>' if saldo else "",
        "datos": _esc(cfg.get("taller_datos")), "acciones": _acciones(o, token),
    }
    for k, v in reempl.items(): t = t.replace("{{" + k + "}}", v)
    return t


def invalido():
    """Página para un link mal escrito o cambiado a mano. No dice si la orden existe o no."""
    return ("<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex,follow\"><title>Link no válido</title>"
            "<link rel=\"stylesheet\" href=\"/static/css/styles.css\"></head><body>"
            "<div class=\"wrap\" style=\"max-width:480px;margin-top:12vh\"><div class=\"card\">"
            "<h1>Link no válido</h1><div class=\"mut\" style=\"margin-top:8px\">Este link de seguimiento no corresponde a "
            "ninguna orden. Pedile al taller el link nuevo (es el mismo para cada orden, no vence).</div>"
            "</div></div></body></html>")
