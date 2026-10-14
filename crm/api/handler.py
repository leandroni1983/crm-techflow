"""Capa HTTP: recibe el pedido, valida la sesión y delega en los servicios. No tiene lógica de negocio."""
import json, os, re, secrets, time, traceback
from hashlib import md5
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from .. import __version__, seg
from ..backup import dump as backup_dump
from ..db import DBUnavailable
from ..log import log
from ..orders import delete_order, save_order
from ..pdf import pdf_comprobante
from ..qr import qr_matrix
from ..resumen import datos as resumen_datos
from ..security import check_pw, hash_pw, token_hash
from ..service import NeedsDB, NoSeq

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
STATIC = os.path.realpath(os.path.join(WEB, "static"))
PROTECTED_STATIC = {f"js/{n}.js" for n in ("app", "db", "util", "comun", "cat", "orden", "lista", "config", "panel", "modo")}  # el resto de /static es público (lo necesita la pantalla de login)
ADMIN_CONFIG_KEYS = {"fallas", "equipos", "repuestos", "seg_clave"}  # claves de configuración que solo puede cambiar el administrador
TYPES = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".png": "image/png",
         ".html": "text/html; charset=utf-8", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml"}
NAME_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")

# Cabeceras de seguridad: van en TODAS las respuestas.
# El CSP es estricto porque la app no usa nada externo (ni CDN ni fuentes remotas) y todo el JS va en archivos propios.
# 'unsafe-inline' solo para estilos: las hojas de impresión se arman en el momento y las plantillas usan style="...".
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "connect-src 'self'; font-src 'self'; manifest-src 'self'; worker-src 'self'; object-src 'none'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
SEC_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "same-origin",
               "Content-Security-Policy": CSP, "Permissions-Policy": "camera=(), microphone=(), geolocation=(), usb=(), payment=()"}


