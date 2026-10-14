"""Pasa un crm.db (SQLite) de versiones anteriores a la base configurada en DATABASE_URL (PostgreSQL). Se corre UNA vez.

    docker compose run --rm -v /ruta/a/tu/crm.db:/origen/crm.db:ro crm python -m crm migrate-sqlite /origen/crm.db

- Copia usuarios (con sus contraseñas ya protegidas), configuración y todas las órdenes con su número, historial y fotos.
- Las fotos/firmas que aún estuvieran dentro del crm.db se pasan a archivos en DATA_DIR/media.
- Todo o nada. Si el destino ya tiene datos, no toca nada.
"""
import os, sqlite3

from .db import DBUnavailable, now_ms, open_store, redact, row_to_order
from .media import MediaStore


def run(settings, src_path):
    if not os.path.isfile(src_path): print("✖ No existe el archivo de origen:", src_path); return 1
    src_path = os.path.abspath(src_path)
    url = settings.database_url
    if url.startswith("sqlite:///") and os.path.abspath(url[len("sqlite:///"):]) == src_path:
        print("✖ El destino es el mismo archivo que el origen."); return 1
    dst = open_store(url)
    try: dst.migrate()
    except DBUnavailable as e: print(f"✖ No se pudo conectar con el destino ({redact(url)}): {e}"); return 1
    i = dst.info()
    if i["ordenes"] or i["usuarios"]:
        print(f"✖ El destino ya tiene datos ({i['ordenes']} órdenes, {i['usuarios']} usuarios). No se toca nada."); return 1

    media = MediaStore(settings.media_dir)
    c = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    tablas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "ordenes" not in tablas: print("✖ El archivo no parece un crm.db (no tiene la tabla 'ordenes')."); return 1
    users = [dict(r) for r in c.execute("SELECT * FROM usuarios")] if "usuarios" in tablas else []
    cfg = {r["k"]: r["v"] for r in c.execute("SELECT k, v FROM config") if r["k"] != "pin"} if "config" in tablas else {}
    orders = []
    for r in c.execute("SELECT * FROM ordenes ORDER BY seq"):
        o = row_to_order(r); oid = str(o["id"])
        o["imagenes"] = [u for u in (media.save(oid, x) for x in o["imagenes"]) if u]
        o["firma"], o["firma_entrega"] = media.save(oid, o["firma"]), media.save(oid, o["firma_entrega"])
        o["seq"] = int(o["seq"]); o["actualizada"] = now_ms()
        orders.append(o)
    c.close()
    print(f"Origen: {len(orders)} órdenes, {len(users)} usuarios, {len(cfg)} valores de configuración")
    dst.bulk_load(users, cfg, orders)
    f = dst.info()
    ok = f["ordenes"] == len(orders) and f["usuarios"] == len(users)
    print(f"Destino: {f['ordenes']} órdenes, {f['usuarios']} usuarios · próximo número de orden: {f['ultimo_numero'] + 1}")
    print("✔ Migración verificada: las cantidades coinciden." if ok else "✖ Las cantidades NO coinciden, revisá antes de usar el destino.")
    print(f"Fotos y firmas en: {settings.media_dir}")
    return 0 if ok else 1
