"""Fotos y firmas: se guardan como archivos en DATA_DIR/media/<orden>/ (la base solo guarda la ruta)."""
import base64, hashlib, os, re

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(DATA_DIR, "media")
MEDIA_RE = re.compile(r"^/media/([\w-]{1,60})/([0-9a-f]{20}\.jpg)$")


def _safe(s): return re.sub(r"[^\w-]", "_", str(s))[:60]


def save_media(oid, val):
    """dataURL JPEG -> archivo en media/<orden>/ ; devuelve la URL (si ya es una URL la deja igual)."""
    if not isinstance(val, str) or not val.startswith("data:"): return val if isinstance(val, str) else ""
    try: b = base64.b64decode(val.split(",", 1)[1])
    except Exception: return ""
    if b[:2] != b"\xff\xd8": return ""
    d = os.path.join(MEDIA, _safe(oid)); os.makedirs(d, exist_ok=True)
    name = hashlib.sha1(b).hexdigest()[:20] + ".jpg"
    p = os.path.join(d, name)
    if not os.path.exists(p):
        with open(p, "wb") as f: f.write(b)
    return f"/media/{_safe(oid)}/{name}"


def clean_media(oid, keep):
    d = os.path.join(MEDIA, _safe(oid))
    if not os.path.isdir(d): return
    keep = {u.rsplit("/", 1)[-1] for u in keep if isinstance(u, str) and u.startswith("/media/")}
    for n in os.listdir(d):
        if n not in keep:
            try: os.remove(os.path.join(d, n))
            except OSError: pass
