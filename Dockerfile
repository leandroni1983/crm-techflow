FROM python:3.12-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="crm-tecnico" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8000 \
    DROP_PRIVILEGES=1

WORKDIR /app

# 1) dependencias (capa que se reutiliza mientras no cambie requirements.txt)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2) el código: todo el paquete `crm` (incluye la parte web)
COPY crm ./crm
RUN mkdir -p /data

VOLUME /data
EXPOSE 8000

# /health responde 200 mientras la app viva (aunque la base esté caída: sigue funcionando en modo local)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=3)"

# Arranca como root solo para ajustar permisos de /data y luego baja a PUID/PGID (ver crm/bootstrap.py)
CMD ["python", "-m", "crm"]
