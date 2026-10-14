"""Archivos por orden: fotos, firmas y adjuntos (documentos).

Se guardan como archivos en <data>/media/<orden>/ y la base solo guarda la ruta (/media/<orden>/<hash>.<ext>).
Para los adjuntos se acepta un conjunto fijo de tipos seguros: nunca se sirve HTML/SVG subido por un usuario
(el navegador no debe ejecutar nada que venga de un archivo adjunto).
"""
import base64, hashlib, os, re, shutil

# Tipos permitidos para adjuntos: extensión -> tipo MIME con el que se sirve.
ALLOWED = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    "pdf": "application/pdf", "txt": "text/plain", "csv": "text/csv", "zip": "application/zip",
    "doc": "application/msword", "xls": "application/vnd.ms-excel",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
# tipo MIME (el que manda el navegador en el dataURL) -> extensión con la que se guarda.
MIME2EXT = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp",
    "application/pdf": "pdf", "text/plain": "txt", "text/csv": "csv", "application/zip": "zip",
    "application/msword": "doc", "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}
MAX_ADJ = 15 * 1024 * 1024   # 15 MB por adjunto


class MediaStore:
    RE = re.compile(r"^/media/([\w-]{1,60})/([0-9a-f]{20}\.[a-z0-9]{1,5})$")

    def __init__(self, root):
        self.root = root

    @staticmethod
    def _safe(oid): return re.sub(r"[^\w-]", "_", str(oid))[:60]

    def _write(self, oid, b, ext):
        """Escribe el archivo (si no existe) y devuelve su URL. Nunca se sale de <root>/<orden>/."""
        d = os.path.join(self.root, self._safe(oid)); os.makedirs(d, exist_ok=True)
        name = hashlib.sha1(b).hexdigest()[:20] + "." + ext
        p = os.path.join(d, name)
        if not os.path.exists(p):
            with open(p, "wb") as f: f.write(b)
        return f"/media/{self._safe(oid)}/{name}", len(b)

    def save(self, oid, val):
        """dataURL JPEG -> archivo; devuelve la URL. Si `val` ya es una URL la deja igual; lo inválido devuelve ''."""
        if not isinstance(val, str) or not val.startswith("data:"): return val if isinstance(val, str) else ""
        try: b = base64.b64decode(val.split(",", 1)[1])
        except Exception: return ""
        if b[:2] != b"\xff\xd8": return ""
        return self._write(oid, b, "jpg")[0]

    def save_adjunto(self, oid, item):
        """Guarda un adjunto. `item` = {n: nombre, data: dataURL} (nuevo) o {n, u, t, s} (ya guardado).
        Devuelve {n, u, t, s} o None si el tipo/tamaño no son válidos."""
        if not isinstance(item, dict): return None
        nombre = str(item.get("n") or "archivo")[:120]
        url = item.get("u") or ""
        if url:   # ya guardado en un alta anterior: se conserva tal cual (validando la ruta)
            return {"n": nombre, "u": url, "t": self.tipo(url), "s": item.get("s") or 0} if self.path(url) else None
        data = item.get("data") or ""
        if not str(data).startswith("data:"): return None
        try:
            head, b64 = str(data).split(",", 1)
            mime = head[5:].split(";")[0].strip().lower()
            b = base64.b64decode(b64)
        except Exception: return None
        if not b or len(b) > MAX_ADJ: return None
        ext = MIME2EXT.get(mime) or os.path.splitext(nombre)[1].lstrip(".").lower()
        if ext not in ALLOWED: return None
        u, n = self._write(oid, b, ext)
        return {"n": nombre, "u": u, "t": ALLOWED[ext], "s": n}

    @staticmethod
    def tipo(url):
        """Tipo MIME con el que se sirve un archivo, según su extensión."""
        return ALLOWED.get(os.path.splitext(url or "")[1].lstrip(".").lower(), "application/octet-stream")

    @staticmethod
    def inline(url):
        """Las imágenes y los PDF se ven en el navegador; el resto se descarga (evita ejecutar contenido subido)."""
        t = MediaStore.tipo(url)
        return t.startswith("image/") or t == "application/pdf"

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
