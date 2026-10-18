"""Fotos y firmas: se guardan como archivos JPEG en <data>/media/<orden>/ y la base solo guarda la ruta (/media/<orden>/<hash>.jpg)."""
import base64, hashlib, os, re, shutil


class MediaStore:
    RE = re.compile(r"^/media/([\w-]{1,60})/([0-9a-f]{20}\.jpg)$")

    def __init__(self, root):
        self.root = root

    @staticmethod
    def _safe(oid): return re.sub(r"[^\w-]", "_", str(oid))[:60]

    def save(self, oid, val):
        """dataURL JPEG -> archivo; devuelve la URL. Si `val` ya es una URL la deja igual; lo inválido devuelve ''."""
        if not isinstance(val, str) or not val.startswith("data:"): return val if isinstance(val, str) else ""
        try: b = base64.b64decode(val.split(",", 1)[1])
        except Exception: return ""
        if b[:2] != b"\xff\xd8": return ""
        d = os.path.join(self.root, self._safe(oid)); os.makedirs(d, exist_ok=True)
        name = hashlib.sha1(b).hexdigest()[:20] + ".jpg"
        p = os.path.join(d, name)
        if not os.path.exists(p):
            with open(p, "wb") as f: f.write(b)
        return f"/media/{self._safe(oid)}/{name}"

    def path(self, url):
        """Ruta en disco de una URL /media/... (None si la URL no es válida: evita salirse de la carpeta)."""
        m = self.RE.match(url or "")
        return os.path.join(self.root, m.group(1), m.group(2)) if m else None

    def read(self, url):
        p = self.path(url)
        if not p or not os.path.isfile(p): return None
        with open(p, "rb") as f: return f.read()

    def clean(self, oid, keep):
        """Borra los archivos de la orden que ya no están referenciados."""
        d = os.path.join(self.root, self._safe(oid))
        if not os.path.isdir(d): return
        keep = {u.rsplit("/", 1)[-1] for u in keep if isinstance(u, str) and u.startswith("/media/")}
        for n in os.listdir(d):
            if n not in keep:
                try: os.remove(os.path.join(d, n))
                except OSError: pass

    def delete_order(self, oid):
        shutil.rmtree(os.path.join(self.root, self._safe(oid)), ignore_errors=True)
