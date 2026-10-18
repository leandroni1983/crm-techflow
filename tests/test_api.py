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
        for n in ("db", "util", "dominio", "comprobantes", "dashboard", "lista", "orden", "config", "app"):
            self.assertEqual(c.get(f"/static/js/{n}.js")[0], 401, n)  # la lógica solo se entrega con sesión
        code, _, h = c.get("/"); self.assertEqual((code, h["Location"]), (302, "/login"))
        self.assertEqual(c.get("/media/o1/aaaaaaaaaaaaaaaaaaaa.jpg")[0], 401)
        for public in ("/login", "/health", "/sw.js", "/manifest.webmanifest", "/static/css/styles.css", "/static/js/login.js", "/static/img/icon-192.png"):
            self.assertEqual(c.get(public)[0], 200, public)

    def test_login_logout_y_cookie(self):
        c = self.c
        code, body, _ = c.login(password="mala"); self.assertEqual(code, 401)
        code, _, h = c.login(); self.assertEqual(code, 200)
        self.assertIn("HttpOnly", h["Set-Cookie"]); self.assertIn("SameSite=Lax", h["Set-Cookie"]); self.assertNotIn("Secure", h["Set-Cookie"])
        self.assertEqual(c.get("/api/data")[0], 200)
        self.assertEqual(c.get("/static/js/app.js")[0], 200); self.assertEqual(c.get("/static/js/dashboard.js")[0], 200)
        c.post("/api/logout"); self.assertEqual(c.get("/api/data")[0], 401)

    def test_bloqueo_tras_intentos_fallidos_por_ip(self):
        with Env() as e:
            c = e.client(); codes = [c.login(password="x%d" % i)[0] for i in range(7)]
            self.assertEqual(codes[:5], [401] * 5); self.assertEqual(codes[5:], [429, 429])
            self.assertEqual(e.client().post("/api/login", {"usuario": "admin", "password": "Secreta123"}, headers={})[0], 429)  # misma IP

    def test_cookie_secure_solo_si_llego_por_https(self):
        with Env(cookie_secure=True) as e:
            _, _, h = e.client().login(); self.assertNotIn("Secure", h["Set-Cookie"])           # http de la red local
            _, _, h = e.client().post("/api/login", {"usuario": "admin", "password": "Secreta123"}, headers={"X-Forwarded-Proto": "https"})
            self.assertIn("Secure", h["Set-Cookie"])                                            # vía Cloudflare/proxy

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
        self.assertEqual(a.delete("/api/usuarios/tec1")[0], 200); self.assertEqual(t.get("/api/data")[0], 401)  # sus sesiones se cierran

    def test_cambio_de_contrasena_cierra_las_otras_sesiones(self):
        with Env() as e:
            a, b = e.client(), e.client(); a.login(); b.login()
            self.assertEqual(a.post("/api/password", {"actual": "mala", "nueva": "NuevaClave456"})[0], 400)
            self.assertEqual(a.post("/api/password", {"actual": "Secreta123", "nueva": "NuevaClave456"})[0], 200)
            self.assertEqual((a.get("/api/data")[0], b.get("/api/data")[0]), (200, 401))
            self.assertEqual(e.client().login(password="Secreta123")[0], 401); self.assertEqual(e.client().login(password="NuevaClave456")[0], 200)

    # ---- clientes, equipos y fallas
    def test_la_orden_crea_cliente_y_equipo_sin_duplicar(self):
        with Env() as e:
            c = e.client(); c.login()
            c.post("/api/orden", {"id": "a", "cliente": "Ana", "tel": "011 5555-1234", "equipo": "Notebook", "marca": "HP", "serie": "SN1", "fallas": ["No enciende", " ", "Pantalla rota"]})
            c.post("/api/orden", {"id": "b", "cliente": "Ana Pérez", "tel": "+54 9 11 5555 1234", "equipo": "Notebook", "marca": "HP", "serie": "sn1"})   # mismo cliente y equipo
            c.post("/api/orden", {"id": "c", "cliente": "Ana Pérez", "tel": "1155551234", "equipo": "Impresora", "marca": "Epson"})                        # mismo cliente, otro equipo
            d = c.get("/api/data")[1]; o = {x["id"]: x for x in d["ordenes"]}
            self.assertEqual(len(d["clientes"]), 1); self.assertEqual(len(d["equipos"]), 2)
            self.assertEqual({o["a"]["cliente_id"], o["b"]["cliente_id"], o["c"]["cliente_id"]}, {d["clientes"][0]["id"]})
            self.assertEqual(o["a"]["equipo_id"], o["b"]["equipo_id"]); self.assertNotEqual(o["a"]["equipo_id"], o["c"]["equipo_id"])
            self.assertEqual(o["a"]["fallas"], ["No enciende", "Pantalla rota"])                               # el catálogo de fallas se guarda limpio

    def test_editar_y_borrar_clientes_y_equipos(self):
        with Env() as e:
            c = e.client(); c.login()
            c.post("/api/orden", {"id": "a", "cliente": "Ana", "tel": "1155551234", "equipo": "Notebook", "marca": "HP", "serie": "SN1"})
            d = c.get("/api/data")[1]; cid, eid = d["clientes"][0]["id"], d["equipos"][0]["id"]
            code, r, _ = c.post("/api/cliente", {"id": cid, "nombre": "Ana María", "tel": "1100000000", "email": "a@x.com", "notas": "Prefiere WhatsApp"})
            self.assertEqual((code, r["nombre"], r["email"]), (200, "Ana María", "a@x.com"))
            self.assertEqual(c.post("/api/equipo", {"id": eid, "cliente_id": cid, "tipo": "Notebook", "marca": "Lenovo", "serie": "SN1", "color": "Gris"})[0], 200)
            o = c.get("/api/data")[1]["ordenes"][0]; self.assertEqual((o["cliente"], o["tel"], o["marca"]), ("Ana María", "1100000000", "Lenovo"))
            self.assertEqual(c.post("/api/cliente", {"nombre": "  "})[0], 400)                                  # nombre obligatorio
            self.assertEqual(c.post("/api/equipo", {"cliente_id": "nadie", "tipo": "PC"})[0], 400)              # el cliente tiene que existir
            self.assertEqual(c.post("/api/equipo", {"cliente_id": cid})[0], 400)                                # algún dato del equipo
            self.assertEqual(c.delete(f"/api/cliente/{cid}")[0], 400); self.assertEqual(c.delete(f"/api/equipo/{eid}")[0], 400)   # tienen órdenes
            c.delete("/api/orden/a"); self.assertEqual(c.delete(f"/api/equipo/{eid}")[0], 200); self.assertEqual(c.delete(f"/api/cliente/{cid}")[0], 200)
            self.assertEqual(c.get("/api/data")[1]["clientes"], [])

    def test_no_se_pisan_clientes_ni_equipos_con_el_mismo_telefono_o_serie(self):
        with Env() as e:
            c = e.client(); c.login()
            ana = c.post("/api/cliente", {"nombre": "Ana", "tel": "1155551234"})[1]
            self.assertEqual(c.post("/api/cliente", {"nombre": "Otra Ana", "tel": "011 5555-1234"})[0], 400)       # mismo teléfono, otro formato
            luis = c.post("/api/cliente", {"nombre": "Luis", "tel": "1166667777"})[1]
            code, r, _ = c.post("/api/cliente", {"id": luis["id"], "nombre": "Luis", "tel": "1155551234"}); self.assertEqual(code, 400)   # no puede quedarse con el teléfono de Ana
            self.assertIn("Ana", r["error"])
            code, r, _ = c.post("/api/cliente", {"id": luis["id"], "nombre": "Luis", "tel": "1100001111"}); self.assertEqual(code, 200)     # cambiar a un teléfono libre sí
            # el id sale del teléfono original: aunque se lo corrija, el número nuevo sigue siendo de ese cliente
            c.post("/api/cliente", {"id": luis["id"], "nombre": "Luis", "tel": "1100001111"})
            self.assertEqual(c.post("/api/cliente", {"nombre": "Otro Luis", "tel": "011 0000-1111"})[0], 400)
            c.post("/api/orden", {"id": "z", "cliente": "Luis (de nuevo)", "tel": "1100001111", "equipo": "PC"})   # una orden con ese número se une a Luis, no crea otro cliente
            self.assertEqual(len(c.get("/api/data")[1]["clientes"]), 2)
            self.assertEqual(c.post("/api/equipo", {"cliente_id": ana["id"], "tipo": "Notebook", "serie": "SN1"})[0], 200)
            self.assertEqual(c.post("/api/equipo", {"cliente_id": ana["id"], "tipo": "Otra", "serie": "sn1"})[0], 400)                    # misma serie
            self.assertEqual(c.post("/api/equipo", {"cliente_id": ana["id"], "tipo": "Notebook", "serie": "SN2"})[0], 200)

    def test_un_equipo_de_otro_cliente_no_se_cuela_en_la_orden(self):
        with Env() as e:
            c = e.client(); c.login()
            c.post("/api/orden", {"id": "a", "cliente": "Ana", "tel": "1155551234", "equipo": "Notebook", "serie": "SN1"})
            ajeno = c.get("/api/data")[1]["equipos"][0]["id"]
            c.post("/api/orden", {"id": "b", "cliente": "Luis", "tel": "1166667777", "equipo": "PC", "serie": "SN2", "equipo_id": ajeno})
            d = c.get("/api/data")[1]; o = {x["id"]: x for x in d["ordenes"]}
            self.assertNotEqual(o["b"]["equipo_id"], ajeno); self.assertEqual(len(d["equipos"]), 2)

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
