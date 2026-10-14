"""Capa HTTP: recibe el pedido, valida la sesión y delega en los servicios. No tiene lógica de negocio."""
import json, os, re, secrets, time, traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from .. import __version__
from ..db import DBUnavailable
from ..log import log
from ..orders import delete_order, save_order
from ..pdf import pdf_comprobante
from ..qr import qr_matrix
from ..security import check_pw, hash_pw, token_hash
from ..service import NeedsDB, NoSeq

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
STATIC = os.path.realpath(os.path.join(WEB, "static"))
PROTECTED_STATIC = {"js/app.js", "js/db.js"}  # el resto de /static es público (lo necesita la pantalla de login)
ADMIN_CONFIG_KEYS = {"fallas"}  # claves de configuración que solo puede cambiar el administrador
TYPES = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".png": "image/png",
         ".html": "text/html; charset=utf-8", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml"}
NAME_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")


def make_handler(app):
    st, svc, media, limiter = app.settings, app.service, app.media, app.limiter

    class Handler(BaseHTTPRequestHandler):
        # ---------------- utilidades de respuesta
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

        def _file(self, path):
            with open(path, "rb") as f: return self._send(200, f.read(), TYPES.get(os.path.splitext(path)[1], "application/octet-stream"))

        def _json(self):
            n = int(self.headers.get("Content-Length", 0))
            if n > st.max_body: raise ValueError("body too large")
            return json.loads(self.rfile.read(n) or b"{}")

        # ---------------- sesión
        def _token(self):
            m = SimpleCookie(self.headers.get("Cookie", "")).get("crm_sid")
            return m.value if m else ""

        def _user(self):
            t = self._token()
            return svc.session_user(token_hash(t), st.session_days) if t else None

        def _ip(self):
            if st.trust_proxy:  # Cloudflare pisa CF-Connecting-IP con la IP real; X-Forwarded-For sí es falseable
                ip = self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
                if ip: return ip
            return self.client_address[0]

        def _https(self):
            return (self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower() == "https"
                    or "https" in self.headers.get("CF-Visitor", "").lower())

        def _cookie(self, token, max_age):
            sec = "; Secure" if (st.cookie_secure and self._https()) else ""
            return {"Set-Cookie": f"crm_sid={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}" + sec}

        def log_message(self, *a): pass

        # ---------------- despacho y manejo de errores
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

        # ---------------- archivos estáticos
        def _static(self, rel, user):
            parts = [p for p in rel.split("/") if p]
            if not parts or any(p in (".", "..") or "\\" in p or "\x00" in p for p in parts): return self._send(404, {"error": "not found"})
            full = os.path.realpath(os.path.join(STATIC, *parts))
            if not full.startswith(STATIC + os.sep) or not os.path.isfile(full): return self._send(404, {"error": "not found"})
            if "/".join(parts) in PROTECTED_STATIC and not user: return self._send(401, {"error": "login"})
            return self._file(full)

        # ---------------- GET
        def _get(self):
            u = urlparse(self.path); p = u.path
            if p == "/health":
                s = svc.status()
                if parse_qs(u.query).get("deep") and not s["online"]: return self._send(503, {"ok": False, "version": __version__, **s})
                return self._send(200, {"ok": True, "version": __version__, **s})
            if p in ("/sw.js", "/manifest.webmanifest"): return self._file(os.path.join(WEB, p[1:]))
            user = self._user()
            if p.startswith("/static/"): return self._static(p[len("/static/"):], user)
            if p == "/login":
                return self._redirect("/") if user else self._file(os.path.join(WEB, "templates", "login.html"))
            if p in ("/", "/index.html"):
                return self._file(os.path.join(WEB, "templates", "index.html")) if user else self._redirect("/login")
            if p.startswith("/media/"):
                if not user: return self._send(401, {"error": "login"})
                data = media.read(p)
                if data is None: return self._send(404, {"error": "not found"})
                return self._send(200, data, "image/jpeg", {"Cache-Control": "private, max-age=31536000, immutable"})
            if not p.startswith("/api/"): return self._send(404, {"error": "not found"})
            if not user: return self._send(401, {"error": "login"})
            if p == "/api/data":
                cfg = svc.config(); cfg.pop("pin", None)
                return self._send(200, {"ordenes": svc.orders(), "config": cfg, "usuario": user, "tecnicos": svc.usernames(), "sync": svc.status()})
            if p == "/api/estado": return self._send(200, svc.status())
            if p == "/api/qr":
                try:
                    rows = qr_matrix(parse_qs(u.query).get("t", [""])[0])
                    return self._send(200, {"n": len(rows), "rows": rows})
                except Exception as e:
                    return self._send(400, {"error": str(e)})
            if p == "/api/usuarios":
                if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
                return self._send(200, svc.users_list())
            self._send(404, {"error": "not found"})

        # ---------------- POST
        def _post(self):
            p = self.path
            try: d = self._json()
            except Exception: return self._send(400, {"error": "solicitud inválida"})
            if p == "/api/login": return self._login(d)
            if p == "/api/logout":
                t = self._token()
                if t: svc.sess_del(token_hash(t))
                return self._send(200, {"ok": True}, headers=self._cookie("", 0))
            user = self._user()
            if not user: return self._send(401, {"error": "login"})
            if p == "/api/orden": return self._send(200, save_order(app, user, d))
            if p == "/api/config":
                if user["rol"] != "admin" and any(k in ADMIN_CONFIG_KEYS for k in d):
                    return self._send(403, {"error": "Solo el administrador puede editar esa configuración"})
                svc.config_set({k: str(v) for k, v in d.items() if k != "pin"})
                return self._send(200, {"ok": True})
            if p == "/api/comprobante":
                pdf = pdf_comprobante(d, media)
                os.makedirs(st.comprobantes_dir, exist_ok=True)
                name = re.sub(r"[^\w-]", "", str(d.get("numero", "orden")) + str(d.get("sufijo", ""))) + ".pdf"
                with open(os.path.join(st.comprobantes_dir, name), "wb") as f: f.write(pdf)
                return self._send(200, pdf, "application/pdf")
            if p == "/api/password":
                new = str(d.get("nueva", ""))
                if len(new) < 8: return self._send(400, {"error": "La contraseña nueva debe tener al menos 8 caracteres"})
                r = svc.user_get(user["nombre"])
                if not r or not check_pw(str(d.get("actual", "")), r["hash"]): return self._send(400, {"error": "La contraseña actual no es correcta"})
                svc.user_set_hash(user["nombre"], hash_pw(new)); svc.sess_del_others(user["nombre"], token_hash(self._token()))
                return self._send(200, {"ok": True})
            if p == "/api/usuarios":
                if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
                name = str(d.get("nombre", "")).strip().lower(); rol = d.get("rol") if d.get("rol") in ("admin", "tecnico") else "tecnico"
                if not NAME_RE.match(name): return self._send(400, {"error": "Usuario: 3 a 30 caracteres (letras, números, . _ -)"})
                if len(str(d.get("password", ""))) < 8: return self._send(400, {"error": "La contraseña debe tener al menos 8 caracteres"})
                svc.user_add(name, hash_pw(str(d["password"])), rol)
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

        def _login(self, d):
            ip = self._ip()
            if limiter.blocked(ip): return self._send(429, {"error": "Demasiados intentos. Probá de nuevo en unos minutos."})
            name = str(d.get("usuario", "")).strip().lower(); r = svc.user_get(name)
            ok = check_pw(str(d.get("password", "")), r["hash"]) if r else False
            if not r: check_pw("x", hash_pw("y"))  # iguala los tiempos de respuesta
            if not ok:
                log(f"Login rechazado desde {ip}: " + (f"el usuario '{name}' no existe" if not r else f"contraseña incorrecta para '{name}'"))
                limiter.fail(ip)
                return self._send(401, {"error": "Usuario o contraseña incorrectos"})
            limiter.ok(ip)
            token = secrets.token_urlsafe(32); svc.sess_add(token_hash(token), name, time.time() + st.session_days * 86400)
            return self._send(200, {"ok": True}, headers=self._cookie(token, st.session_days * 86400))

        # ---------------- DELETE
        def _delete(self):
            user = self._user()
            if not user: return self._send(401, {"error": "login"})
            if self.path.startswith("/api/orden/"):
                delete_order(app, self.path.rsplit("/", 1)[1])
                return self._send(200, {"ok": True})
            if self.path.startswith("/api/usuarios/"):
                if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
                name = self.path.rsplit("/", 1)[1].lower()
                if name == user["nombre"]: return self._send(400, {"error": "No podés borrar tu propio usuario"})
                svc.user_del(name)
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

    return Handler
