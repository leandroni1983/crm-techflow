FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8000 \
    DROP_PRIVILEGES=1

WORKDIR /app

# única dependencia externa: el driver de PostgreSQL (trae su propia libpq, no hace falta apt)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py store.py backend.py media.py pdfqr.py migrar_sqlite_a_postgres.py ./
COPY crm-tecnico.html login.html app.js db.js login.js styles.css manifest.webmanifest sw.js \
     icon-192.png icon-512.png apple-touch-icon.png favicon.png ./
RUN mkdir -p /data

VOLUME /data
EXPOSE 8000

# /health responde 200 mientras la app viva (aunque la base esté caída: la app sigue funcionando en modo local)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=3)"

# Arranca como root solo para ajustar permisos de /data y luego baja a PUID/PGID (ver server.py)
CMD ["python", "server.py"]
