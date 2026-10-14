"""Motores de base de datos: SQLite (pruebas/desarrollo) y PostgreSQL (producción), con el mismo SQL.
DATABASE_URL elige el motor:
    postgresql://usuario:clave@host:5432/base?sslmode=require
    sqlite:////ruta/absoluta/crm.db
"""
import json, os, queue, sqlite3, time
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

from .migrations import LATEST, MIGRATIONS
from .models import JSON_COLS, ORDER_COLS, TEXT_COLS, now_iso, now_ms, row_to_order


class DBUnavailable(Exception):
    """No hay conexión con la base (red caída, base apagada, timeout)."""


class _Rollback(Exception):
    pass


def redact(url):
    """Oculta la contraseña de la URL para mostrarla en logs."""
    try:
        u = urlsplit(url)
        if u.password: return urlunsplit(u._replace(netloc=f"{u.username}:***@{u.hostname}" + (f":{u.port}" if u.port else "")))
    except Exception: pass
    return url


# ------------------------------------------------------------------ transacción
class _Tx:
    def __init__(self, conn, pg): self.c, self.pg = conn, pg

    def _sql(self, s, has_params):
        if not self.pg: return s
        return s.replace("%", "%%").replace("?", "%s") if has_params else s

    def run(self, sql, p=()):
        p = tuple(p)
        return self.c.execute(self._sql(sql, bool(p)), p if p else None) if self.pg else self.c.execute(sql, p)

    def all(self, sql, p=()):
        return [dict(r) for r in self.run(sql, p).fetchall()]

    def one(self, sql, p=()):
        rows = self.all(sql, p)
        return rows[0] if rows else None


