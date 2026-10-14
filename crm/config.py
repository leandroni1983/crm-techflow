"""Configuración: se lee UNA vez del entorno y se pasa como objeto (nada de variables globales sueltas)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    data_dir: str
    database_url: str
    host: str = "127.0.0.1"
    port: int = 8000
    cookie_secure: bool = False
    trust_proxy: bool = False
    require_postgres: bool = False
    session_days: int = 7
    max_body: int = 80 * 1024 * 1024
    sync_secs: int = 10
    open_browser: bool = True
    drop_privileges: bool = False
    puid: int = 10001
    pgid: int = 10001
    admin_user: str = "admin"
    admin_password: str = ""

    @property
    def media_dir(self): return os.path.join(self.data_dir, "media")

    @property
    def comprobantes_dir(self): return os.path.join(self.data_dir, "comprobantes")

    @property
    def es_postgres(self): return self.database_url.startswith(("postgresql://", "postgres://"))

    @classmethod
    def from_env(cls, env=None):
        e = os.environ if env is None else env
        data_dir = os.path.abspath(e.get("DATA_DIR") or os.path.join(os.getcwd(), "data"))
        puid = int(e.get("PUID") or 10001)
        return cls(
            data_dir=data_dir,
            database_url=e.get("DATABASE_URL") or "sqlite:///" + os.path.join(data_dir, "crm.db"),
            host=e.get("HOST", "127.0.0.1"), port=int(e.get("PORT") or 8000),
            cookie_secure=e.get("COOKIE_SECURE") == "1", trust_proxy=e.get("TRUST_PROXY") == "1",
            require_postgres=e.get("REQUIRE_POSTGRES") == "1", sync_secs=int(e.get("SYNC_SECS") or 10), open_browser=e.get("OPEN_BROWSER", "1") != "0",
            drop_privileges=e.get("DROP_PRIVILEGES") == "1", puid=puid, pgid=int(e.get("PGID") or puid),
            admin_user=(e.get("ADMIN_USER") or "admin").strip().lower() or "admin", admin_password=e.get("ADMIN_PASSWORD") or "",
        )
