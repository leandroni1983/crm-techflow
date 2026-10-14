"""Contenedor de dependencias de la aplicación (se crea una vez y se pasa a quien lo necesite)."""
import os

from .bootstrap import ensure_admin, migrate_legacy_media
from .config import Settings
from .db import open_store
from .media import MediaStore
from .security import LoginLimiter
from .service import DataService


class App:
    def __init__(self, settings: Settings, store=None):
        os.makedirs(settings.data_dir, exist_ok=True)
        self.settings = settings
        self.store = store or open_store(settings.database_url)
        self.media = MediaStore(settings.media_dir)
        self.service = DataService(self.store, settings.data_dir, settings.database_url, probe_secs=settings.sync_secs)
        self.limiter = LoginLimiter()

    def start(self):
        """Conecta con la base, migra el esquema, asegura el administrador y carga la copia en memoria."""
        self.service.start()
        ensure_admin(self)
        migrate_legacy_media(self)
