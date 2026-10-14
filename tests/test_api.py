"""API HTTP real (servidor en un hilo): sesión, permisos, medios, historial sellado por el servidor, estáticos."""
import unittest

from tests.helpers import Env, jpeg_url, jpeg_url2


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.env = Env(); cls.url = cls.env.url

    @classmethod
    def tearDownClass(cls): cls.env.close()

    def setUp(self): self.c = self.env.client()

    # ---- sesión
    def test_sin_sesion_todo_esta_protegido(self):
        c = self.c
        self.assertEqual(c.get("/api/data")[0], 401)
        self.assertEqual(c.get("/static/js/app.js")[0], 401)          # la lógica solo se entrega con sesión
        self.assertEqual(c.get("/static/js/db.js")[0], 401)
        code, _, h = c.get("/"); self.assertEqual((code, h["Location"]), (302, "/login"))
        self.assertEqual(c.get("/media/o1/aaaaaaaaaaaaaaaaaaaa.jpg")[0], 401)
        for public in ("/login", "/health", "/sw.js", "/manifest.webmanifest", "/static/css/styles.css", "/static/js/login.js", "/static/img/icon-192.png"):
            self.assertEqual(c.get(public)[0], 200, public)

    def test_login_logout_y_cookie(self):
        c = self.c
        code, body, _ = c.login(password="mala"); self.assertEqual(code, 401)
        code, _, h = c.login(); self.assertEqual(code, 200)
        self.assertIn("crm_sid=", h["Set-Cookie"])                                              # por http, sin prefijo
        self.assertIn("HttpOnly", h["Set-Cookie"]); self.assertIn("SameSite=Lax", h["Set-Cookie"]); self.assertNotIn("Secure", h["Set-Cookie"])
        self.assertEqual(c.get("/api/data")[0], 200)
        self.assertEqual(c.get("/static/js/app.js")[0], 200)
        c.post("/api/logout"); self.assertEqual(c.get("/api/data")[0], 401)
        self.assertEqual(c.get("/static/js/app.js")[0], 401)

    def test_bloqueo_tras_intentos_fallidos_por_ip(self):
        with Env() as e:
            c = e.client(); codes = [c.login(password="x%d" % i)[0] for i in range(7)]
            self.assertEqual(codes[:5], [401] * 5); self.assertEqual(codes[5:], [429, 429])
            self.assertEqual(e.client().post("/api/login", {"usuario": "admin", "password": "Secreta123"}, headers={})[0], 429)  # misma IP

    def test_cookie_secure_solo_si_llego_por_https(self):
        with Env(cookie_secure=True) as e:
            _, _, h = e.client().login(); self.assertNotIn("Secure", h["Set-Cookie"])           # http de la red local
            self.assertIn("crm_sid=", h["Set-Cookie"])
            _, _, h = e.client().post("/api/login", {"usuario": "admin", "password": "Secreta123"}, headers={"X-Forwarded-Proto": "https"})
            self.assertIn("Secure", h["Set-Cookie"])                                            # vía Cloudflare/proxy
            self.assertIn("__Host-crm_sid=", h["Set-Cookie"])                                   # con https, cookie reforzada
            self.assertEqual(h["Strict-Transport-Security"], "max-age=31536000")

    def test_cabeceras_de_seguridad(self):
        c = self.c; c.login()
        code, _, h = c.get("/")
        self.assertEqual(code, 200)
        self.assertIn("script-src 'self'", h["Content-Security-Policy"])                        # nada de JS de terceros
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
        self.assertIn("object-src 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertIn("geolocation=()", h["Permissions-Policy"])
        self.assertNotIn("Strict-Transport-Security", h)                                        # HSTS solo por https

    def test_pedido_de_otro_sitio_se_rechaza(self):
        c = self.c; c.login()
        self.assertEqual(c.post("/api/config", {"taller": "X"}, headers={"Origin": "https://malo.example"})[0], 403)
        self.assertEqual(c.delete("/api/orden/loquesea", headers={"Origin": "https://malo.example"})[0], 403)
        self.assertEqual(c.post("/api/config", {"taller": "Taller propio"}, headers={"Origin": self.env.url})[0], 200)
        self.assertEqual(c.get("/api/data")[1]["config"]["taller"], "Taller propio")

    def test_limite_en_los_endpoints_pesados(self):
        with Env() as e:
            c = e.client(); c.login()
            codes = [c.get("/api/qr?t=x")[0] for _ in range(125)]     # el límite es 120 por minuto
            self.assertEqual(set(codes[:120]), {200}); self.assertEqual(set(codes[120:]), {429})

    def test_los_estaticos_se_revalidan_con_etag(self):
        c = self.c; c.login()
        code, _, h = c.get("/static/css/styles.css")
        self.assertEqual((code, h["Content-Type"]), (200, "text/css; charset=utf-8"))
        self.assertIn("no-cache", h["Cache-Control"]); self.assertTrue(h["ETag"].startswith('W/"'))
        self.assertEqual(c.get("/static/css/styles.css", headers={"If-None-Match": h["ETag"]})[0], 304)   # no se baja de nuevo

    def test_avisa_si_la_clave_de_arranque_es_debil(self):
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with Env(admin_password="cambiame"): pass
        self.assertIn("ADMIN_PASSWORD es corta", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with Env(admin_password="UnaClaveLargaYSegura"): pass
        self.assertNotIn("ADMIN_PASSWORD es corta", buf.getvalue())

    def test_ip_real_con_cloudflare_no_se_puede_falsear(self):
        with Env(trust_proxy=True) as e:
            c = e.client(); h = lambda i: {"CF-Connecting-IP": "203.0.113.5", "X-Forwarded-For": "9.9.9.%d" % i}
            codes = [c.post("/api/login", {"usuario": "admin", "password": "x"}, headers=h(i))[0] for i in range(7)]
            self.assertEqual(codes[-1], 429)
            ok = e.client().post("/api/login", {"usuario": "admin", "password": "Secreta123"}, headers={"CF-Connecting-IP": "198.51.100.7"})[0]
            self.assertEqual(ok, 200)  # otro visitante real no queda bloqueado

    # ---- órdenes, medios, historial
    def test_orden_fotos_firma_e_historial_sellado(self):
        c = self.c; c.login()
        o = {"id": "ord1", "creada": "2026-10-10T10:00:00Z", "cliente": "Ana", "tel": "11", "tecnico": "admin", "seq": 999,
             "imagenes": [jpeg_url()], "firma": jpeg_url2(),
             "historial": [{"f": "2000-01-01", "t": "falso viejo", "u": "otro"}, {"f": "x", "t": "Orden creada", "n": True, "u": "hacker"}]}
        code, r, _ = c.post("/api/orden", o); self.assertEqual(code, 200)
        self.assertNotEqual(r["seq"], 999)                                       # el número lo decide el servidor
        self.assertEqual(len(r["historial"]), 1)                                 # lo viejo enviado por el cliente se ignora
        self.assertEqual((r["historial"][0]["u"], r["historial"][0]["t"]), ("admin", "Orden creada"))
        self.assertTrue(r["historial"][0]["f"].startswith("20") and r["historial"][0]["f"] != "x")
        self.assertRegex(r["imagenes"][0], r"^/media/ord1/[0-9a-f]{20}\.jpg$"); self.assertTrue(r["firma"].startswith("/media/ord1/"))
        code, body, h = c.get(r["imagenes"][0]); self.assertEqual((code, h["Content-Type"]), (200, "image/jpeg")); self.assertIn("immutable", h["Cache-Control"])
        self.assertEqual(body[:2], b"\xff\xd8")
        # editar sin la foto: el archivo huérfano se borra
        r2 = c.post("/api/orden", {**o, "imagenes": [], "firma": r["firma"], "historial": [{"t": "Estado: A → B", "n": True}]})[1]
        self.assertEqual(len(r2["historial"]), 2); self.assertEqual(c.get(r["imagenes"][0])[0], 404)
        c.delete("/api/orden/ord1"); self.assertEqual(c.get(r["firma"])[0], 404)  # borrar la orden borra sus archivos

    def test_comprobante_pdf(self):
        c = self.c; c.login()
        code, pdf, h = c.post("/api/comprobante", {"numero": "0001010126", "taller": "T", "filas": [["Cliente", "Ana"]], "sufijo": "-entrega",
                              "firma": jpeg_url(), "fotos": [jpeg_url()], "titulo": "Comprobante de entrega"})
        self.assertEqual((code, h["Content-Type"], pdf[:4]), (200, "application/pdf", b"%PDF"))
        import os; self.assertTrue(os.path.exists(self.env.path("comprobantes", "0001010126-entrega.pdf")))

    # ---- usuarios y roles
    def test_roles_y_gestion_de_usuarios(self):
        a = self.env.client(); a.login()
        self.assertEqual(a.post("/api/usuarios", {"nombre": "Tec1", "password": "clavecorta"[:5], "rol": "tecnico"})[0], 400)
        self.assertEqual(a.post("/api/usuarios", {"nombre": "Tec1", "password": "tecnico-pass-1", "rol": "tecnico"})[0], 200)
        self.assertEqual(a.post("/api/usuarios", {"nombre": "tec1", "password": "tecnico-pass-1"})[0], 400)  # ya existe
        t = self.env.client(); self.assertEqual(t.login("tec1", "tecnico-pass-1")[0], 200)
        self.assertEqual(t.get("/api/usuarios")[0], 403); self.assertEqual(t.get("/api/data")[0], 200)
        self.assertEqual(t.delete("/api/usuarios/admin")[0], 403)
        self.assertEqual(a.delete("/api/usuarios/admin")[0], 400)               # no podés borrarte a vos mismo
        self.assertIn("tec1", a.get("/api/data")[1]["tecnicos"])
        # el tipo de falla (configuración) solo lo puede cambiar el administrador
        self.assertEqual(t.post("/api/config", {"fallas": "Solo esta"})[0], 403)
        self.assertEqual(a.post("/api/config", {"fallas": "No enciende\nOtro"})[0], 200)
        self.assertEqual(a.get("/api/data")[1]["config"]["fallas"], "No enciende\nOtro")
        self.assertEqual(t.post("/api/config", {"taller": "Otro taller"})[0], 200)   # el resto de la config sí puede
        self.assertEqual(a.delete("/api/usuarios/tec1")[0], 200); self.assertEqual(t.get("/api/data")[0], 401)  # sus sesiones se cierran

    def test_cambio_de_contrasena_cierra_las_otras_sesiones(self):
        with Env() as e:
            a, b = e.client(), e.client(); a.login(); b.login()
            self.assertEqual(a.post("/api/password", {"actual": "mala", "nueva": "NuevaClave456"})[0], 400)
            self.assertEqual(a.post("/api/password", {"actual": "Secreta123", "nueva": "NuevaClave456"})[0], 200)
            self.assertEqual((a.get("/api/data")[0], b.get("/api/data")[0]), (200, 401))
            self.assertEqual(e.client().login(password="Secreta123")[0], 401); self.assertEqual(e.client().login(password="NuevaClave456")[0], 200)

    # ---- estáticos y salud
    def test_estaticos_no_permiten_salirse_de_la_carpeta(self):
        self.c.login()
        for bad in ("/static/../server.py", "/static/css/../../__init__.py", "/static/%2e%2e/__init__.py", "/static//etc/passwd", "/static/js/..\\app.js"):
            self.assertEqual(self.c.get(bad)[0], 404, bad)

    def test_health_informa_version_y_estado(self):
        code, h, _ = self.c.get("/health"); self.assertEqual(code, 200)
        self.assertEqual((h["ok"], h["online"], h["pendientes"], h["motor"]), (True, True, 0, "SQLite")); self.assertRegex(h["version"], r"^\d+\.\d+\.\d+$")

    def test_sin_conexion_la_api_responde_y_avisa(self):
        with Env() as e:
            c = e.client(); c.login(); e.go_offline()
            code, r, _ = c.post("/api/orden", {"id": "x", "cliente": "Off", "tel": "1"}); self.assertEqual(code, 200)   # se encola
            self.assertEqual(c.get("/health?deep=1")[0], 503)
            self.assertEqual(c.get("/health")[0], 200)                                # vivo aunque la base no esté
            self.assertEqual(c.post("/api/usuarios", {"nombre": "nuevo1", "password": "unaclavelarga1"})[0], 503)
            self.assertEqual(c.get("/api/estado")[1]["pendientes"], 1)


if __name__ == "__main__": unittest.main()
