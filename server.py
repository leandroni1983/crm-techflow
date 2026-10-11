#!/usr/bin/env python3
"""Servidor del CRM técnico.

Uso:
    python server.py                    -> http://localhost:8000   (por defecto guarda en SQLite: DATA_DIR/crm.db)
    python server.py --lan              -> accesible desde otros equipos de la red
    python server.py --check-db         -> prueba conexión, migraciones y escritura (se deshace) y sale
    python server.py --list-users
    python server.py --reset-password USUARIO NUEVA_CONTRASEÑA

Variables de entorno: DATABASE_URL, DATA_DIR, HOST, PORT, ADMIN_USER, ADMIN_PASSWORD, COOKIE_SECURE, TRUST_PROXY,
                      PUID/PGID, SYNC_SECS
"""
import hashlib, hmac, json, os, re, secrets, shutil, socket, sys, time, traceback, webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from media import DATA_DIR, MEDIA, MEDIA_RE, _safe, save_media, clean_media
from pdfqr import qr_matrix, pdf_comprobante
from store import DBUnavailable, open_store, norm_order, redact
from backend import Backend, NeedsDB, NoSeq, log

DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///" + os.path.join(DATA_DIR, "crm.db")
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE") == "1"
TRUST_PROXY = os.environ.get("TRUST_PROXY") == "1"
SESSION_DAYS = 7
MAX_BODY = 80 * 1024 * 1024
PUBLIC = {"/styles.css": "text/css; charset=utf-8", "/login.js": "application/javascript; charset=utf-8",
          "/manifest.webmanifest": "application/manifest+json", "/sw.js": "application/javascript; charset=utf-8",
          "/icon-192.png": "image/png", "/icon-512.png": "image/png", "/apple-touch-icon.png": "image/png", "/favicon.png": "image/png"}
PROTECTED = {"/app.js": "application/javascript; charset=utf-8", "/db.js": "application/javascript; charset=utf-8"}
NAME_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")
LOGIN_FAILS = {}  # ip -> [fallos, bloqueado_hasta]
BE = None         # Backend (se crea al arrancar)


# ------------------------------------------------------------------ usuarios y sesiones
def hash_pw(p, salt=None, it=200_000):
    salt = salt or secrets.token_hex(16)
    return f"pbkdf2${it}${salt}${hashlib.pbkdf2_hmac('sha256', p.encode(), bytes.fromhex(salt), it).hex()}"


def check_pw(p, stored):
    try:
        _, it, salt, h = stored.split("$")
        return hmac.compare_digest(hash_pw(p, salt, int(it)).split("$")[3], h)
    except Exception:
        return False


def _th(token): return hashlib.sha256(token.encode()).hexdigest()


def ensure_admin():
    if BE.users_count(): return
    u = os.environ.get("ADMIN_USER", "admin").strip().lower() or "admin"
    env_pw = os.environ.get("ADMIN_PASSWORD"); p = env_pw or secrets.token_urlsafe(9)
    BE.user_add(u, hash_pw(p), "admin")
    if env_pw: log(f"Usuario administrador creado: {u} (contraseña tomada de ADMIN_PASSWORD)")
    else: print("=" * 60 + f"\n  PRIMER INGRESO  ->  usuario: {u}   contraseña: {p}\n  (guardala y cambiala desde ⚙️ > Mi cuenta)\n" + "=" * 60, flush=True)


def migrate_legacy_media(store):
    """Pasa a archivos las fotos/firmas que versiones viejas guardaban dentro de la base."""
    n = 0
    for r in store.media_pending():
        try: imgs = json.loads(r["imagenes"] or "[]")
        except Exception: imgs = []
        store.media_set(r["id"], [u for u in (save_media(r["id"], x) for x in imgs) if u], save_media(r["id"], r["firma"] or ""), save_media(r["id"], r["firma_entrega"] or "")); n += 1
    if n: log(f"Migración: {n} órdenes con fotos/firmas pasadas a archivos en {MEDIA}")


