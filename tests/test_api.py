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
        for js in ("app", "db", "util", "comun", "cat", "orden", "lista", "config", "panel", "modo"):
            self.assertEqual(c.get("/static/js/%s.js" % js)[0], 401, js)   # la lógica solo se entrega con sesión
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
        for js in ("app", "db", "util", "comun", "cat", "orden", "lista", "config", "panel", "modo"):
            self.assertEqual(c.get("/static/js/%s.js" % js)[0], 200, js)
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

    # ---- papelera y respaldo
    def test_papelera_y_respaldo(self):
        a = self.env.client(); a.login()
        o = {"id": "pap1", "cliente": "Pablo", "tel": "1155550000"}
        self.assertEqual(a.post("/api/orden", o)[0], 200)
        # mandar a la papelera: la orden sigue en la base, marcada con la fecha
        self.assertEqual(a.post("/api/orden", {**o, "borrada": "2026-10-14T10:00:00Z"})[0], 200)
        pap = [x for x in a.get("/api/data")[1]["ordenes"] if x["id"] == "pap1"][0]
        self.assertEqual(pap["borrada"], "2026-10-14T10:00:00Z")
        # recuperarla deja la orden como estaba
        self.assertEqual(a.post("/api/orden", {**o, "borrada": ""})[0], 200)
        self.assertEqual([x for x in a.get("/api/data")[1]["ordenes"] if x["id"] == "pap1"][0]["borrada"], "")
        # el respaldo (solo administrador) trae configuración, usuarios y órdenes, papelera incluida
        a.post("/api/orden", {**o, "borrada": "2026-10-14T11:00:00Z"})
        code, d, h = a.get("/api/respaldo")
        self.assertEqual(code, 200)
        self.assertIn("attachment; filename=\"respaldo-", h["Content-Disposition"])
        self.assertEqual([x["id"] for x in d["ordenes"]], ["pap1"]); self.assertIn("admin", [u["nombre"] for u in d["usuarios"]])
        self.assertTrue(d["fecha"] and d["app"] == "crm-tecnico" and isinstance(d["config"], dict))
        # borrar de verdad (DELETE) es solo del administrador: los técnicos usan la papelera
        a.post("/api/usuarios", {"nombre": "tec-pap", "password": "clave-tec-1234", "rol": "tecnico"})
        t = self.env.client(); t.login("tec-pap", "clave-tec-1234")
        self.assertEqual(t.delete("/api/orden/pap1")[0], 403)
        self.assertEqual(t.get("/api/respaldo")[0], 403)
        self.assertEqual(a.delete("/api/orden/pap1")[0], 200)
        self.assertNotIn("pap1", [x["id"] for x in a.get("/api/data")[1]["ordenes"]])
        a.delete("/api/usuarios/tec-pap")

    # ---- portal de seguimiento (lo abre el cliente, sin usuario ni contraseña)
    def test_portal_de_seguimiento(self):
        a = self.env.client(); a.login()
        a.post("/api/orden", {"id": "seg1", "cliente": "Seguim Cliente", "tel": "11", "equipo": "Notebook", "estado": "En reparación", "clave": "clave-interna-777"})
        d = a.get("/api/data")[1]
        o = [x for x in d["ordenes"] if x["id"] == "seg1"][0]
        self.assertTrue(o["seg"]); self.assertNotIn("seg_clave", d["config"])     # la clave secreta no sale del servidor
        sin_sesion = self.env.client()                                            # sin cookies: cualquiera con el link entra
        code, pag, h = sin_sesion.get(f"/seguimiento/{o['seq']}/{o['seg']}")
        self.assertEqual(code, 200); self.assertEqual(h["Content-Type"], "text/html; charset=utf-8")
        pag = pag.decode()
        self.assertIn("Seguim Cliente", pag); self.assertIn("En reparación", pag)
        self.assertNotIn("clave-interna-777", pag)                                # las notas internas no se muestran
        self.assertEqual(sin_sesion.get(f"/seguimiento/{o['seq']}/000000000000")[0], 404)   # token cambiado
        self.assertEqual(sin_sesion.get("/seguimiento/999/000000000000")[0], 404)           # orden que no existe
        self.assertEqual(sin_sesion.get(f"/seguimiento/{o['seq']}/{o['seg']}/x")[0], 404)
        a.delete("/api/orden/seg1")

    # ---- panel de estadísticas: agregación en el servidor y ETag
    def test_resumen_y_etag_del_servidor(self):
        """El panel puede pedir los números ya calculados y no bajar de nuevo lo que no cambió."""
        a = self.env.client(); a.login()
        for i, (est, fecha) in enumerate([("Entregado", ""), ("Listo para retirar", "2020-01-01T00:00:00Z")]):
            self.assertEqual(a.post("/api/orden", {
                "id": "res%d" % i, "creada": "2024-04-0%dT10:00:00Z" % (i + 1), "cliente": "R%d" % i, "tel": "11",
                "equipo_tipo": "Notebook", "falla_tipo": "No enciende", "estado": est, "estado_fecha": fecha,
                "monto": "10000", "entrega_fecha": "2024-04-20" if est == "Entregado" else "",
                "repuestos": [{"desc": "Batería", "cant": "2", "costo": "1000"}]})[0], 200)
        url = "/api/resumen?desde=2024-04-01&hasta=2024-04-30"
        code, d, h = a.get(url)
        self.assertEqual(code, 200)
        self.assertEqual((d["ingresadas"], d["pendientes"], d["entregadas"]), (2, 1, 1))
        self.assertEqual((d["facturado"], d["repuestos"], d["ganancia"]), (10000, 2000, 8000))
        self.assertEqual(d["ticket"], 10000)
        self.assertEqual(d["fallas"], [{"label": "No enciende", "value": 2}])
        self.assertEqual(d["equipos"], [{"label": "Notebook", "value": 2}])
        self.assertEqual(d["sinretirar"], 1)                                        # el que está listo hace años
        self.assertEqual(d["porMes"]["2024-04"], {"n": 2, "fact": 10000, "cost": 2000})
        self.assertIn("2024-04", d["meses"]); self.assertEqual(len(d["meses"]), 12)
        # el ETag evita volver a bajar lo mismo (ni el resumen ni todas las órdenes)
        self.assertEqual(a.get(url, headers={"If-None-Match": h["ETag"]})[0], 304)
        code, _, hd = a.get("/api/data")
        self.assertEqual(code, 200); self.assertTrue(hd["ETag"])
        self.assertEqual(a.get("/api/data", headers={"If-None-Match": hd["ETag"]})[0], 304)
        # al cambiar algo, cambia el sello y se vuelve a mandar todo
        a.post("/api/orden", {"id": "res9", "cliente": "Otra", "tel": "11"})
        code, _, hd2 = a.get("/api/data")
        self.assertEqual(code, 200); self.assertNotEqual(hd2["ETag"], hd["ETag"])
        # el sello mira TODA la base (es conservador): con cualquier cambio se vuelve a calcular
        self.assertEqual(a.get(url, headers={"If-None-Match": h["ETag"]})[0], 200)
        for i in ("res0", "res1", "res9"): self.assertEqual(a.delete("/api/orden/" + i)[0], 200)

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
        # lo mismo para los tipos de equipo (lista aparte)
        self.assertEqual(t.post("/api/config", {"equipos": "Solo este"})[0], 403)
        self.assertEqual(a.post("/api/config", {"equipos": "Notebook\nCelular\nOtro"})[0], 200)
        self.assertEqual(a.get("/api/data")[1]["config"]["equipos"], "Notebook\nCelular\nOtro")
        # y el inventario de repuestos (se guarda como lista JSON dentro de la configuración)
        inv = '[{"id": "r1", "nombre": "Batería", "stock": "3", "minimo": "1", "costo": "6000"}]'
        self.assertEqual(t.post("/api/config", {"repuestos": inv})[0], 403)
        self.assertEqual(a.post("/api/config", {"repuestos": inv})[0], 200)
        self.assertIn("Batería", a.get("/api/data")[1]["config"]["repuestos"])
        self.assertEqual(t.post("/api/config", {"taller": "Otro taller"})[0], 200)   # el resto de la config sí puede
        self.assertEqual(a.delete("/api/usuarios/tec1")[0], 200); self.assertEqual(t.get("/api/data")[0], 401)  # sus sesiones se cierran

    def test_renombrar_categorias_actualiza_las_ordenes(self):
        """Renombrar un tipo de falla o de equipo cambia también las órdenes que ya lo usaban (y solo el admin puede)."""
        a = self.env.client(); a.login()
        a.post("/api/orden", {"id": "ren1", "cliente": "Ana", "tel": "11", "equipo": "Notebook Lenovo", "marca": "Lenovo",
                              "equipo_tipo": "Notebook", "falla_tipo": "No enciende"})
        a.post("/api/usuarios", {"nombre": "tec-ren", "password": "clave-tec-1234", "rol": "tecnico"})
        t = self.env.client(); t.login("tec-ren", "clave-tec-1234")
        self.assertEqual(t.post("/api/config/renombrar", {"clave": "fallas", "de": "No enciende", "a": "No arranca", "lista": "No arranca"})[0], 403)
        for malo in ({"clave": "fallas", "de": "No enciende"}, {"clave": "otra", "de": "x", "a": "y"},
                     {"clave": "fallas", "de": "No enciende", "a": "x" * 61}):
            self.assertEqual(a.post("/api/config/renombrar", malo)[0], 400, malo)
        # renombrar el tipo de falla: se actualiza la orden vieja y la lista de configuración
        code, r, _ = a.post("/api/config/renombrar", {"clave": "fallas", "de": "No enciende", "a": "No arranca", "lista": "No arranca\nOtro"})
        self.assertEqual((code, r["cambiadas"]), (200, 1))
        self.assertEqual(a.get("/api/data")[1]["config"]["fallas"], "No arranca\nOtro")
        self.assertEqual(self._orden(a, "ren1")["falla_tipo"], "No arranca")
        # renombrar el tipo de equipo
        self.assertEqual(a.post("/api/config/renombrar", {"clave": "equipos", "de": "Notebook", "a": "Notebook / portátil", "lista": "Notebook / portátil"})[1]["cambiadas"], 1)
        self.assertEqual(self._orden(a, "ren1")["equipo_tipo"], "Notebook / portátil")
        # renombrar a lo mismo no toca nada, y un valor sin órdenes tampoco rompe
        self.assertEqual(a.post("/api/config/renombrar", {"clave": "equipos", "de": "Notebook / portátil", "a": "Notebook / portátil", "lista": "x"})[1]["cambiadas"], 0)
        self.assertEqual(a.post("/api/config/renombrar", {"clave": "fallas", "de": "No existe", "a": "Otro nombre", "lista": "Otro nombre"})[1]["cambiadas"], 0)
        a.delete("/api/usuarios/tec-ren"); a.delete("/api/orden/ren1")

    def _orden(self, c, oid):
        return [o for o in c.get("/api/data")[1]["ordenes"] if o["id"] == oid][0]

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
