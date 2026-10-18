"""Migraciones numeradas del esquema. Para cambiar la base: agregar una función mN y sumarla a MIGRATIONS (nunca editar una vieja)."""
from .models import JSON_COLS, TEXT_COLS, id_cliente, id_equipo, now_iso

def _cols(t, table):
    if t.pg: return {r["column_name"] for r in t.all("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))}
    return {r["name"] for r in t.all(f"PRAGMA table_info({table})")}


def m1_esquema(t):
    t.run("CREATE TABLE IF NOT EXISTS ordenes(id TEXT PRIMARY KEY, seq BIGINT NOT NULL, creada TEXT)")
    t.run("CREATE TABLE IF NOT EXISTS config(k TEXT PRIMARY KEY, v TEXT)")
    t.run("CREATE TABLE IF NOT EXISTS usuarios(nombre TEXT PRIMARY KEY, hash TEXT NOT NULL, rol TEXT NOT NULL, creado TEXT)")
    t.run("CREATE TABLE IF NOT EXISTS sesiones(token TEXT PRIMARY KEY, usuario TEXT NOT NULL, expira DOUBLE PRECISION NOT NULL)")
    have = _cols(t, "ordenes")
    for col in ["actualizada"] + TEXT_COLS + JSON_COLS:
        if col not in have: t.run(f"ALTER TABLE ordenes ADD COLUMN {col} TEXT")
    t.run("CREATE INDEX IF NOT EXISTS ordenes_seq_idx ON ordenes(seq)")


def m2_secuencia(t):
    if t.pg:
        t.run("CREATE SEQUENCE IF NOT EXISTS orden_seq")
        t.run("SELECT setval('orden_seq', COALESCE((SELECT MAX(seq) FROM ordenes),1), (SELECT COUNT(*)>0 FROM ordenes))")
    else:
        t.run("CREATE TABLE IF NOT EXISTS contadores(nombre TEXT PRIMARY KEY, valor BIGINT NOT NULL)")
        t.run("INSERT INTO contadores(nombre, valor) VALUES('orden', COALESCE((SELECT MAX(seq) FROM ordenes),0)) ON CONFLICT(nombre) DO NOTHING")


def m3_clientes_y_fallas(t):
    """Clientes y equipos como registros propios, y el catálogo de fallas por orden."""
    t.run("CREATE TABLE IF NOT EXISTS clientes(id TEXT PRIMARY KEY, nombre TEXT, tel TEXT, direccion TEXT, email TEXT, notas TEXT, creado TEXT, actualizado TEXT)")
    t.run("CREATE TABLE IF NOT EXISTS equipos(id TEXT PRIMARY KEY, cliente_id TEXT, tipo TEXT, marca TEXT, serie TEXT, color TEXT, notas TEXT, creado TEXT, actualizado TEXT)")
    have = _cols(t, "ordenes")
    for col in ("cliente_id", "equipo_id", "fallas"):
        if col not in have: t.run(f"ALTER TABLE ordenes ADD COLUMN {col} TEXT")
    t.run("CREATE INDEX IF NOT EXISTS ordenes_cliente_idx ON ordenes(cliente_id)")
    t.run("CREATE INDEX IF NOT EXISTS ordenes_equipo_idx ON ordenes(equipo_id)")
    t.run("CREATE INDEX IF NOT EXISTS equipos_cliente_idx ON equipos(cliente_id)")


def backfill_clientes(t):
    """Arma los clientes y equipos a partir de las órdenes que todavía no tienen cliente_id (idempotente).
    Mismo teléfono (o mismo nombre si no hay teléfono) = mismo cliente. Mismo número de serie (o mismo tipo y marca si no hay serie) = mismo equipo."""
    rows = t.all("SELECT id, cliente, tel, direccion, equipo, marca, serie, color, creada FROM ordenes WHERE COALESCE(cliente_id,'') = '' ORDER BY creada, seq")
    cli, eqs, asign, ahora = {}, {}, [], now_iso()
    for r in rows:
        cid = id_cliente(r["tel"], r["cliente"])
        if not cid: continue
        prev = cli.get(cid)
        cli[cid] = {"id": cid, "nombre": r["cliente"] or "", "tel": r["tel"] or "", "direccion": r["direccion"] or "", "creado": prev["creado"] if prev else (r["creada"] or ahora)}
        eid = id_equipo(cid, r["serie"], r["equipo"], r["marca"])
        if eid:
            p = eqs.get(eid)
            eqs[eid] = {"id": eid, "cliente_id": cid, "tipo": r["equipo"] or "", "marca": r["marca"] or "", "serie": r["serie"] or "", "color": r["color"] or "", "creado": p["creado"] if p else (r["creada"] or ahora)}
        asign.append((cid, eid, r["id"]))
    for c in cli.values():
        t.run("INSERT INTO clientes(id,nombre,tel,direccion,email,notas,creado,actualizado) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING", (c["id"], c["nombre"], c["tel"], c["direccion"], "", "", c["creado"], ahora))
    for e in eqs.values():
        t.run("INSERT INTO equipos(id,cliente_id,tipo,marca,serie,color,notas,creado,actualizado) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING", (e["id"], e["cliente_id"], e["tipo"], e["marca"], e["serie"], e["color"], "", e["creado"], ahora))
    for cid, eid, oid in asign: t.run("UPDATE ordenes SET cliente_id=?, equipo_id=? WHERE id=?", (cid, eid, oid))
    return len(asign)


def m4_agrupar_ordenes_existentes(t): backfill_clientes(t)


MIGRATIONS = [(1, "esquema base", m1_esquema), (2, "secuencia de números de orden", m2_secuencia),
              (3, "clientes, equipos y fallas", m3_clientes_y_fallas), (4, "agrupar las órdenes existentes por cliente y equipo", m4_agrupar_ordenes_existentes)]
LATEST = MIGRATIONS[-1][0]
