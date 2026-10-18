"""Servicio de datos con funcionamiento con y sin conexión.

- Con conexión: todo va directo a la base (PostgreSQL / SQLite de pruebas).
- Sin conexión: los cambios de órdenes y configuración se guardan en una COLA (outbox.db, un SQLite diminuto) y se
  siguen mostrando desde una copia en MEMORIA de lo último leído. Al volver la conexión, la cola se envía en orden y,
  cuando queda vacía, el archivo outbox.db se BORRA: no queda ninguna copia de los datos en disco.
- Los números de orden se toman de un bloque reservado de la secuencia (reserva.json, unos pocos bytes), así los
  números que se entregan al cliente sin conexión son los definitivos.
"""
import json, os, sqlite3, threading, time, traceback
from .db import DBUnavailable, norm_order, now_iso, now_ms, redact, tel_key
from .log import log


class NeedsDB(Exception):
    """Acción que requiere conexión con la base (usuarios, contraseñas)."""


class NoSeq(Exception):
    """Sin conexión y sin números de orden reservados."""


class DataService:
    BLOCK = 10        # cantidad de números de orden que se reservan por adelantado
    MIN_BLOCK = 3     # se repone cuando quedan menos de estos

    def __init__(self, remote, data_dir, url="", probe_secs=10):
        self.remote, self.dir, self.url, self.probe = remote, data_dir, url, probe_secs
        self.outbox_path = os.path.join(data_dir, "outbox.db")
        self.reserva_path = os.path.join(data_dir, "reserva.json")
        self.lock = threading.RLock()
        self.online, self.last_error = True, ""
        self.c_orders, self.c_users, self.c_cfg, self.c_sess = {}, {}, {}, {}
        self.c_cli, self.c_eq = {}, {}
        self.sess_push, self.sess_drop = [], []
        self.wake = threading.Event()
        self.pend, self.errores = self._count_outbox()
        self.block = self._load_block()

    # ------------------------------------------------------------ estado
    @property
    def motor(self): return self.remote.nombre

    def status(self):
        return {"online": self.online, "pendientes": self.pend, "errores": self.errores, "reservados": len(self.block),
                "motor": self.motor, "error": self.last_error if not self.online else ""}

    def _set_offline(self, msg):
        with self.lock:
            if self.online: log(f"⚠ Sin conexión con la base ({msg}). Trabajando en modo local; los cambios quedan en cola.")
            self.online, self.last_error = False, msg
        self.wake.set()

    def _remote(self, fn):
        """Ejecuta fn() contra la base. Devuelve (True, resultado) o (False, None) si no hay conexión."""
        if not self.online: return False, None
        try: return True, fn()
        except DBUnavailable as e:
            self._set_offline(str(e)); return False, None

    def _use_cache(self):
        with self.lock: return (not self.online) or self.pend > 0

    # ------------------------------------------------------------ arranque
    def start(self, tries=30):
        """Conecta, migra y carga la copia en memoria. Reintenta unos segundos (la base puede estar arrancando)."""
        last = None
        for i in range(tries):
            try:
                v = self.remote.migrate(); log(f"Base de datos lista: {self.motor} · {redact(self.url)} · esquema v{v}")
                break
            except DBUnavailable as e:
                last = e; log(f"Esperando la base de datos ({i + 1}/{tries}): {e}"); time.sleep(2)
        else:
            raise SystemExit(f"No se pudo conectar con la base de datos ({redact(self.url)}): {last}\n"
                             "Revisá DATABASE_URL, que el servicio de la base esté encendido y las reglas de red/firewall.")
        self.refresh_cache(); self.top_up_block()

    def start_thread(self):
        threading.Thread(target=self._loop, daemon=True, name="sync").start()

    def refresh_cache(self):
        ok, data = self._remote(lambda: (self.remote.orders_all(), self.remote.users_full(), self.remote.config_all(), self.remote.clientes_all(), self.remote.equipos_all()))
        if ok:
            with self.lock:
                self.c_orders = {o["id"]: o for o in data[0]}; self.c_users = {u["nombre"]: u for u in data[1]}; self.c_cfg = data[2]
                self.c_cli = {c["id"]: c for c in data[3]}; self.c_eq = {e["id"]: e for e in data[4]}

    # ------------------------------------------------------------ lecturas
    def orders(self):
        if not self._use_cache():
            ok, rows = self._remote(self.remote.orders_all)
            if ok:
                with self.lock: self.c_orders = {o["id"]: o for o in rows}
                return rows
        with self.lock: return sorted(self.c_orders.values(), key=lambda o: -o["seq"])

    def clientes(self):
        if not self._use_cache():
            ok, rows = self._remote(self.remote.clientes_all)
            if ok:
                with self.lock: self.c_cli = {c["id"]: c for c in rows}
                return rows
        with self.lock: return sorted(self.c_cli.values(), key=lambda c: (c.get("nombre") or "").lower())

    def equipos(self):
        if not self._use_cache():
            ok, rows = self._remote(self.remote.equipos_all)
            if ok:
                with self.lock: self.c_eq = {e["id"]: e for e in rows}
                return rows
        with self.lock: return sorted(self.c_eq.values(), key=lambda e: (e.get("tipo") or "").lower())

    def config(self):
        if not self._use_cache():
            ok, c = self._remote(self.remote.config_all)
            if ok:
                with self.lock: self.c_cfg = c
                return c
        with self.lock: return dict(self.c_cfg)

    def users_list(self):
        ok, rows = self._remote(self.remote.users_full)
        if ok:
            with self.lock: self.c_users = {u["nombre"]: u for u in rows}
        with self.lock: return [{"nombre": u["nombre"], "rol": u["rol"], "creado": u.get("creado")} for u in sorted(self.c_users.values(), key=lambda u: u["nombre"])]

    def usernames(self): return [u["nombre"] for u in self.users_list()]

    def user_get(self, nombre):
        ok, u = self._remote(lambda: self.remote.user_get(nombre))
        if ok:
            with self.lock:
                if u: self.c_users[nombre] = u
                else: self.c_users.pop(nombre, None)
            return u
        with self.lock: return self.c_users.get(nombre)

    # ------------------------------------------------------------ usuarios (requieren conexión)
    def _need(self, fn):
        ok, r = self._remote(fn)
        if not ok: raise NeedsDB()
        return r

    def user_add(self, nombre, hash_, rol): self._need(lambda: self.remote.user_add(nombre, hash_, rol)); self.refresh_cache()
    def user_set_hash(self, nombre, hash_): self._need(lambda: self.remote.user_set_hash(nombre, hash_)); self.refresh_cache()
    def user_del(self, nombre): self._need(lambda: self.remote.user_del(nombre)); self.refresh_cache()
    def users_count(self): return self._need(self.remote.users_count)
    def sess_del_others(self, usuario, th): self._need(lambda: self.remote.sess_del_others(usuario, th))

    # ------------------------------------------------------------ sesiones
    def sess_add(self, th, usuario, expira):
        ok, _ = self._remote(lambda: self.remote.sess_add(th, usuario, expira))
        with self.lock:
            u = self.c_users.get(usuario) or {}
            self.c_sess[th] = {"nombre": usuario, "rol": u.get("rol", "tecnico"), "expira": expira}
            if not ok: self.sess_push.append((th, usuario, expira))

    def session_user(self, th, days):
        """Usuario de la sesión (None si no existe o venció). Renueva la sesión si le queda poco."""
        if not th: return None
        ok, r = self._remote(lambda: self.remote.sess_get(th))
        if ok and r:
            with self.lock: self.c_sess[th] = r
            if r["expira"] - time.time() < (days - 1) * 86400:
                self._remote(lambda: self.remote.sess_touch(th, time.time() + days * 86400))
        else:
            with self.lock:
                local = self.c_sess.get(th)
                pending = any(p[0] == th for p in self.sess_push)
            r = local if (not ok or pending) else None
        if not r or r["expira"] < time.time(): return None
        return {"nombre": r["nombre"], "rol": r["rol"]}

    def sess_del(self, th):
        with self.lock: self.c_sess.pop(th, None)
        ok, _ = self._remote(lambda: self.remote.sess_del(th))
        if not ok:
            with self.lock: self.sess_drop.append(th)

    # ------------------------------------------------------------ escrituras con cola
    def order_save(self, o, hist_new, cliente=None, equipo=None):
        """Las órdenes nuevas toman SIEMPRE el próximo número del bloque reservado (así la numeración es continua
        con o sin conexión). Si el bloque está vacío y hay conexión, la base asigna el número."""
        o = norm_order(o); seq = None
        with self.lock:
            if o["id"] not in self.c_orders and self.block:
                seq = self.block.pop(0); self._save_block()
        if not self._use_cache():
            try: ok, res = self._remote(lambda: self.remote.order_save(o, hist_new, seq=seq, cliente=cliente, equipo=equipo))
            except Exception:
                with self.lock:
                    if seq is not None: self.block.insert(0, seq); self._save_block()
                raise
            if ok:
                with self.lock:
                    self.c_orders[o["id"]] = {**o, "seq": res["seq"], "historial": res["historial"], "actualizada": res["actualizada"]}
                    self._cache_cli_eq(cliente, equipo)
                self.top_up_block()
                return res
        return self._enqueue_order(o, hist_new, seq, cliente, equipo)

    def _cache_cli_eq(self, cliente, equipo):
        """Los registros nuevos entran a la copia en memoria; si ya existían, se respetan (la orden no los pisa)."""
        if cliente: self.c_cli.setdefault(cliente["id"], {"email": "", "notas": "", "creado": now_iso(), "actualizado": now_iso(), **cliente})
        if equipo: self.c_eq.setdefault(equipo["id"], {"notas": "", "creado": now_iso(), "actualizado": now_iso(), **equipo})

    def _enqueue_order(self, o, hist_new, seq, cliente=None, equipo=None):
        with self.lock:
            ex = self.c_orders.get(o["id"])
            if ex: seq = ex["seq"]
            elif seq is None: raise NoSeq()
            base_mod = None if self._has_pending(o["id"]) else ((ex or {}).get("actualizada") if ex else None)
            hist = list(ex["historial"] if ex else []) + list(hist_new)
            mod = now_ms()
            self._outbox_add("orden_save", o["id"], {"o": {**o, "seq": seq}, "hist_new": hist_new, "base_mod": base_mod, "seq": None if ex else seq, "cliente": cliente, "equipo": equipo})
            self.c_orders[o["id"]] = {**o, "seq": seq, "historial": hist, "actualizada": mod}
            self._cache_cli_eq(cliente, equipo)
        self.wake.set()
        return {"seq": seq, "historial": hist, "actualizada": mod}

    # ---- clientes y equipos: se editan con o sin conexión (van a la misma cola); borrarlos requiere conexión
    def cliente_por_tel(self, tel):
        """El cliente que hoy tiene ese teléfono (el id no sirve: sale del teléfono original y puede haberse corregido después)."""
        k = tel_key(tel)
        if not k: return None
        with self.lock: return next((c for c in self.c_cli.values() if tel_key(c.get("tel")) == k), None)

    def equipo_por_clave(self, cid, serie, tipo, marca):
        """El equipo de ese cliente con el mismo número de serie o, si no tiene serie, el mismo tipo y marca."""
        s, tm = str(serie or "").strip().lower(), (str(tipo or "").strip().lower(), str(marca or "").strip().lower())
        with self.lock:
            for e in self.c_eq.values():
                if e["cliente_id"] != cid: continue
                es = str(e.get("serie") or "").strip().lower()
                if s and es == s: return e
                if not s and not es and tm != ("", "") and (str(e.get("tipo") or "").strip().lower(), str(e.get("marca") or "").strip().lower()) == tm: return e
        return None

    def get_cliente(self, cid):
        with self.lock: return self.c_cli.get(cid)

    def get_equipo(self, eid):
        with self.lock: return self.c_eq.get(eid)

    def cliente_save(self, c):
        c = {**c}
        if not self._use_cache():
            ok, saved = self._remote(lambda: self.remote.cliente_save(c))
            if ok:
                with self.lock: self._aplicar_cliente(saved)
                return saved
        with self.lock:
            prev = self.c_cli.get(c["id"], {}); saved = {"email": "", "notas": "", "creado": now_iso(), **prev, **c, "actualizado": now_iso()}
            self._aplicar_cliente(saved); self._outbox_add("cliente_save", "c:" + c["id"], c)
        self.wake.set(); return saved

    def _aplicar_cliente(self, c):
        self.c_cli[c["id"]] = c
        for o in self.c_orders.values():
            if o.get("cliente_id") == c["id"]: o.update(cliente=c.get("nombre", ""), tel=c.get("tel", ""), direccion=c.get("direccion", ""))

    def equipo_save(self, e):
        e = {**e}
        if not self._use_cache():
            ok, saved = self._remote(lambda: self.remote.equipo_save(e))
            if ok:
                with self.lock: self._aplicar_equipo(saved)
                return saved
        with self.lock:
            prev = self.c_eq.get(e["id"], {}); saved = {"notas": "", "creado": now_iso(), **prev, **e, "actualizado": now_iso()}
            self._aplicar_equipo(saved); self._outbox_add("equipo_save", "e:" + e["id"], e)
        self.wake.set(); return saved

    def _aplicar_equipo(self, e):
        self.c_eq[e["id"]] = e
        for o in self.c_orders.values():
            if o.get("equipo_id") == e["id"]: o.update(equipo=e.get("tipo", ""), marca=e.get("marca", ""), serie=e.get("serie", ""), color=e.get("color", ""))

    def cliente_del(self, cid):
        self._need(lambda: self.remote.cliente_del(cid))
        with self.lock:
            self.c_cli.pop(cid, None)
            for k in [k for k, e in self.c_eq.items() if e.get("cliente_id") == cid]: self.c_eq.pop(k, None)

    def equipo_del(self, eid):
        self._need(lambda: self.remote.equipo_del(eid))
        with self.lock: self.c_eq.pop(eid, None)

    def order_del(self, oid):
        with self.lock: self.c_orders.pop(oid, None)
        if not self._use_cache():
            ok, _ = self._remote(lambda: self.remote.order_del(oid))
            if ok: return
        with self.lock: self._outbox_add("orden_del", oid, {"id": oid})
        self.wake.set()

    def config_set(self, d):
        if not self._use_cache():
            ok, _ = self._remote(lambda: self.remote.config_set(d))
            if ok:
                with self.lock: self.c_cfg.update({k: str(v) for k, v in d.items()})
                return
        with self.lock:
            self.c_cfg.update({k: str(v) for k, v in d.items()}); self._outbox_add("config", "", d)
        self.wake.set()

    # ------------------------------------------------------------ bloque de números de orden
    def _load_block(self):
        try:
            with open(self.reserva_path) as f: return [int(x) for x in json.load(f).get("block", [])]
        except Exception: return []

    def _save_block(self):
        try:
            if self.block:
                with open(self.reserva_path, "w") as f: json.dump({"block": self.block}, f)
            elif os.path.exists(self.reserva_path): os.remove(self.reserva_path)
        except OSError as e: log(f"No se pudo guardar la reserva de números: {e}")

    def top_up_block(self):
        with self.lock: falta = self.BLOCK - len(self.block) if len(self.block) < self.MIN_BLOCK else 0
        if falta <= 0 or not self.online: return
        ok, vals = self._remote(lambda: self.remote.next_seq(falta))
        if ok:
            with self.lock: self.block += vals; self._save_block()

    # ------------------------------------------------------------ cola (SQLite diminuto que se borra al vaciarse)
    def _ob(self):
        c = sqlite3.connect(self.outbox_path, timeout=30); c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE IF NOT EXISTS ops(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, oid TEXT, payload TEXT, estado TEXT DEFAULT 'pend', intentos INTEGER DEFAULT 0, error TEXT)")
        return c

    def _count_outbox(self):
        if not os.path.exists(self.outbox_path): return 0, 0
        c = self._ob()
        try: return (c.execute("SELECT COUNT(*) FROM ops WHERE estado='pend'").fetchone()[0], c.execute("SELECT COUNT(*) FROM ops WHERE estado='error'").fetchone()[0])
        finally: c.close()

    def _outbox_add(self, kind, oid, payload):
        with self.lock: self.pend += 1  # se cuenta ya mismo: así el estado nunca muestra "sin conexión" con 0 pendientes mientras se crea la cola
        try:
            c = self._ob()
            try:
                c.execute("INSERT INTO ops(ts, kind, oid, payload) VALUES(?,?,?,?)", (now_iso(), kind, oid, json.dumps(payload))); c.commit()
            finally: c.close()
        except Exception:
            with self.lock: self.pend -= 1
            raise

    def _has_pending(self, oid):
        if not os.path.exists(self.outbox_path): return False
        c = self._ob()
        try: return c.execute("SELECT 1 FROM ops WHERE estado='pend' AND oid=? LIMIT 1", (oid,)).fetchone() is not None
        finally: c.close()

    def _outbox_first(self):
        if not os.path.exists(self.outbox_path): return None
        c = self._ob()
        try:
            r = c.execute("SELECT * FROM ops WHERE estado='pend' ORDER BY id LIMIT 1").fetchone()
            return dict(r) if r else None
        finally: c.close()

    def _outbox_done(self, op_id):
        c = self._ob()
        try: c.execute("DELETE FROM ops WHERE id=?", (op_id,)); c.commit()
        finally: c.close()
        with self.lock: self.pend = max(0, self.pend - 1)

    def _outbox_fail(self, op_id, msg):
        c = self._ob()
        try:
            c.execute("UPDATE ops SET intentos=intentos+1, error=?, estado=CASE WHEN intentos+1>=5 THEN 'error' ELSE estado END WHERE id=?", (msg[:500], op_id)); c.commit()
            if c.execute("SELECT estado FROM ops WHERE id=?", (op_id,)).fetchone()["estado"] == "error":
                with self.lock: self.pend = max(0, self.pend - 1); self.errores += 1
                log(f"✖ Un cambio pendiente falló 5 veces y quedó apartado en {self.outbox_path}: {msg}")
        finally: c.close()

    def _outbox_cleanup(self):
        with self.lock:
            if self.pend == 0 and self.errores == 0:
                for p in (self.outbox_path, self.outbox_path + "-journal", self.outbox_path + "-wal", self.outbox_path + "-shm"):
                    try: os.remove(p)
                    except OSError: pass

    # ------------------------------------------------------------ sincronización
    def _loop(self):
        while True:
            self.wake.wait(self.probe); self.wake.clear()
            try: self.sync_once()
            except Exception: log("Error en la sincronización:\n" + traceback.format_exc())

    def sync_once(self):
        with self.lock: needs = (not self.online) or self.pend or self.sess_push or self.sess_drop or len(self.block) < self.MIN_BLOCK
        if not needs: return
        try: self.remote.ping()
        except DBUnavailable as e:
            self._set_offline(str(e)); return
        if not self.online:
            with self.lock: self.online, self.last_error = True, ""
            log("✔ Conexión con la base recuperada. Sincronizando…")
        self._push_sessions()
        if not self._replay(): return
        if self.pend == 0:
            self._outbox_cleanup(); self.refresh_cache()
        self.top_up_block()

    def _push_sessions(self):
        with self.lock: push, drop = list(self.sess_push), list(self.sess_drop)
        try:
            for th, u, ex in push: self.remote.sess_add(th, u, ex)
            for th in drop: self.remote.sess_del(th)
        except DBUnavailable as e: self._set_offline(str(e)); return
        with self.lock:
            self.sess_push = [p for p in self.sess_push if p not in push]; self.sess_drop = [d for d in self.sess_drop if d not in drop]

    def _replay(self):
        n = 0
        while True:
            op = self._outbox_first()
            if not op: break
            p = json.loads(op["payload"])
            try:
                if op["kind"] == "orden_save": self.remote.order_save(p["o"], p["hist_new"], seq=p.get("seq"), base_mod=p.get("base_mod"), cliente=p.get("cliente"), equipo=p.get("equipo"))
                elif op["kind"] == "cliente_save": self.remote.cliente_save(p)
                elif op["kind"] == "equipo_save": self.remote.equipo_save(p)
                elif op["kind"] == "orden_del": self.remote.order_del(p["id"])
                elif op["kind"] == "config": self.remote.config_set(p)
            except DBUnavailable as e:
                self._set_offline(str(e)); return False
            except Exception as e:
                log(f"Error al enviar un cambio pendiente: {e}"); self._outbox_fail(op["id"], str(e)); continue
            self._outbox_done(op["id"]); n += 1
        if n: log(f"✔ {n} cambio(s) pendiente(s) enviados a la base. La cola quedó vacía.")
        return True
