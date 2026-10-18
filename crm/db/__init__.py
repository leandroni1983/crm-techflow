"""Capa de datos. Uso: store = open_store(DATABASE_URL); store.migrate()."""
from .models import CLIENTE_COLS, EQUIPO_COLS, JSON_COLS, ORDER_COLS, TEXT_COLS, id_cliente, id_equipo, norm_order, now_iso, now_ms, row_to_order, tel_key
from .migrations import LATEST, MIGRATIONS
from .store import DBUnavailable, PgStore, SqliteStore, Store, open_store, redact

__all__ = ["CLIENTE_COLS", "EQUIPO_COLS", "id_cliente", "id_equipo", "tel_key", "JSON_COLS", "ORDER_COLS", "TEXT_COLS", "norm_order", "now_iso", "now_ms", "row_to_order", "LATEST", "MIGRATIONS",
           "DBUnavailable", "PgStore", "SqliteStore", "Store", "open_store", "redact"]
