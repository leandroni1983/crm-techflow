"""Tareas de arranque: primer administrador, migración de fotos viejas y bajada de privilegios en Docker."""
import json, os, secrets

from .log import log
from .security import hash_pw

# Claves de ejemplo que no deberían quedar en producción (ADMIN_PASSWORD se usa solo al crear el primer usuario).
CLAVES_DEBILES = {"cambiame-por-algo-largo", "cambiame", "admin", "admin123", "12345678", "password", "crm", "crmtecnico", "test"}


def ensure_admin(app):
    """Si todavía no hay usuarios crea el administrador (con ADMIN_USER/ADMIN_PASSWORD, o con una clave generada)."""
    svc, st = app.service, app.settings
    if svc.users_count(): return
    pw = st.admin_password or secrets.token_urlsafe(9)
    svc.user_add(st.admin_user, hash_pw(pw), "admin")
    if st.admin_password:
        log(f"Usuario administrador creado: {st.admin_user} (contraseña tomada de ADMIN_PASSWORD)")
        if st.admin_password.strip().lower() in CLAVES_DEBILES or len(st.admin_password.strip()) < 12:
            log("ATENCIÓN: ADMIN_PASSWORD es corta o es una clave de ejemplo. Cambiala ya desde ⚙️ > Mi cuenta: "
                "mientras siga así, quien llegue a la pantalla de ingreso puede probarla sin límite.")
    else: print("=" * 60 + f"\n  PRIMER INGRESO  ->  usuario: {st.admin_user}   contraseña: {pw}\n  (guardala y cambiala desde ⚙️ > Mi cuenta)\n" + "=" * 60, flush=True)


def migrate_legacy_media(app):
    """Pasa a archivos las fotos/firmas que versiones viejas guardaban dentro de la base."""
    n = 0
    for r in app.store.media_pending():
        try: imgs = json.loads(r["imagenes"] or "[]")
        except Exception: imgs = []
        m = app.media
        app.store.media_set(r["id"], [u for u in (m.save(r["id"], x) for x in imgs) if u], m.save(r["id"], r["firma"] or ""), m.save(r["id"], r["firma_entrega"] or "")); n += 1
    if n: log(f"Migración: {n} órdenes con fotos/firmas pasadas a archivos en {app.settings.media_dir}")


def drop_privileges(settings):
    """Dentro de Docker arranca como root solo para ajustar permisos de /data y luego baja a PUID/PGID."""
    if os.name != "posix" or not settings.drop_privileges or os.getuid() != 0: return
    for root, dirs, files in os.walk(settings.data_dir):
        for n in [root] + [os.path.join(root, x) for x in dirs + files]:
            try: os.chown(n, settings.puid, settings.pgid)
            except OSError: pass
    os.setgroups([]); os.setgid(settings.pgid); os.setuid(settings.puid)
