"""Clientes y equipos: agrupación de lo existente, alta junto con la orden, edición, borrado y modo sin conexión."""
import os, shutil, tempfile, unittest

from crm.db import SqliteStore, id_cliente, id_equipo, tel_key
from crm.db.migrations import m1_esquema, m2_secuencia
from tests.helpers import Env, hist, order


class IdentidadTest(unittest.TestCase):
    def test_el_mismo_telefono_en_cualquier_formato_es_el_mismo_cliente(self):
        a, b, c = id_cliente("011 5555-1234", "x"), id_cliente("1155551234", "y"), id_cliente("+54 9 11 5555 1234", "z")
        self.assertEqual(a, b); self.assertEqual(b, c); self.assertEqual(tel_key("0115555-1234"), "1155551234")
        self.assertNotEqual(a, id_cliente("1155551235", "x"))
        self.assertEqual(id_cliente("", "Ana Pérez"), id_cliente("", " ana pérez "))   # sin teléfono: por nombre
        self.assertEqual(id_cliente("", ""), "")

    def test_equipo_por_serie_o_por_tipo_y_marca(self):
        c = id_cliente("1155551234", "")
        self.assertEqual(id_equipo(c, "SN1", "Notebook", "HP"), id_equipo(c, "sn1", "Otro", "Otra"))   # la serie manda
        self.assertEqual(id_equipo(c, "", "Notebook", "HP"), id_equipo(c, "", "notebook", "hp"))
        self.assertNotEqual(id_equipo(c, "", "Notebook", "HP"), id_equipo(c, "", "Notebook", "Dell"))
        self.assertEqual(id_equipo(c, "", "", ""), "")


class StoreClientesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.tmp, True)
        self.st = SqliteStore(os.path.join(self.tmp, "c.db"))

    def test_actualizar_desde_la_version_anterior_agrupa_las_ordenes_existentes(self):
        # base como la dejaba la versión 1.3: esquema v2 y órdenes sin cliente_id
        with self.st.tx() as t:
            m1_esquema(t); m2_secuencia(t)
            t.run("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, aplicada TEXT, descripcion TEXT)")
            for v in (1, 2): t.run("INSERT INTO schema_version VALUES(?,?,?)", (v, "x", "x"))
            filas = [("o1", 1, "2026-01-01T10:00:00Z", "Ana", "011 5555-1234", "Notebook", "HP", "SN1"),
                     ("o2", 2, "2026-02-01T10:00:00Z", "Ana Pérez", "1155551234", "Notebook", "HP", "sn1"),      # mismo cliente, mismo equipo
                     ("o3", 3, "2026-03-01T10:00:00Z", "Ana Pérez", "+54 9 11 5555 1234", "Impresora", "Epson", ""),  # mismo cliente, otro equipo
                     ("o4", 4, "2026-03-05T10:00:00Z", "Luis", "1166667777", "PC", "Armada", ""),
                     ("o5", 5, "2026-03-06T10:00:00Z", "Sin teléfono", "", "Monitor", "LG", ""),
                     ("o6", 6, "2026-03-07T10:00:00Z", "", "", "", "", "")]                                          # no se puede identificar
            for oid, seq, cre, cli, tel, eq, ma, se in filas:
                t.run("INSERT INTO ordenes(id,seq,creada,cliente,tel,equipo,marca,serie) VALUES(?,?,?,?,?,?,?,?)", (oid, seq, cre, cli, tel, eq, ma, se))
        self.assertEqual(self.st.migrate(), 4)
        cli = {c["id"]: c for c in self.st.clientes_all()}; eq = self.st.equipos_all(); o = {x["id"]: x for x in self.st.orders_all()}
        self.assertEqual(len(cli), 3)                                                       # Ana, Luis y "Sin teléfono"
        ana = id_cliente("1155551234", "")
        self.assertEqual(cli[ana]["nombre"], "Ana Pérez")                                   # queda el dato de la orden más reciente
        self.assertEqual({o["o1"]["cliente_id"], o["o2"]["cliente_id"], o["o3"]["cliente_id"]}, {ana})
        self.assertEqual(o["o1"]["equipo_id"], o["o2"]["equipo_id"]); self.assertNotEqual(o["o1"]["equipo_id"], o["o3"]["equipo_id"])
        self.assertEqual(len([e for e in eq if e["cliente_id"] == ana]), 2)
        self.assertEqual((o["o6"]["cliente_id"], o["o6"]["equipo_id"]), ("", ""))
        self.assertEqual(self.st.migrate(), 4)                                              # idempotente
        self.assertEqual(len(self.st.clientes_all()), 3)

    def test_la_orden_crea_cliente_y_equipo_pero_no_pisa_los_existentes(self):
        self.st.migrate(); cid = id_cliente("1155551234", ""); eid = id_equipo(cid, "SN1", "Notebook", "HP")
        c0 = {"id": cid, "nombre": "Ana", "tel": "1155551234", "direccion": ""}; e0 = {"id": eid, "cliente_id": cid, "tipo": "Notebook", "marca": "HP", "serie": "SN1"}
        self.st.order_save(order("a", cliente_id=cid, equipo_id=eid), [], cliente=c0, equipo=e0)
        self.st.cliente_save({**c0, "nombre": "Ana Editada", "notas": "VIP"})
        self.st.order_save(order("b", cliente_id=cid, equipo_id=eid), [], cliente={**c0, "nombre": "OTRO"}, equipo={**e0, "marca": "OTRA"})
        self.assertEqual(self.st.clientes_all()[0]["nombre"], "Ana Editada")                # no se pisó
        self.assertEqual(self.st.equipos_all()[0]["marca"], "HP")

    def test_editar_cliente_y_equipo_actualiza_sus_ordenes(self):
        self.st.migrate(); cid = id_cliente("1155551234", ""); eid = id_equipo(cid, "SN1", "Notebook", "HP")
        c0 = {"id": cid, "nombre": "Ana", "tel": "1155551234", "direccion": "Calle 1"}; e0 = {"id": eid, "cliente_id": cid, "tipo": "Notebook", "marca": "HP", "serie": "SN1"}
        self.st.order_save(order("a", cliente_id=cid, equipo_id=eid, tel="1155551234"), [], cliente=c0, equipo=e0)
        self.st.cliente_save({**c0, "tel": "1100000000", "nombre": "Ana María"}); self.st.equipo_save({**e0, "marca": "Lenovo", "color": "Negro"})
        o = self.st.orders_all()[0]
        self.assertEqual((o["cliente"], o["tel"], o["marca"], o["color"]), ("Ana María", "1100000000", "Lenovo", "Negro"))   # los mensajes usan el dato nuevo

    def test_no_se_borra_lo_que_tiene_ordenes(self):
        self.st.migrate(); cid = id_cliente("1155551234", ""); eid = id_equipo(cid, "SN1", "Notebook", "HP")
        self.st.order_save(order("a", cliente_id=cid, equipo_id=eid), [], cliente={"id": cid, "nombre": "Ana"}, equipo={"id": eid, "cliente_id": cid, "tipo": "N"})
        with self.assertRaises(ValueError): self.st.cliente_del(cid)
        with self.assertRaises(ValueError): self.st.equipo_del(eid)
        self.st.order_del("a"); self.st.equipo_del(eid); self.st.cliente_del(cid)
        self.assertEqual((self.st.clientes_all(), self.st.equipos_all()), ([], []))

    def test_bulk_load_agrupa_las_ordenes_cargadas(self):
        self.st.migrate()
        self.st.bulk_load([], {}, [{**order("x", seq=1, tel="1155551234", equipo="PC", serie="S1"), "seq": 1, "historial": []}])
        self.assertEqual(len(self.st.clientes_all()), 1); self.assertTrue(self.st.orders_all()[0]["cliente_id"])


