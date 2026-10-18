"""Servicio de datos: modo sin conexión, cola que se borra al sincronizar, números reservados y conflictos."""
import os, time, unittest

from crm.service import NeedsDB, NoSeq
from tests.helpers import Env, hist, order, wait_until


class OfflineTest(unittest.TestCase):
    def setUp(self):
        self.env = Env(serve=False); self.addCleanup(self.env.close)
        self.svc, self.store = self.env.app.service, self.env.store
        self.outbox = self.env.path("outbox.db")

    def sync(self):
        self.env.go_online(); self.svc.wake.set(); self.svc.sync_once()

    def test_flujo_completo_sin_conexion(self):
        svc = self.svc
        self.assertEqual(svc.order_save(order("a"), [hist("creada")])["seq"], 1)  # online: la primera es la 1
        self.env.go_offline()
        r = svc.order_save(order("b", cliente="Offline"), [hist("creada")])
        self.assertEqual(r["seq"], 2)  # sin conexión continúa la numeración
        st = svc.status(); self.assertFalse(st["online"]); self.assertEqual(st["pendientes"], 1)
        self.assertTrue(os.path.exists(self.outbox)); self.assertLess(os.path.getsize(self.outbox), 64 * 1024)
        self.assertEqual({o["id"] for o in svc.orders()}, {"a", "b"})  # la lista se sigue viendo desde memoria
        r2 = svc.order_save(order("b", cliente="Editado"), [hist("estado")]); self.assertEqual((r2["seq"], len(r2["historial"])), (2, 2))
        self.assertEqual(svc.order_save(order("c"), [hist("creada")])["seq"], 3)
        svc.config_set({"taller": "Offline SA"}); self.assertEqual(svc.config()["taller"], "Offline SA")
        with self.assertRaises(NeedsDB): svc.user_add("x", "h", "tecnico")  # los usuarios requieren conexión
        self.assertEqual(svc.user_get("admin")["rol"], "admin")             # pero el login funciona
        svc.sess_add("th1", "admin", time.time() + 999); self.assertEqual(svc.session_user("th1", 7)["nombre"], "admin")
        self.assertEqual(svc.status()["pendientes"], 4)

        self.sync()  # vuelve la conexión
        self.assertEqual((svc.pend, svc.online), (0, True))
        self.assertFalse(os.path.exists(self.outbox), "la cola se borra al vaciarse")
        rows = {o["id"]: o for o in self.store.orders_all()}
        self.assertEqual({k: v["seq"] for k, v in rows.items()}, {"a": 1, "b": 2, "c": 3})
        self.assertEqual(rows["b"]["cliente"], "Editado")
        self.assertEqual([h["t"] for h in rows["b"]["historial"]], ["creada", "estado"])
        self.assertEqual(self.store.config_all()["taller"], "Offline SA")
        self.assertIsNotNone(self.store.sess_get("th1"))

    def test_conflicto_gana_el_cambio_mas_reciente_y_queda_anotado(self):
        self.svc.order_save(order("a"), [hist("creada")])
        self.env.go_offline()
        self.svc.order_save(order("a", cliente="Local"), [hist("edición local")])
        self.env.go_online(); self.store.order_save(order("a", cliente="Remoto"), [])  # otro la cambió en la base
        self.svc.online = True; self.svc.wake.set(); self.svc.sync_once()
        a = self.store.orders_all()[0]
        self.assertEqual(a["cliente"], "Local")
        self.assertTrue(any("Sincronización" in h["t"] for h in a["historial"]))

    def test_sin_numeros_reservados_no_hay_ordenes_nuevas_pero_si_ediciones(self):
        self.svc.order_save(order("a"), [])
        self.env.go_offline(); self.svc._set_offline("x"); self.svc.block = []
        with self.assertRaises(NoSeq): self.svc.order_save(order("zz"), [])
        self.assertEqual(self.svc.order_save(order("a", cliente="ok"), [])["seq"], 1)

    def test_la_cola_sobrevive_a_un_reinicio(self):
        from crm.service import DataService
        self.svc.order_save(order("a"), [hist("creada")])
        self.env.go_offline(); self.svc.order_save(order("a", cliente="Pendiente"), [])
        nuevo = DataService(self.store, self.env.tmp, "x", probe_secs=1)   # "proceso nuevo" sobre los mismos archivos
        self.assertEqual(nuevo.pend, 1)
        self.env.go_online(); nuevo.refresh_cache(); nuevo.sync_once()
        self.assertEqual((nuevo.pend, os.path.exists(self.outbox)), (0, False))
        self.assertEqual(self.store.orders_all()[0]["cliente"], "Pendiente")

    def test_hilo_de_sincronizacion_envia_solo(self):
        self.svc.start_thread(); self.svc.order_save(order("a"), [hist("creada")])
        self.env.go_offline(); self.svc.order_save(order("b"), [hist("creada")])
        self.assertEqual(self.svc.pend, 1); self.env.go_online()
        self.assertTrue(wait_until(lambda: self.svc.pend == 0 and not os.path.exists(self.outbox), 8))


if __name__ == "__main__": unittest.main()
