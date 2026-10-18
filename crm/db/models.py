"""Modelo de datos: columnas de la orden y funciones para normalizarla. Sin dependencias de base de datos."""
import hashlib, json, re, time

TEXT_COLS = ["cliente", "tel", "direccion", "equipo", "marca", "color", "serie", "accesorios", "fisico", "deteriorado",
             "clave", "problema", "diagnostico", "monto", "autoriza", "sena", "pagado", "estado", "estado_fecha", "hora",
             "entrega_est", "entrega_fecha", "garantia_fab", "observ", "firma", "firma_entrega", "tecnico", "cliente_id", "equipo_id"]
JSON_COLS = ["checklist", "repuestos", "historial", "imagenes", "fallas"]
ORDER_COLS = ["id", "seq"] + TEXT_COLS + JSON_COLS + ["creada", "actualizada"]
CLIENTE_COLS = ["id", "nombre", "tel", "direccion", "email", "notas", "creado", "actualizado"]
EQUIPO_COLS = ["id", "cliente_id", "tipo", "marca", "serie", "color", "notas", "creado", "actualizado"]


# ---- identidad de clientes y equipos: ids determinísticos, así el mismo teléfono/serie siempre da el mismo registro
def tel_key(t):
    """Clave de un teléfono: los últimos 10 dígitos (iguala "011 5555-1234", "1155551234" y "+54 9 11 5555 1234")."""
    d = re.sub(r"\D", "", str(t or "")).lstrip("0")
    return d[-10:] if len(d) >= 10 else d


def _h(s): return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def id_cliente(tel, nombre):
    k = tel_key(tel) or ("n:" + str(nombre or "").strip().lower() if str(nombre or "").strip() else "")
    return "c" + _h(k) if k else ""


def id_equipo(cid, serie, tipo, marca):
    s = str(serie or "").strip().lower(); tm = f"{str(tipo or '').strip()}|{str(marca or '').strip()}".lower()
    k = "s:" + s if s else ("t:" + tm if tm != "|" else "")
    return "e" + _h(cid + "|" + k) if cid and k else ""


def now_iso(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def now_ms():
    """Marca de tiempo con milisegundos: sirve para detectar si una orden cambió mientras se trabajaba sin conexión."""
    t = time.time(); return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def norm_order(o):
    d = dict(o)
    for k in TEXT_COLS: d[k] = "" if d.get(k) is None else str(d[k])
    for k in JSON_COLS: d[k] = d[k] if isinstance(d.get(k), list) else []
    d["actualizada"] = d.get("actualizada") or ""
    return d


def row_to_order(r):
    d = dict(r)
    for k in TEXT_COLS: d[k] = "" if d.get(k) is None else d[k]
    for k in JSON_COLS:
        try: d[k] = json.loads(d.get(k) or "[]")
        except Exception: d[k] = []
    d["actualizada"] = d.get("actualizada") or ""
    return d