class ServicioClientesTest(unittest.TestCase):
    def setUp(self):
        self.env = Env(serve=False); self.addCleanup(self.env.close); self.svc, self.st = self.env.app.service, self.env.store

    def test_cliente_y_equipo_nuevos_cargados_sin_conexion_llegan_a_la_base(self):
        cid = id_cliente("1155551234", ""); eid = id_equipo(cid, "SN9", "Notebook", "HP")
        self.env.go_offline()
        self.svc.order_save(order("a", cliente_id=cid, equipo_id=eid), [hist("creada")], cliente={"id": cid, "nombre": "Ana", "tel": "1155551234"},
                            equipo={"id": eid, "cliente_id": cid, "tipo": "Notebook", "marca": "HP", "serie": "SN9"})
        self.assertEqual([c["nombre"] for c in self.svc.clientes()], ["Ana"]); self.assertEqual(len(self.svc.equipos()), 1)   # ya se ven en pantalla
        self.svc.cliente_save({"id": cid, "nombre": "Ana María", "tel": "1100000000"})                                          # y se pueden editar
        self.assertEqual(self.svc.orders()[0]["cliente"], "Ana María")
        self.assertEqual(self.svc.status()["pendientes"], 2)
        with self.assertRaises(Exception): self.svc.cliente_del(cid)                                                            # borrar requiere conexión
        self.env.go_online(); self.svc.online = True; self.svc.wake.set(); self.svc.sync_once()
        self.assertEqual(self.svc.pend, 0)
        c = self.st.clientes_all()[0]; self.assertEqual((c["nombre"], c["tel"]), ("Ana María", "1100000000"))
        self.assertEqual(self.st.orders_all()[0]["tel"], "1100000000"); self.assertEqual(len(self.st.equipos_all()), 1)


if __name__ == "__main__": unittest.main()
