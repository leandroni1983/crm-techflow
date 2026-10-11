#!/usr/bin/env python3
"""Pasa tu crm.db (SQLite) a la base de DATABASE_URL (PostgreSQL). Se corre UNA sola vez.

Docker:
  docker compose run --rm -v /ruta/a/tu/crm.db:/origen/crm.db:ro crm python migrar_sqlite_a_postgres.py /origen/crm.db
Sin Docker:
  DATABASE_URL=postgresql://... python migrar_sqlite_a_postgres.py ./crm.db

- Copia usuarios (con sus contraseñas ya protegidas), configuración y todas las órdenes con su número, historial y fotos.
- Las fotos/firmas que aún estuvieran dentro del crm.db se pasan a archivos en DATA_DIR/media.
- Todo o nada: si algo falla no queda nada a medias. Si el destino ya tiene datos, no toca nada.
"""
import json, os, sqlite3, sys
from media import MEDIA, save_media
from store import DBUnavailable, norm_order, open_store, redact, row_to_order, now_iso

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def main():
    if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]): sys.exit("Uso: python migrar_sqlite_a_postgres.py RUTA/crm.db")
    src_path = os.path.abspath(sys.argv[1])
    if not DATABASE_URL: sys.exit("Definí DATABASE_URL con la base de destino (postgresql://...).")
    if DATABASE_URL.startswith("sqlite:///") and os.path.abspath(DATABASE_URL[len("sqlite:///"):]) == src_path:
        sys.exit("✖ El destino es el mismo archivo que el origen.")
    dst = open_store(DATABASE_URL)
    try: dst.migrate()
    except DBUnavailable as e: sys.exit(f"✖ No se pudo conectar con el destino ({redact(DATABASE_URL)}): {e}")
    i = dst.info()
    if i["ordenes"] or i["usuarios"]:
        sys.exit(f"✖ El destino ya tiene datos ({i['ordenes']} órdenes, {i['usuarios']} usuarios). No se toca nada.")

    c = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True); c.row_factory = sqlite3.Row
    tablas = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "ordenes" not in tablas: sys.exit("✖ El archivo no parece un crm.db (no tiene la tabla 'ordenes').")
    users = [dict(r) for r in c.execute("SELECT * FROM usuarios")] if "usuarios" in tablas else []
    cfg = {r["k"]: r["v"] for r in c.execute("SELECT k, v FROM config") if r["k"] != "pin"} if "config" in tablas else {}
    orders = []
    for r in c.execute("SELECT * FROM ordenes ORDER BY seq"):
        o = row_to_order(r); oid = str(o["id"])
        o["imagenes"] = [u for u in (save_media(oid, x) for x in o["imagenes"]) if u]
        o["firma"], o["firma_entrega"] = save_media(oid, o["firma"]), save_media(oid, o["firma_entrega"])
        o["seq"] = int(o["seq"]); o["actualizada"] = now_iso()
        orders.append(o)
    c.close()
    print(f"Origen: {len(orders)} órdenes, {len(users)} usuarios, {len(cfg)} valores de configuración")
    dst.bulk_load(users, cfg, orders)
    f = dst.info()
    ok = f["ordenes"] == len(orders) and f["usuarios"] == len(users)
    print(f"Destino: {f['ordenes']} órdenes, {f['usuarios']} usuarios · próximo número de orden: {f['ultimo_numero'] + 1}")
    print("✔ Migración verificada: las cantidades coinciden." if ok else "✖ Las cantidades NO coinciden, revisá antes de usar el destino.")
    print(f"Fotos y firmas en: {MEDIA}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
