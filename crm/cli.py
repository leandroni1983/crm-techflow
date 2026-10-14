"""Línea de comandos:  python -m crm [serve|check-db|list-users|reset-password|backup|restore|migrate-sqlite|version]"""
import argparse, os, sys, time

from . import __version__
from .app import App
from .config import Settings
from .db import DBUnavailable, open_store, redact
from .security import hash_pw


def _open_migrated(settings):
    st = open_store(settings.database_url)
    try: st.migrate()
    except DBUnavailable as e:
        print(f"✖ No se pudo conectar con la base ({redact(settings.database_url)}): {e}"); sys.exit(1)
    return st


def cmd_check_db(settings):
    st = _open_migrated(settings); i = st.info()
    if st.nombre == "SQLite": print("⚠ ATENCIÓN: el motor es SQLite, no PostgreSQL. Revisá DATABASE_URL.")
    print(f"✔ Motor: {st.nombre}   Base: {redact(settings.database_url)}\n✔ Esquema v{i['version']} (última del programa)\n"
          f"✔ Órdenes: {i['ordenes']}   Usuarios: {i['usuarios']}   Último número de orden: {i['ultimo_numero']}\n✔ Escritura de prueba: {i['escritura']}")
    try:
        os.makedirs(settings.media_dir, exist_ok=True); t = os.path.join(settings.data_dir, ".check"); open(t, "w").close(); os.remove(t)
        print(f"✔ Carpeta de archivos escribible: {settings.data_dir}")
    except OSError as e: print(f"✖ No se puede escribir en {settings.data_dir}: {e}")
    if i["usuarios"] == 0: print("ℹ Todavía no hay usuarios: el primero se crea con ADMIN_USER / ADMIN_PASSWORD al arrancar.")
    return 0


def cmd_list_users(settings):
    for r in _open_migrated(settings).users_full(): print(f"{r['nombre']}  ({r['rol']})")
    return 0


def cmd_reset_password(settings, usuario, clave):
    if len(clave) < 8: print("La contraseña debe tener al menos 8 caracteres"); return 1
    st, name = _open_migrated(settings), usuario.strip().lower()
    if st.user_get(name): st.user_set_hash(name, hash_pw(clave))
    else: st.user_add(name, hash_pw(clave), "admin")
    print(f"Listo: contraseña de '{name}' actualizada (o creada como administrador).")
    return 0


def cmd_backup(settings, destino):
    from .backup import save
    destino = destino or os.path.join(settings.data_dir, "respaldo-" + time.strftime("%Y%m%d-%H%M") + ".json")
    n = save(_open_migrated(settings), destino)
    print(f"✔ Respaldo escrito en {destino} ({n} órdenes, con configuración y usuarios).\n"
          f"ℹ Las fotos y firmas están en {settings.media_dir}: copiá esa carpeta aparte para un respaldo completo.")
    return 0


def cmd_restore(settings, origen):
    from .backup import load
    try: n = load(_open_migrated(settings), origen)
    except (OSError, ValueError) as e: print(f"✖ No se pudo restaurar: {e}"); return 1
    print(f"✔ Restaurado: {n} órdenes (no se borró nada de lo que ya estaba en la base).\nℹ Reiniciá el CRM para que los cambios se vean en pantalla.")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="python -m crm", description="CRM técnico. Sin subcomando arranca el servidor.")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="arranca el servidor (por defecto)"); s.add_argument("--lan", action="store_true", help="aceptar conexiones de la red local")
    sub.add_parser("check-db", help="prueba conexión, migraciones y escritura (se deshace)")
    sub.add_parser("list-users", help="lista los usuarios")
    r = sub.add_parser("reset-password", help="cambia la contraseña de un usuario (o lo crea como administrador)")
    r.add_argument("usuario"); r.add_argument("clave")
    m = sub.add_parser("migrate-sqlite", help="pasa un crm.db viejo a la base de DATABASE_URL (una sola vez)"); m.add_argument("origen")
    b = sub.add_parser("backup", help="guarda un respaldo de la base en un archivo JSON"); b.add_argument("destino", nargs="?", help="archivo de salida (por defecto: data/respaldo-FECHA.json)")
    rs = sub.add_parser("restore", help="restaura un respaldo hecho con 'backup' (no borra nada)"); rs.add_argument("origen")
    sub.add_parser("version", help="muestra la versión")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")): argv.insert(0, "serve")
    args = build_parser().parse_args(argv)
    if args.cmd == "version": print(__version__); return 0
    settings = Settings.from_env()
    if settings.require_postgres and not settings.es_postgres:
        print(f"✖ Este despliegue exige PostgreSQL (REQUIRE_POSTGRES=1) pero DATABASE_URL vale: '{redact(settings.database_url)}'.\n"
              "  Revisá que tu .env tenga DATABASE_URL=postgresql://... y que docker-compose.yml lo pase en 'environment'.")
        return 1
    if args.cmd == "check-db": return cmd_check_db(settings)
    if args.cmd == "list-users": return cmd_list_users(settings)
    if args.cmd == "reset-password": return cmd_reset_password(settings, args.usuario, args.clave)
    if args.cmd == "backup": return cmd_backup(settings, args.destino)
    if args.cmd == "restore": return cmd_restore(settings, args.origen)
    if args.cmd == "migrate-sqlite":
        from .migrate import run
        return run(settings, args.origen)
    from .api import serve
    from .log import log
    if not settings.es_postgres: log("⚠ ATENCIÓN: se está usando SQLite (DATABASE_URL vacío o sqlite://). Si querías PostgreSQL, revisá el .env y el docker-compose.yml.")
    serve(App(settings), lan=getattr(args, "lan", False))
    return 0
