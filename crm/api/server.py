import socket, webbrowser
from http.server import ThreadingHTTPServer

from ..bootstrap import drop_privileges
from ..log import log
from .handler import make_handler


def make_server(app, host=None, port=None):
    """Crea el servidor HTTP (no lo arranca). port=0 elige un puerto libre (útil en pruebas)."""
    s = app.settings
    return ThreadingHTTPServer((host or s.host, s.port if port is None else port), make_handler(app))


def _lan_ip():
    try:
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sk.connect(("8.8.8.8", 80)); ip = sk.getsockname()[0]; sk.close()
        return ip
    except Exception:
        return "IP-de-tu-PC"


def serve(app, lan=False):
    """Arranque de producción: inicia la app, baja privilegios (Docker), lanza la sincronización y atiende pedidos."""
    s = app.settings
    app.start()
    drop_privileges(s)
    app.service.start_thread()
    host = "0.0.0.0" if lan else s.host
    log(f"CRM en http://localhost:{s.port}  |  archivos: {s.data_dir}")
    if host == "0.0.0.0" and not s.drop_privileges: log(f"Acceso desde la red: http://{_lan_ip()}:{s.port}")
    if host == "127.0.0.1" and s.open_browser:
        try: webbrowser.open(f"http://localhost:{s.port}")
        except Exception: pass
    make_server(app, host).serve_forever()