def drop_privileges():
    """Dentro de Docker arranca como root solo para ajustar permisos de /data y luego baja a PUID/PGID."""
    if os.name != "posix" or os.environ.get("DROP_PRIVILEGES") != "1" or os.getuid() != 0: return
    uid = int(os.environ.get("PUID", "10001")); gid = int(os.environ.get("PGID", str(uid)))
    for root, dirs, files in os.walk(DATA_DIR):
        for n in [root] + [os.path.join(root, x) for x in dirs + files]:
            try: os.chown(n, uid, gid)
            except OSError: pass
    os.setgroups([]); os.setgid(gid); os.setuid(uid)


# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", headers=None):
        if not isinstance(body, bytes): body = json.dumps(body).encode()
        self.send_response(code)
        h = {"Content-Type": ctype, "Content-Length": str(len(body)), "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
             "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin"}
        h.update(headers or {})
        for k, v in h.items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to):
        self.send_response(302); self.send_header("Location", to); self.send_header("Content-Length", "0"); self.end_headers()

    def _file(self, name, ctype):
        with open(os.path.join(DIR, name), "rb") as f: return self._send(200, f.read(), ctype)

    def _json(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > MAX_BODY: raise ValueError("body too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def _token(self):
        m = SimpleCookie(self.headers.get("Cookie", "")).get("crm_sid")
        return m.value if m else ""

    def _user(self):
        t = self._token()
        return BE.session_user(_th(t), SESSION_DAYS) if t else None

    def _ip(self):
        if TRUST_PROXY:  # Cloudflare pisa CF-Connecting-IP con la IP real; X-Forwarded-For sí es falseable
            ip = self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            if ip: return ip
        return self.client_address[0]

    def _https(self):
        return (self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower() == "https"
                or "https" in self.headers.get("CF-Visitor", "").lower())

    def _cookie(self, token, max_age):
        sec = "; Secure" if (COOKIE_SECURE and self._https()) else ""
        return {"Set-Cookie": f"crm_sid={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}" + sec}

    def log_message(self, *a): pass

    def _guard(self, fn):
        try: fn()
        except NeedsDB: self._send(503, {"error": "Esta acción necesita conexión con la base de datos y ahora no hay."})
        except NoSeq: self._send(409, {"error": "Sin conexión y sin números de orden reservados: las órdenes nuevas esperan a que vuelva la conexión (podés seguir editando las existentes)."})
        except DBUnavailable: self._send(503, {"error": "No hay conexión con la base de datos."})
        except ValueError as e: self._send(400, {"error": str(e)})
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception:
            log("Error interno:\n" + traceback.format_exc())
            try: self._send(500, {"error": "Error interno del servidor"})
            except Exception: pass

    def do_GET(self): self._guard(self._get)
    def do_POST(self): self._guard(self._post)
    def do_DELETE(self): self._guard(self._delete)

    # ---------------- GET
    def _get(self):
        u = urlparse(self.path); p = u.path
        if p == "/health":
            st = BE.status()
            if parse_qs(u.query).get("deep") and not st["online"]: return self._send(503, {"ok": False, **st})
            return self._send(200, {"ok": True, **st})
        if p in PUBLIC: return self._file(p[1:], PUBLIC[p])
        user = self._user()
        if p == "/login": return self._redirect("/") if user else self._file("login.html", "text/html; charset=utf-8")
        if p in ("/", "/index.html"):
            return self._file("crm-tecnico.html", "text/html; charset=utf-8") if user else self._redirect("/login")
        if p.startswith("/media/"):
            m = MEDIA_RE.match(p); fp = os.path.join(MEDIA, m.group(1), m.group(2)) if m else ""
            if not user: return self._send(401, {"error": "login"})
            if not m or not os.path.isfile(fp): return self._send(404, {"error": "not found"})
            with open(fp, "rb") as f: return self._send(200, f.read(), "image/jpeg", {"Cache-Control": "private, max-age=31536000, immutable"})
        if p in PROTECTED: return self._file(p[1:], PROTECTED[p]) if user else self._send(401, {"error": "login"})
        if not p.startswith("/api/"): return self._send(404, {"error": "not found"})
        if not user: return self._send(401, {"error": "login"})
        if p == "/api/data":
            cfg = BE.config(); cfg.pop("pin", None)
            return self._send(200, {"ordenes": BE.orders(), "config": cfg, "usuario": user, "tecnicos": BE.usernames(), "sync": BE.status()})
        if p == "/api/estado": return self._send(200, BE.status())
        if p == "/api/qr":
            try:
                rows = qr_matrix(parse_qs(u.query).get("t", [""])[0])
                return self._send(200, {"n": len(rows), "rows": rows})
            except Exception as e:
                return self._send(400, {"error": str(e)})
        if p == "/api/usuarios":
            if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
            return self._send(200, BE.users_list())
        self._send(404, {"error": "not found"})

    # ---------------- POST
    def _post(self):
        p = self.path
        try: d = self._json()
        except Exception: return self._send(400, {"error": "solicitud inválida"})
        if p == "/api/login":
            ip = self._ip(); f = LOGIN_FAILS.get(ip, [0, 0])
            if f[1] > time.time(): return self._send(429, {"error": "Demasiados intentos. Probá de nuevo en unos minutos."})
            name = str(d.get("usuario", "")).strip().lower(); r = BE.user_get(name)
            ok = check_pw(str(d.get("password", "")), r["hash"]) if r else False
            if not r: check_pw("x", hash_pw("y"))  # iguala los tiempos de respuesta
            if not ok:
                log(f"Login rechazado desde {ip}: " + (f"el usuario '{name}' no existe" if not r else f"contraseña incorrecta para '{name}'"))
                f[0] += 1
                if f[0] >= 5: f = [0, time.time() + 300]
                LOGIN_FAILS[ip] = f
                return self._send(401, {"error": "Usuario o contraseña incorrectos"})
            LOGIN_FAILS.pop(ip, None)
            token = secrets.token_urlsafe(32); BE.sess_add(_th(token), name, time.time() + SESSION_DAYS * 86400)
            return self._send(200, {"ok": True}, headers=self._cookie(token, SESSION_DAYS * 86400))
        if p == "/api/logout":
            t = self._token()
            if t: BE.sess_del(_th(t))
            return self._send(200, {"ok": True}, headers=self._cookie("", 0))
        user = self._user()
        if not user: return self._send(401, {"error": "login"})
        if p == "/api/orden":
            oid = str(d["id"]); d.pop("seq", None); d.pop("actualizada", None)
            imgs = [u for u in (save_media(oid, x) for x in (d.get("imagenes") or [])) if u]
            firma, firma_e = save_media(oid, d.get("firma", "")), save_media(oid, d.get("firma_entrega", ""))
            d["id"], d["imagenes"], d["firma"], d["firma_entrega"] = oid, imgs, firma, firma_e
            ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            # solo se agregan las entradas nuevas (marcadas n); fecha y usuario los pone el servidor, no se pueden falsear
            hist_new = [{"f": ahora, "t": str(h.get("t", ""))[:300], "u": user["nombre"]} for h in (d.get("historial") or []) if isinstance(h, dict) and h.get("n")]
            res = BE.order_save(norm_order(d), hist_new)
            clean_media(oid, imgs + [firma, firma_e])
            return self._send(200, {"seq": res["seq"], "imagenes": imgs, "firma": firma, "firma_entrega": firma_e, "historial": res["historial"]})
        if p == "/api/config":
            BE.config_set({k: str(v) for k, v in d.items() if k != "pin"})
            return self._send(200, {"ok": True})
        if p == "/api/comprobante":
            pdf = pdf_comprobante(d)
            carpeta = os.path.join(DATA_DIR, "comprobantes"); os.makedirs(carpeta, exist_ok=True)
            with open(os.path.join(carpeta, re.sub(r"[^\w-]", "", str(d.get("numero", "orden")) + str(d.get("sufijo", ""))) + ".pdf"), "wb") as f: f.write(pdf)
            return self._send(200, pdf, "application/pdf")
        if p == "/api/password":
            new = str(d.get("nueva", ""))
            if len(new) < 8: return self._send(400, {"error": "La contraseña nueva debe tener al menos 8 caracteres"})
            r = BE.user_get(user["nombre"])
            if not r or not check_pw(str(d.get("actual", "")), r["hash"]): return self._send(400, {"error": "La contraseña actual no es correcta"})
            BE.user_set_hash(user["nombre"], hash_pw(new)); BE.sess_del_others(user["nombre"], _th(self._token()))
            return self._send(200, {"ok": True})
        if p == "/api/usuarios":
            if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
            name = str(d.get("nombre", "")).strip().lower(); rol = d.get("rol") if d.get("rol") in ("admin", "tecnico") else "tecnico"
            if not NAME_RE.match(name): return self._send(400, {"error": "Usuario: 3 a 30 caracteres (letras, números, . _ -)"})
            if len(str(d.get("password", ""))) < 8: return self._send(400, {"error": "La contraseña debe tener al menos 8 caracteres"})
            BE.user_add(name, hash_pw(str(d["password"])), rol)
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})

    # ---------------- DELETE
    def _delete(self):
        user = self._user()
        if not user: return self._send(401, {"error": "login"})
        if self.path.startswith("/api/orden/"):
            oid = self.path.rsplit("/", 1)[1]
            BE.order_del(oid); shutil.rmtree(os.path.join(MEDIA, _safe(oid)), ignore_errors=True)
            return self._send(200, {"ok": True})
        if self.path.startswith("/api/usuarios/"):
            if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
            name = self.path.rsplit("/", 1)[1].lower()
            if name == user["nombre"]: return self._send(400, {"error": "No podés borrar tu propio usuario"})
            BE.user_del(name)
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})


