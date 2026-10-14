"""Soporte común de las pruebas: aplicación en memoria con SQLite temporal, servidor HTTP real y cliente con cookies."""
import http.cookiejar, json, os, shutil, tempfile, threading, time, urllib.error, urllib.request

from crm.api import make_server
from crm.app import App
from crm.config import Settings
from crm.db import open_store

TINY_JPEG = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAAMABADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDCooorzj7E/9k="  # JPEG válido de 16x12, para no depender de Pillow


def jpeg_url(): return "data:image/jpeg;base64," + TINY_JPEG


def jpeg_url2():
    """Otro JPEG válido con distinto contenido (le agrega un comentario), para probar archivos distintos."""
    import base64
    b = base64.b64decode(TINY_JPEG)
    return "data:image/jpeg;base64," + base64.b64encode(b[:2] + b"\xff\xfe\x00\x05abc" + b[2:]).decode()


def wait_until(cond, secs=10, step=0.05):
    end = time.time() + secs
    while time.time() < end:
        if cond(): return True
        time.sleep(step)
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None


class Client:
    """Cliente HTTP con cookies que NO sigue redirecciones (para poder comprobarlas)."""

    def __init__(self, base):
        self.base, self.jar = base, http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect)

    def req(self, method, path, data=None, headers=None):
        h = {"Content-Type": "application/json", **(headers or {})}
        body = json.dumps(data).encode() if data is not None else None
        try:
            r = self.opener.open(urllib.request.Request(self.base + path, data=body, method=method, headers=h))
            code, raw, hd = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            code, raw, hd = e.code, e.read(), e.headers
        try: parsed = json.loads(raw)
        except Exception: parsed = None
        return code, (parsed if parsed is not None else raw), hd

    def get(self, path, **k): return self.req("GET", path, **k)
    def post(self, path, data=None, **k): return self.req("POST", path, data if data is not None else {}, **k)
    def delete(self, path, **k): return self.req("DELETE", path, **k)

    def login(self, user="admin", password="Secreta123"):
        return self.post("/api/login", {"usuario": user, "password": password})


class Env:
    """Una app completa en un directorio temporal. Uso: with Env() as env: env.client().login() ..."""

    def __init__(self, serve=True, **settings):
        self.tmp = tempfile.mkdtemp(prefix="crmtest_")
        self.flag = os.path.join(self.tmp, "OFFLINE")  # si existe este archivo, la base "se cae"
        base = dict(data_dir=self.tmp, database_url="sqlite:///" + os.path.join(self.tmp, "crm.db"), admin_password="Secreta123", sync_secs=1)
        base.update(settings)
        self.settings = Settings(**base)
        self.store = open_store(self.settings.database_url, offline_flag=self.flag)
        self.app = App(self.settings, self.store)
        self.app.start()
        self.server = self.url = None
        if serve:
            self.server = make_server(self.app, "127.0.0.1", 0)
            self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
            threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def client(self): return Client(self.url)
    def go_offline(self): open(self.flag, "w").close()
    def go_online(self): os.path.exists(self.flag) and os.remove(self.flag)
    def path(self, *p): return os.path.join(self.tmp, *p)

    def close(self):
        if self.server: self.server.shutdown(); self.server.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self): return self
    def __exit__(self, *a): self.close()


def order(i, **kw):
    return {"id": i, "creada": "2026-10-10T10:00:00Z", "cliente": "C" + i, "tel": "11", "estado": "Recibido", **kw}


def hist(text, user="admin"): return {"f": "2026-10-10T10:00:00Z", "t": text, "u": user}