# ------------------------------------------------------------------ almacenes
class Store:
    pg = False
    nombre = ""

    # ---- infraestructura
    def ping(self):
        with self.tx() as t: t.one("SELECT 1 AS x")

    def migrate(self):
        with self.tx() as t:
            if self.pg: t.run("SELECT pg_advisory_xact_lock(727274)")  # una sola instancia migra a la vez
            t.run("CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY, aplicada TEXT, descripcion TEXT)")
            cur = (t.one("SELECT MAX(version) AS v FROM schema_version") or {}).get("v") or 0
            if cur > LATEST:
                raise RuntimeError(f"La base está en la versión {cur} del esquema y este programa solo conoce hasta la {LATEST}. "
                                   "Actualizá el CRM antes de arrancar (así no se daña la base).")
            for v, desc, fn in MIGRATIONS:
                if v > cur:
                    fn(t); t.run("INSERT INTO schema_version(version, aplicada, descripcion) VALUES(?,?,?)", (v, now_iso(), desc))
                    print(f"Migración {v} aplicada: {desc}", flush=True)
        return LATEST

    def info(self):
        """Datos para --check-db y /health. La prueba de escritura se deshace."""
        with self.tx() as t:
            r = {"version": t.one("SELECT MAX(version) AS v FROM schema_version")["v"], "ordenes": t.one("SELECT COUNT(*) AS n FROM ordenes")["n"],
                 "usuarios": t.one("SELECT COUNT(*) AS n FROM usuarios")["n"]}
            r["ultimo_numero"] = t.one("SELECT last_value AS v FROM orden_seq")["v"] if self.pg else t.one("SELECT valor AS v FROM contadores WHERE nombre='orden'")["v"]
        try:
            with self.tx() as t:
                t.run("INSERT INTO config(k,v) VALUES('__check__','1') ON CONFLICT(k) DO UPDATE SET v=excluded.v")
                assert t.one("SELECT v FROM config WHERE k='__check__'")["v"] == "1"
                raise _Rollback()
        except _Rollback:
            r["escritura"] = "ok (deshecha)"
        return r

    # ---- usuarios
    def users_full(self):
        with self.tx() as t: return t.all("SELECT nombre, hash, rol, creado FROM usuarios ORDER BY nombre")

    def user_get(self, nombre):
        with self.tx() as t: return t.one("SELECT nombre, hash, rol, creado FROM usuarios WHERE nombre=?", (nombre,))

    def users_count(self):
        with self.tx() as t: return t.one("SELECT COUNT(*) AS n FROM usuarios")["n"]

    def user_add(self, nombre, hash_, rol):
        with self.tx() as t:
            if t.one("SELECT 1 AS x FROM usuarios WHERE nombre=?", (nombre,)): raise ValueError("Ese usuario ya existe")
            t.run("INSERT INTO usuarios(nombre, hash, rol, creado) VALUES(?,?,?,?)", (nombre, hash_, rol, now_iso()))

    def user_set_hash(self, nombre, hash_):
        with self.tx() as t: t.run("UPDATE usuarios SET hash=? WHERE nombre=?", (hash_, nombre))

    def user_del(self, nombre):
        with self.tx() as t:
            t.run("DELETE FROM usuarios WHERE nombre=?", (nombre,)); t.run("DELETE FROM sesiones WHERE usuario=?", (nombre,))

    # ---- sesiones
    def sess_add(self, th, usuario, expira):
        with self.tx() as t:
            t.run("DELETE FROM sesiones WHERE expira < ?", (time.time(),))
            t.run("INSERT INTO sesiones(token, usuario, expira) VALUES(?,?,?) ON CONFLICT(token) DO NOTHING", (th, usuario, expira))

    def sess_get(self, th):
        with self.tx() as t:
            return t.one("SELECT s.expira AS expira, u.nombre AS nombre, u.rol AS rol FROM sesiones s JOIN usuarios u ON u.nombre=s.usuario WHERE s.token=?", (th,))

    def sess_touch(self, th, expira):
        with self.tx() as t: t.run("UPDATE sesiones SET expira=? WHERE token=?", (expira, th))

    def sess_del(self, th):
        with self.tx() as t: t.run("DELETE FROM sesiones WHERE token=?", (th,))

    def sess_del_others(self, usuario, keep_th):
        with self.tx() as t: t.run("DELETE FROM sesiones WHERE usuario=? AND token<>?", (usuario, keep_th))

    # ---- configuración
    def config_all(self):
        with self.tx() as t: return {r["k"]: r["v"] for r in t.all("SELECT k, v FROM config")}

    def config_set(self, d):
        with self.tx() as t:
            for k, v in d.items():
                t.run("INSERT INTO config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))

    # ---- órdenes
    def orders_all(self):
        with self.tx() as t: return [row_to_order(r) for r in t.all("SELECT * FROM ordenes ORDER BY seq DESC")]

    def _nextval(self, t):
        if self.pg: return t.one("SELECT nextval('orden_seq') AS v")["v"]
        t.run("UPDATE contadores SET valor = valor + 1 WHERE nombre='orden'")
        return t.one("SELECT valor AS v FROM contadores WHERE nombre='orden'")["v"]

    def next_seq(self, n=1):
        with self.tx() as t: return [self._nextval(t) for _ in range(n)]

    def _upsert(self, t, o, seq, hist, mod):
        names = ORDER_COLS
        vals = [o["id"], seq] + [("" if o.get(k) is None else str(o.get(k))) for k in TEXT_COLS] \
            + [json.dumps(hist if k == "historial" else (o.get(k) or [])) for k in JSON_COLS] + [o.get("creada"), mod]
        upd = ", ".join(f"{k}=excluded.{k}" for k in TEXT_COLS + JSON_COLS + ["actualizada"])
        t.run(f"INSERT INTO ordenes({','.join(names)}) VALUES({','.join('?' * len(names))}) ON CONFLICT(id) DO UPDATE SET {upd}", vals)

    def order_save(self, o, hist_new, seq=None, base_mod=None):
        """Guarda una orden. El historial existente se conserva y solo se agregan las entradas nuevas (sin duplicar)."""
        with self.tx() as t:
            ex = t.one("SELECT seq, historial, actualizada FROM ordenes WHERE id=?", (o["id"],))
            n = ex["seq"] if ex else (seq or self._nextval(t))
            try: hist = json.loads(ex["historial"] or "[]") if ex else []
            except Exception: hist = []
            seen = {(h.get("f"), h.get("t"), h.get("u")) for h in hist}
            hist += [h for h in hist_new if (h.get("f"), h.get("t"), h.get("u")) not in seen]
            if ex and base_mod is not None and (ex["actualizada"] or "") != base_mod:
                hist.append({"f": now_iso(), "t": "Sincronización: se pisó un cambio hecho en la base mientras se trabajaba sin conexión", "u": "sistema"})
            mod = now_ms()
            self._upsert(t, o, n, hist, mod)
        return {"seq": n, "historial": hist, "actualizada": mod}

    def order_del(self, oid):
        with self.tx() as t: t.run("DELETE FROM ordenes WHERE id=?", (oid,))

    def categoria_renombrar(self, clave, col, de, a, lista):
        """Renombra una categoría (tipo de falla o de equipo) en TODAS las órdenes y guarda la lista nueva de
        configuración, todo en la misma transacción. Devuelve cuántas órdenes cambiaron.
        `col` se valida contra una lista fija: el nombre de la columna nunca viene del cliente."""
        if col not in ("falla_tipo", "equipo_tipo"): raise ValueError("columna no permitida")
        with self.tx() as t:
            n = t.run(f"UPDATE ordenes SET {col}=?, actualizada=? WHERE {col}=?", (a, now_ms(), de)).rowcount
            t.run("INSERT INTO config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (clave, str(lista)))
        return n

    def media_pending(self):
        """Órdenes de versiones viejas con fotos/firmas dentro de la base (dataURL)."""
        with self.tx() as t:
            return t.all("SELECT id, imagenes, firma, firma_entrega FROM ordenes WHERE imagenes LIKE '%data:%' OR firma LIKE 'data:%' OR firma_entrega LIKE 'data:%'")

    def media_set(self, oid, imgs, firma, firma_e):
        with self.tx() as t: t.run("UPDATE ordenes SET imagenes=?, firma=?, firma_entrega=? WHERE id=?", (json.dumps(imgs), firma, firma_e, oid))

    def bulk_load(self, users, cfg, orders):
        """Carga de una sola vez (script de migración). Todo o nada."""
        with self.tx() as t:
            for u in users:
                t.run("INSERT INTO usuarios(nombre, hash, rol, creado) VALUES(?,?,?,?) ON CONFLICT(nombre) DO NOTHING", (u["nombre"], u["hash"], u["rol"], u.get("creado")))
            for k, v in cfg.items():
                t.run("INSERT INTO config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))
            for o in orders: self._upsert(t, o, o["seq"], o["historial"], o.get("actualizada") or now_ms())
            mx = max([o["seq"] for o in orders] + [0])
            if self.pg: t.run("SELECT setval('orden_seq', ?, ?)", (max(mx, 1), mx > 0))
            else: t.run("UPDATE contadores SET valor=? WHERE nombre='orden'", (mx,))


class SqliteStore(Store):
    nombre = "SQLite"

    def __init__(self, path, offline_flag=None):
        """offline_flag: ruta de un archivo; si existe, simula que la base cayó (solo para pruebas)."""
        self.path, self.offline_flag = path, offline_flag
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    @contextmanager
    def tx(self):
        if self.offline_flag and os.path.exists(self.offline_flag): raise DBUnavailable("conexión simulada caída")
        c = sqlite3.connect(self.path, timeout=30); c.row_factory = sqlite3.Row
        try:
            yield _Tx(c, False); c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()


class PgStore(Store):
    pg = True
    nombre = "PostgreSQL"

    def __init__(self, url):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError:
            raise SystemExit("✖ Falta el driver de PostgreSQL (psycopg). Sin Docker: pip install -r requirements.txt. "
                             "Con Docker se instala al construir la imagen: reconstruila con `docker compose build --no-cache`.")
        self.psycopg, self.dict_row, self.url = psycopg, dict_row, url
        self.idle = queue.LifoQueue()
        self.errs = (psycopg.OperationalError, psycopg.InterfaceError)

    def _connect(self):
        try: return self.psycopg.connect(self.url, row_factory=self.dict_row, connect_timeout=5)
        except self.errs as e: raise DBUnavailable(str(e).strip().splitlines()[0] if str(e).strip() else "no se pudo conectar") from e

    def _get(self):
        while True:
            try: ts, c = self.idle.get_nowait()
            except queue.Empty: return self._connect()
            if c.closed: continue
            if time.time() - ts > 20:  # conexión ociosa: se verifica antes de usarla (la nube suele cortarlas)
                try: c.execute("SELECT 1"); c.rollback()
                except Exception:
                    try: c.close()
                    except Exception: pass
                    continue
            return c

    def _put(self, c):
        if c.closed: return
        if self.idle.qsize() < 5: self.idle.put((time.time(), c))
        else: c.close()

    @contextmanager
    def tx(self):
        c = self._get()
        try:
            yield _Tx(c, True); c.commit()
        except Exception as e:
            try: c.rollback()
            except Exception: pass
            if isinstance(e, self.errs):
                try: c.close()
                except Exception: pass
                raise DBUnavailable(str(e).strip().splitlines()[0] if str(e).strip() else "conexión perdida") from e
            raise
        finally:
            self._put(c)


def open_store(url, offline_flag=None):
    if url.startswith("sqlite:///"): return SqliteStore(url[len("sqlite:///"):], offline_flag or os.environ.get("CRM_SIM_OFFLINE_FILE"))
    if url.startswith(("postgresql://", "postgres://")): return PgStore(url)
    raise ValueError("DATABASE_URL debe empezar con postgresql:// (o sqlite:/// para pruebas)")
