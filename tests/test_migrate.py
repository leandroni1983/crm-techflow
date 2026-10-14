"""Migración de un crm.db viejo (SQLite) a la base de destino."""
import json, os, shutil, sqlite3, tempfile, unittest

from crm.config import Settings
from crm.db import open_store
from crm.migrate import run
from tests.helpers import jpeg_url


class MigrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "origen.db"); c = sqlite3.connect(self.src)
        c.executescript("""CREATE TABLE ordenes(id TEXT PRIMARY KEY, seq INTEGER NOT NULL, creada TEXT, cliente TEXT, tel TEXT, estado TEXT, imagenes TEXT DEFAULT '[]', firma TEXT, historial TEXT);
        CREATE TABLE config(k TEXT PRIMARY KEY, v TEXT); CREATE TABLE usuarios(nombre TEXT PRIMARY KEY, hash TEXT NOT NULL, rol TEXT NOT NULL, creado TEXT);""")
        for i in (1, 2, 5):
            c.execute("INSERT INTO ordenes VALUES(?,?,?,?,?,?,?,?,?)", (f"o{i}", i, "2026-02-01T10:00:00Z", f"Cliente {i}", "1155", "Recibido", json.dumps([jpeg_url()]), jpeg_url(), json.dumps([{"f": "x", "t": "Orden creada", "u": "admin"}])))
        c.execute("INSERT INTO usuarios VALUES('admin','pbkdf2$200000$aa$bb','admin','2026-01-01')")
        c.execute("INSERT INTO config VALUES('taller','Mi Taller')"); c.execute("INSERT INTO config VALUES('pin','1234')"); c.commit(); c.close()
        self.settings = Settings(data_dir=self.tmp, database_url="sqlite:///" + os.path.join(self.tmp, "destino.db"))

    def test_copia_todo_y_es_idempotente(self):
        self.assertEqual(run(self.settings, self.src), 0)
        d = open_store(self.settings.database_url); o = d.orders_all()
        self.assertEqual([x["seq"] for x in o], [5, 2, 1])
        self.assertTrue(o[0]["imagenes"][0].startswith("/media/o5/") and os.path.isfile(self.tmp + o[0]["imagenes"][0]))  # fotos a archivos
        self.assertEqual(o[0]["historial"][0]["u"], "admin")
        self.assertEqual(d.user_get("admin")["hash"], "pbkdf2$200000$aa$bb")           # contraseña conservada tal cual
        self.assertEqual(d.config_all(), {"taller": "Mi Taller"})                       # sin el PIN viejo
        self.assertEqual(d.next_seq(1), [6])
        self.assertEqual(run(self.settings, self.src), 1)                               # segunda vez: se niega a duplicar

    def test_rechaza_origen_invalido_o_igual_al_destino(self):
        self.assertEqual(run(self.settings, os.path.join(self.tmp, "noexiste.db")), 1)
        same = Settings(data_dir=self.tmp, database_url="sqlite:///" + self.src)
        self.assertEqual(run(same, self.src), 1)


if __name__ == "__main__": unittest.main()