def make_handler(app):
    st, svc, media, limiter, rate = app.settings, app.service, app.media, app.limiter, app.rate

    class Handler(BaseHTTPRequestHandler):
        # ---------------- utilidades de respuesta
        def _send(self, code, body, ctype="application/json", headers=None):
            if not isinstance(body, bytes): body = json.dumps(body).encode()
            self.send_response(code)
            h = {"Content-Type": ctype, "Content-Length": str(len(body)), "Cache-Control": "no-store", **SEC_HEADERS}
            if self._https(): h["Strict-Transport-Security"] = "max-age=31536000"   # solo tiene sentido (y solo se aplica) por https
            extra = []
            if isinstance(headers, dict): h.update(headers)
            else: extra = list(headers or [])      # lista de pares: para poder mandar dos Set-Cookie
            for k, v in h.items(): self.send_header(k, v)
            for k, v in extra: self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json_etag(self, body, extra=""):
            """Manda un JSON con ETag propio de la aplicación. Si el navegador ya tiene lo mismo (If-None-Match),
            responde 304 sin cuerpo: no vuelve a bajar todo el listado de órdenes."""
            sello = 'W/"%s-%s"' % (svc.sello(), md5(str(extra).encode()).hexdigest()[:8])
            if self.headers.get("If-None-Match") == sello: return self._send(304, b"", headers={"ETag": sello})
            return self._send(200, body, headers={"ETag": sello})

        def _redirect(self, to):
            self.send_response(302); self.send_header("Location", to); self.send_header("Content-Length", "0"); self.end_headers()

        def _file(self, path, cache="no-store"):
            """Entrega un archivo. Con cache="no-cache" manda ETag y responde 304 si no cambió (ahorra bajar CSS/JS en cada visita)."""
            try: stt = os.stat(path)
            except OSError: return self._send(404, {"error": "not found"})
            etag = 'W/"%d-%d"' % (int(stt.st_mtime), stt.st_size)
            if cache != "no-store" and self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                for k, v in {"ETag": etag, "Cache-Control": cache}.items(): self.send_header(k, v)
                self.end_headers(); return
            with open(path, "rb") as f: data = f.read()
            return self._send(200, data, TYPES.get(os.path.splitext(path)[1], "application/octet-stream"),
                              {"ETag": etag, "Cache-Control": cache})

        def _json(self):
            n = int(self.headers.get("Content-Length", 0))
            if n > st.max_body: raise ValueError("body too large")
            return json.loads(self.rfile.read(n) or b"{}")

        # ---------------- sesión
        def _token(self):
            ck = SimpleCookie(self.headers.get("Cookie", ""))
            for n in ("__Host-crm_sid", "crm_sid"):     # __Host- cuando hay https; crm_sid en http de la red local
                m = ck.get(n)
                if m and m.value: return m.value
            return ""

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

        def _origen_ok(self):
            """Frena pedidos que un navegador manda desde otro sitio (CSRF). Los clientes que no son navegadores no mandan Origin."""
            o = self.headers.get("Origin")
            if not o: return True
            try: u = urlparse(o)
            except Exception: return False
            return bool(u.netloc) and u.netloc == (self.headers.get("Host") or "")

        def _cookie(self, token, max_age):
            """Devuelve la cabecera Set-Cookie. Con https usa el prefijo __Host- (no se puede pisar desde un subdominio);
            al cerrar sesión (token vacío) borra también el otro nombre, por si quedó de antes."""
            sec = "; Secure" if (st.cookie_secure and self._https()) else ""
            name = "__Host-crm_sid" if sec else "crm_sid"
            out = [("Set-Cookie", f"{name}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{sec}")]
            if not token:
                other = "crm_sid" if name.startswith("__Host-") else "__Host-crm_sid"
                out.append(("Set-Cookie", f"{other}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" + ("; Secure" if other.startswith("__Host-") else "")))
            return out

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
            return self._file(full, cache="no-cache")

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
            if p.startswith("/seguimiento/"):
                # Portal del cliente: sin login, pero con un link firmado que solo sirve para su propia orden.
                if not rate.allow(self._ip()): return self._send(429, {"error": "Demasiadas solicitudes seguidas. Probá en un rato."})
                partes = [x for x in p[len("/seguimiento/"):].split("/") if x]
                clave, o = svc.config().get("seg_clave", ""), None
                if len(partes) == 2 and partes[0].isdigit() and clave:
                    o = next((x for x in svc.orders() if x["seq"] == int(partes[0])), None)
                    if o and not seg.valido(clave, o["seq"], o["id"], partes[1]): o = None
                if not o: return self._send(404, seg.invalido().encode(), "text/html; charset=utf-8")
                return self._send(200, seg.pagina(svc.config(), o).encode(), "text/html; charset=utf-8")
            if not p.startswith("/api/"): return self._send(404, {"error": "not found"})
            if not user: return self._send(401, {"error": "login"})
            if p == "/api/data":
                cfg = svc.config(); cfg.pop("pin", None)
                clave = cfg.pop("seg_clave", "")          # la clave secreta nunca sale del servidor
                ordenes = svc.orders()
                if clave: ordenes = [{**o, "seg": seg.token(clave, o["seq"], o["id"])} for o in ordenes]
                return self._json_etag({"ordenes": ordenes, "config": cfg, "usuario": user, "tecnicos": svc.usernames(), "sync": svc.status()})
            if p == "/api/resumen":
                # Agregados del panel: se calculan acá (la base es mucho más rápida que el celular).
                q = parse_qs(u.query)
                desde, hasta, tz = q.get("desde", [""])[0], q.get("hasta", [""])[0], q.get("tz", [""])[0]
                return self._json_etag(resumen_datos(svc.orders(), svc.config(), desde, hasta, tz), f"{desde}|{hasta}|{tz}")
            if p == "/api/estado": return self._send(200, svc.status())
            if p == "/api/respaldo":
                # Respaldo completo de la base en un archivo JSON (solo el administrador).
                if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
                if not rate.allow(self._ip()): return self._send(429, {"error": "Demasiadas solicitudes seguidas. Esperá un momento."})
                body = json.dumps(backup_dump(app.store), ensure_ascii=False, indent=1).encode()
                return self._send(200, body, "application/json; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="respaldo-%s.json"' % time.strftime("%Y%m%d")})
            if p == "/api/qr":
                if not rate.allow(self._ip()): return self._send(429, {"error": "Demasiadas solicitudes seguidas. Esperá un momento."})
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
            if not self._origen_ok(): return self._send(403, {"error": "Origen no permitido"})
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
            if p == "/api/config/renombrar":
                # Renombra una categoría ya usada por las órdenes (tipo de falla o de equipo) en todas ellas.
                if user["rol"] != "admin": return self._send(403, {"error": "Solo el administrador"})
                clave, de, a = str(d.get("clave", "")), str(d.get("de", "")).strip(), str(d.get("a", "")).strip()
                if clave not in ("fallas", "equipos") or not de or not a: return self._send(400, {"error": "Faltan datos para renombrar"})
                if len(a) > 60: return self._send(400, {"error": "El nombre nuevo no puede pasar de 60 caracteres"})
                if a == de: return self._send(200, {"ok": True, "cambiadas": 0})
                return self._send(200, {"ok": True, "cambiadas": svc.categoria_renombrar(clave, de, a, str(d.get("lista", "")))})
            if p == "/api/comprobante":
                if not rate.allow(self._ip()): return self._send(429, {"error": "Demasiadas solicitudes seguidas. Esperá un momento."})
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
            if not self._origen_ok(): return self._send(403, {"error": "Origen no permitido"})
            user = self._user()
            if not user: return self._send(401, {"error": "login"})
            if self.path.startswith("/api/orden/"):
                if user["rol"] != "admin": return self._send(403, {"error": "Para borrar de verdad hace falta ser administrador (los demás pueden mandarla a la papelera)."})
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
