#!/usr/bin/env bash
# Prueba de punta a punta en un navegador real (Playwright). Arranca su propio servidor con SQLite temporal.
# Requisitos (una vez):  npm install -g playwright && npx playwright install chromium
set -euo pipefail
cd "$(dirname "$0")/../.."
TMP=$(mktemp -d); PORT=${PORT:-8765}; ASSETS="$TMP/assets"; mkdir -p "$ASSETS"
trap 'kill ${SRV:-0} 2>/dev/null || true; rm -rf "$TMP"' EXIT

# imágenes de prueba (sin Pillow): un PNG de 300x120 y un JPEG
python3 - "$ASSETS" <<'PY'
import base64, struct, sys, zlib
from tests.helpers import TINY_JPEG
d = sys.argv[1]
def chunk(t, b): return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
w, h = 300, 120
raw = b"".join(b"\x00" + bytes((29, 78, 216)) * w for _ in range(h))
open(d + "/logo.png", "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
open(d + "/foto.jpg", "wb").write(base64.b64decode(TINY_JPEG))
PY

export DATA_DIR="$TMP/data" PORT ADMIN_PASSWORD=Secreta123 SYNC_SECS=2 OPEN_BROWSER=0 CRM_SIM_OFFLINE_FILE="$TMP/sim_off"
unset DATABASE_URL REQUIRE_POSTGRES
python3 -m crm > "$TMP/server.log" 2>&1 & SRV=$!
for i in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.25; done

export BASE_URL="http://127.0.0.1:$PORT" SIM_FILE="$TMP/sim_off" ASSETS_DIR="$ASSETS"
NODE_PATH="${NODE_PATH:-$(npm root -g)}" node tests/e2e/e2e.js || { echo "--- log del servidor ---"; tail -30 "$TMP/server.log"; exit 1; }
grep -q Traceback "$TMP/server.log" && { echo "El servidor registró errores:"; grep -A5 Traceback "$TMP/server.log"; exit 1; } || true
