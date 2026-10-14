"""Prueba de punta a punta en un navegador real (Playwright), sin depender de bash.

Arranca su propio servidor con SQLite temporal, genera imagenes de prueba y corre tests/e2e/e2e.js con Node.
Funciona igual en Windows, Linux y macOS.

Requisitos (una sola vez):
    npm install -g playwright && npx playwright install chromium

Uso:
    python tests/e2e/run.py            # puerto 8765
    python tests/e2e/run.py --port 8799
"""
import argparse, base64, os, struct, subprocess, sys, tempfile, time, urllib.error, urllib.request, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.helpers import TINY_JPEG  # noqa: E402


def imagenes(destino):
    """Un PNG de 300x120 y un JPEG, sin depender de Pillow."""
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    w, h = 300, 120
    raw = b"".join(b"\x00" + bytes((29, 78, 216)) * w for _ in range(h))
    (destino / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                       + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    (destino / "foto.jpg").write_bytes(base64.b64decode(TINY_JPEG))


def node_path():
    try:
        return subprocess.check_output(["npm", "root", "-g"], text=True, shell=(os.name == "nt")).strip()
    except Exception:
        return os.environ.get("NODE_PATH", "")


def esperar_servidor(base, segundos=40):
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.25)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT") or 8765))
    ap.add_argument("--keep", action="store_true", help="no borra el temporal al terminar (para depurar)")
    a = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="crm_e2e_"))
    assets = tmp / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    imagenes(assets)
    base = f"http://127.0.0.1:{a.port}"

    env = dict(os.environ)
    for k in ("DATABASE_URL", "REQUIRE_POSTGRES"):  # la prueba corre sin PostgreSQL
        env.pop(k, None)
    env.update(DATA_DIR=str(tmp / "data"), PORT=str(a.port), ADMIN_PASSWORD="Secreta123", SYNC_SECS="2",
               OPEN_BROWSER="0", CRM_SIM_OFFLINE_FILE=str(tmp / "sim_off"), BASE_URL=base, SIM_FILE=str(tmp / "sim_off"),
               ASSETS_DIR=str(assets), NODE_PATH=node_path())

    log = tmp / "server.log"
    print(f"TMP={tmp}\nservidor: {base}", flush=True)
    with open(log, "wb") as lf:
        srv = subprocess.Popen([sys.executable, "-m", "crm"], cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT)
    codigo = 1
    try:
        if not esperar_servidor(base):
            print("El servidor no respondio /health a tiempo.")
        else:
            codigo = subprocess.call(["node", str(ROOT / "tests" / "e2e" / "e2e.js")], cwd=ROOT, env=env)
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()

    texto = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    if codigo != 0:
        print("----- log del servidor (ultimas lineas) -----")
        print("\n".join(texto.splitlines()[-30:]))
    if "Traceback" in texto:
        print("El servidor registro errores:")
        print("\n".join(texto.splitlines()[-40:]))
        codigo = 1
    if a.keep:
        print(f"temporal conservado en {tmp}")
    else:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    raise SystemExit(codigo)


if __name__ == "__main__":
    main()
