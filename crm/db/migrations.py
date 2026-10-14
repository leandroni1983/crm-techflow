"""Migraciones numeradas del esquema. Para cambiar la base: agregar una función mN y sumarla a MIGRATIONS (nunca editar una vieja)."""
from .models import JSON_COLS, TEXT_COLS

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


def m3_falla_tipo(t):
    """Agrega el tipo de falla (categoría) para la estadística de "Fallas más comunes"."""
    if "falla_tipo" not in _cols(t, "ordenes"): t.run("ALTER TABLE ordenes ADD COLUMN falla_tipo TEXT")


def m4_equipo_tipo(t):
    """Agrega el tipo de equipo (categoría) para la estadística de "Equipos más frecuentes"."""
    if "equipo_tipo" not in _cols(t, "ordenes"): t.run("ALTER TABLE ordenes ADD COLUMN equipo_tipo TEXT")


def m5_papelera(t):
    """Papelera: `borrada` guarda cuándo la orden se mandó a la papelera (vacío = orden activa).
    Borrar de verdad (DELETE y borrado de fotos) queda solo para purgar desde la papelera."""
    if "borrada" not in _cols(t, "ordenes"): t.run("ALTER TABLE ordenes ADD COLUMN borrada TEXT")


MIGRATIONS = [(1, "esquema base", m1_esquema), (2, "secuencia de números de orden", m2_secuencia),
              (3, "tipo de falla", m3_falla_tipo), (4, "tipo de equipo", m4_equipo_tipo),
              (5, "papelera", m5_papelera)]
LATEST = MIGRATIONS[-1][0]
