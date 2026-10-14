"""Respaldo y restauración de la base en un solo archivo JSON (configuración, usuarios y órdenes).

Las fotos y firmas NO van dentro del archivo: son archivos sueltos en la carpeta `media/`
(copiala aparte, o respaldá la carpeta `data/` completa del servidor).
"""
import json, os, time

from . import __version__


def dump(store):
    """Arma el respaldo. Incluye TODAS las órdenes, también las que están en la papelera."""
    return {"app": "crm-tecnico", "version": __version__, "fecha": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": store.config_all(), "usuarios": store.users_full(), "ordenes": store.orders_all()}


def save(store, destino):
    """Escribe el respaldo en `destino` y devuelve cuántas órdenes incluyó."""
    d = dump(store)
    if os.path.dirname(destino): os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    return len(d["ordenes"])


def load(store, origen):
    """Restaura un respaldo: agrega los usuarios y las órdenes que falten y pisa la configuración.
    No borra nada de lo que ya estaba (si una orden existe, el respaldo la actualiza)."""
    with open(origen, encoding="utf-8") as f: d = json.load(f)
    if not isinstance(d, dict) or "ordenes" not in d: raise ValueError("el archivo no parece un respaldo del CRM")
    ordenes = [o for o in (d.get("ordenes") or []) if isinstance(o, dict) and o.get("id")]
    store.bulk_load([u for u in (d.get("usuarios") or []) if isinstance(u, dict) and u.get("nombre")],
                    d.get("config") or {}, ordenes)
    return len(ordenes)
