"""Agregados del panel de estadísticas, calculados en el servidor.

El navegador ya tiene todas las órdenes (las necesita para poder trabajar sin conexión), así que este resumen
es un atajo: cuando hay conexión y no quedan cambios sin sincronizar, el panel lo pide acá en vez de recorrer
miles de órdenes en el celular. Las cuentas son las mismas que las del cálculo local (ver
crm/web/static/js/panel.js) para que los números no cambien según de dónde salgan.
"""
import math
from datetime import datetime, timedelta, timezone

MESES = 12   # meses que muestra el gráfico
TOP = 8      # elementos por ranking (fallas, equipos, técnicos, marcas, estados)


def _n(x):
    """Igual que num() en el navegador: acepta coma decimal y cualquier cosa rara vale 0."""
    try: return float(str("" if x is None else x).replace(",", "."))
    except ValueError: return 0.0


def _cant(r):
    """Igual que cantR(): al menos 1 unidad (Math.round redondea .5 hacia arriba, round() de Python no)."""
    return max(1, math.floor((_n(r.get("cant")) or 1) + 0.5))


def _costo(o):
    """Costo de los repuestos de una orden (cantidad × costo unitario)."""
    return sum(_n(r.get("costo")) * _cant(r) for r in (o.get("repuestos") or []))


def _dia(iso):
    return str(iso or "")[:10]


def _en_rango(iso, desde, hasta):
    """El rango se compara contra los primeros 10 caracteres, igual que enRango() en el navegador."""
    d = _dia(iso)
    return bool(d) and (not desde or d >= desde) and (not hasta or d <= hasta)


def _mes(iso, tz):
    """'YYYY-MM' en la hora del navegador (ym() del panel). tz = minutos a sumar a UTC."""
    s = str(iso or "")
    if len(s) >= 19 and s[10] == "T":
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo: d = d.astimezone(timezone(timedelta(minutes=tz)))
            return d.strftime("%Y-%m")
        except ValueError: pass
    return s[:7]


def _ultimos_meses(n, hasta):
    """Los n meses que terminan en 'hasta' ('YYYY-MM-DD'); si no viene, hoy."""
    d = datetime.strptime(hasta, "%Y-%m-%d") if hasta else datetime.now()
    out = []
    for i in range(n - 1, -1, -1):
        m = d.month - i
        out.append("%04d-%02d" % (d.year + (m - 1) // 12, (m - 1) % 12 + 1))
    return out


def _top(pares, n=TOP):
    """Ranking igual que topN(): cuenta apariciones y deja las n más grandes (empates: el primero que aparece)."""
    c = {}
    for x in pares:
        if x in c: c[x] += 1
        else: c[x] = 1
    return [{"label": k, "value": v} for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:n]]


def datos(ordenes, cfg, desde="", hasta="", tz="0"):
    """Cuenta lo que muestra el panel para el período pedido (desde/hasta vacíos = todo el historial)."""
    try: tzc = int(float(tz or 0))
    except ValueError: tzc = 0
    ing = [o for o in ordenes if _en_rango(o.get("creada"), desde, hasta)]
    ent = [o for o in ordenes if o.get("entrega_fecha") and _en_rango(o.get("entrega_fecha"), desde, hasta)]
    fact = sum(_n(o.get("monto")) for o in ent)
    cost = sum(_costo(o) for o in ent)
    try: alerta = int(float(cfg.get("dias_alerta") or 7))
    except ValueError: alerta = 7
    sin = 0
    for o in ordenes:
        if o.get("estado") != "Listo para retirar": continue
        try: t = datetime.fromisoformat(str(o.get("estado_fecha") or o.get("creada") or "").replace("Z", "+00:00")).timestamp()
        except ValueError: continue
        if (datetime.now().timestamp() - t) / 86400 > alerta: sin += 1

    meses = _ultimos_meses(MESES, hasta or datetime.now().strftime("%Y-%m-%d"))
    por_mes = {m: {"n": 0, "fact": 0, "cost": 0} for m in meses}
    for o in ordenes:
        m = _mes(o.get("creada"), tzc)
        if m in por_mes: por_mes[m]["n"] += 1
    for o in ent:
        m = str(o.get("entrega_fecha"))[:7]
        if m in por_mes:
            por_mes[m]["fact"] += _n(o.get("monto")); por_mes[m]["cost"] += _costo(o)

    return {
        "ingresadas": len(ing),
        "pendientes": len([o for o in ing if o.get("estado") != "Entregado"]),
        "entregadas": len(ent),
        "facturado": fact,
        "repuestos": cost,
        "ganancia": fact - cost,
        "sinretirar": sin,
        "ticket": (fact / len(ent)) if ent else 0,
        "meses": meses,
        "porMes": por_mes,
        "estados": _top(o.get("estado") or "" for o in ing),
        "tecnicos": _top(o.get("tecnico") or "(sin asignar)" for o in ing),
        "equipos": _top((o.get("equipo_tipo") or "").strip() or "Sin clasificar" for o in ing),
        "marcas": _top((o.get("marca") or "").strip().lower() for o in ing if (o.get("marca") or "").strip()),
        "fallas": _top((o.get("falla_tipo") or "").strip() or "Sin clasificar" for o in ing),
    }