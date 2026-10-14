"""Modelo de datos: columnas de la orden y funciones para normalizarla. Sin dependencias de base de datos."""
import json, time

TEXT_COLS = ["cliente", "tel", "direccion", "equipo", "equipo_tipo", "marca", "color", "serie", "accesorios", "fisico", "deteriorado",
             "clave", "falla_tipo", "problema", "diagnostico", "monto", "autoriza", "sena", "pagado", "estado", "estado_fecha", "hora",
             "entrega_est", "entrega_fecha", "garantia_fab", "observ", "firma", "firma_entrega", "tecnico", "borrada",
             "prioridad", "presu_estado", "presu_fecha", "presu_motivo", "presu_quien"]
JSON_COLS = ["checklist", "repuestos", "historial", "imagenes", "pagos"]
ORDER_COLS = ["id", "seq"] + TEXT_COLS + JSON_COLS + ["creada", "actualizada"]


def now_iso(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def now_ms():
    """Marca de tiempo con milisegundos: sirve para detectar si una orden cambió mientras se trabajaba sin conexión."""
    t = time.time(); return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def norm_order(o):
    d = dict(o)
    for k in TEXT_COLS: d[k] = "" if d.get(k) is None else str(d[k])
    for k in JSON_COLS:
        if k == "pagos":
            if isinstance(d.get(k), list): d[k] = d[k]
            elif isinstance(d.get(k), str) and d[k]:
                try: d[k] = json.loads(d[k])
                except Exception: d[k] = []
            else: d[k] = []
        else:
            d[k] = d[k] if isinstance(d.get(k), list) else []
    d["actualizada"] = d.get("actualizada") or ""
    return d


def row_to_order(r):
    d = dict(r)
    for k in TEXT_COLS: d[k] = "" if d.get(k) is None else d[k]
    for k in JSON_COLS:
        try:
            if k == "pagos":
                try: d[k] = json.loads(d.get(k) or "[]")
                except Exception: d[k] = []
            else: d[k] = json.loads(d.get(k) or "[]")
        except Exception:
            d[k] = []
    d["actualizada"] = d.get("actualizada") or ""
    return d
