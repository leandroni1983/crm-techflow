"""Capa de datos: migraciones, base vieja, protección de versión, secuencia e historial."""
import os, shutil, sqlite3, tempfile, unittest

from crm.db import LATEST, SqliteStore, norm_order
from crm.media import MediaStore
from tests.helpers import hist, jpeg_url, order


class DbTest(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_base_nueva_queda_en_la_ultima_version(self):
        st = SqliteStore(os.path.join(self.tmp, "n.db"))
        self.assertEqual(st.migrate(), LATEST)
        self.assertEqual(st.migrate(), LATEST)  # idempotente
        self.assertEqual(st.info()["escritura"], "ok (deshecha)")

    def test_base_vieja_se_migra_sin_perder_datos(self):
        p = os.path.join(self.tmp, "viejo.db"); c = sqlite3.connect(p)
        c.executescript("""CREATE TABLE ordenes(id TEXT PRIMARY KEY, seq INTEGER NOT NULL, creada TEXT, cliente TEXT, imagenes TEXT DEFAULT '[]', firma TEXT);
        CREATE TABLE config(k TEXT PRIMARY KEY, v TEXT); CREATE TABLE usuarios(nombre TEXT PRIMARY KEY, hash TEXT NOT NULL, rol TEXT NOT NULL, creado TEXT);
        CREATE TABLE sesiones(token TEXT PRIMARY KEY, usuario TEXT NOT NULL, expira REAL NOT NULL);""")
        c.execute("INSERT INTO ordenes(id,seq,creada,cliente) VALUES('v1',7,'2026-01-01T00:00:00Z','Viejo')"); c.commit(); c.close()
        st = SqliteStore(p); st.migrate(); o = st.orders_all()[0]
        self.assertEqual((o["cliente"], o["seq"], o["checklist"]), ("Viejo", 7, []))
        self.assertEqual(o["falla_tipo"], "")  # la columna nueva se agrega vacía
        self.assertEqual(st.next_seq(1), [8])  # la secuencia continúa después del mayor número

    def test_tipo_de_falla_se_guarda_y_vuelve(self):
        st = SqliteStore(os.path.join(self.tmp, "ft.db")); st.migrate()
        st.order_save(norm_order(order("x", falla_tipo="No carga / batería")), [])
        self.assertEqual(st.orders_all()[0]["falla_tipo"], "No carga / batería")

    def test_base_mas_nueva_que_el_programa_no_arranca(self):
        p = os.path.join(self.tmp, "f.db"); st = SqliteStore(p); st.migrate()
        c = sqlite3.connect(p); c.execute("INSERT INTO schema_version VALUES(99,'x','futura')"); c.commit(); c.close()
        with self.assertRaises(RuntimeError): st.migrate()

    def test_historial_se_acumula_sin_duplicar_y_marca_conflictos(self):
        st = SqliteStore(os.path.join(self.tmp, "h.db")); st.migrate()
        r1 = st.order_save(order("a"), [hist("creada")]); self.assertEqual(r1["seq"], 1)
        r2 = st.order_save(order("a"), [hist("creada"), hist("editada")]); self.assertEqual([h["t"] for h in r2["historial"]], ["creada", "editada"])
        r3 = st.order_save(order("a"), [], base_mod="2000-01-01T00:00:00Z")  # alguien la cambió mientras tanto
        self.assertTrue(any("Sincronización" in h["t"] for h in r3["historial"]))
        self.assertEqual(st.order_save(order("b"), [])["seq"], 2)

    def test_usuarios_y_sesiones(self):
        st = SqliteStore(os.path.join(self.tmp, "u.db")); st.migrate()
        st.user_add("ana", "h", "tecnico")
        with self.assertRaises(ValueError): st.user_add("ana", "h", "tecnico")
        st.sess_add("t1", "ana", 9e9); st.sess_add("t2", "ana", 9e9)
        self.assertEqual(st.sess_get("t1")["nombre"], "ana")
        st.sess_del_others("ana", "t1"); self.assertIsNone(st.sess_get("t2"))
        st.user_del("ana"); self.assertIsNone(st.sess_get("t1"))  # borrar el usuario cierra sus sesiones

    def test_norm_order_completa_valores_faltantes(self):
        o = norm_order({"id": "x", "monto": 5})
        self.assertEqual((o["monto"], o["cliente"], o["repuestos"]), ("5", "", []))


class MediaTest(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True); self.m = MediaStore(self.tmp)

    def test_guarda_lee_y_limpia(self):
        url = self.m.save("o1", jpeg_url()); self.assertRegex(url, r"^/media/o1/[0-9a-f]{20}\.jpg$")
        self.assertEqual(self.m.save("o1", jpeg_url()), url)           # mismo contenido, mismo archivo
        self.assertEqual(self.m.read(url)[:2], b"\xff\xd8")
        self.assertEqual(self.m.save("o1", url), url)                  # una URL se deja igual
        self.m.clean("o1", []); self.assertIsNone(self.m.read(url))
        self.assertEqual(self.m.save("o1", "data:text/plain;base64,aGk="), "")  # solo JPEG

    def test_no_se_puede_salir_de_la_carpeta(self):
        for bad in ("/media/../crm.db", "/media/o1/../../x.jpg", "/media/o1/abc.jpg", "../etc/passwd"):
            self.assertIsNone(self.m.path(bad), bad)


if __name__ == "__main__": unittest.main()