# ------------------------------------------------------------------ comandos de línea
def cli():
    flags = ("--list-users", "--reset-password", "--check-db")
    if not any(a in sys.argv for a in flags): return False
    st = open_store(DATABASE_URL)
    try: st.migrate()
    except DBUnavailable as e:
        print(f"✖ No se pudo conectar con la base ({redact(DATABASE_URL)}): {e}"); sys.exit(1)
    if "--check-db" in sys.argv:
        i = st.info()
        print(f"✔ Motor: {st.nombre}   Base: {redact(DATABASE_URL)}\n✔ Esquema v{i['version']} (última del programa)\n✔ Órdenes: {i['ordenes']}   Usuarios: {i['usuarios']}   Último número de orden: {i['ultimo_numero']}\n✔ Escritura de prueba: {i['escritura']}")
        try:
            os.makedirs(MEDIA, exist_ok=True); t = os.path.join(DATA_DIR, ".check"); open(t, "w").close(); os.remove(t)
            print(f"✔ Carpeta de archivos escribible: {DATA_DIR}")
        except OSError as e: print(f"✖ No se puede escribir en {DATA_DIR}: {e}")
        if i["usuarios"] == 0: print("ℹ Todavía no hay usuarios: el primero se crea con ADMIN_USER / ADMIN_PASSWORD al arrancar.")
    elif "--list-users" in sys.argv:
        for r in st.users_full(): print(f"{r['nombre']}  ({r['rol']})")
    else:
        i = sys.argv.index("--reset-password")
        if len(sys.argv) < i + 3: print("Uso: python server.py --reset-password USUARIO NUEVA_CONTRASEÑA"); return True
        name, pw = sys.argv[i + 1].strip().lower(), sys.argv[i + 2]
        if len(pw) < 8: print("La contraseña debe tener al menos 8 caracteres"); return True
        if st.user_get(name): st.user_set_hash(name, hash_pw(pw))
        else: st.user_add(name, hash_pw(pw), "admin")
        print(f"Listo: contraseña de '{name}' actualizada (o creada como administrador).")
    return True


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "IP-de-tu-PC"


if __name__ == "__main__":
    if cli(): sys.exit(0)
    store = open_store(DATABASE_URL)
    BE = Backend(store, DATA_DIR, DATABASE_URL, probe_secs=int(os.environ.get("SYNC_SECS", "10")))
    BE.start(); ensure_admin(); migrate_legacy_media(store); drop_privileges(); BE.start_thread()
    host = "0.0.0.0" if "--lan" in sys.argv else HOST
    log(f"CRM en http://localhost:{PORT}  |  archivos: {DATA_DIR}")
    if host == "0.0.0.0" and not os.environ.get("DROP_PRIVILEGES"): log(f"Acceso desde la red: http://{lan_ip()}:{PORT}")
    if host == "127.0.0.1":
        try: webbrowser.open(f"http://localhost:{PORT}")
        except Exception: pass
    ThreadingHTTPServer((host, PORT), H).serve_forever()
