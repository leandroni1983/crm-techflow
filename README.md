# CRM Técnico

Sistema de gestión para servicios técnicos de reparación de equipos (celulares, electrónica, etc.). Gestiona órdenes de trabajo, presupuestos, historiales, garantías y comunicación con clientes.

---

## 📦 Instalación con Docker (Recomendado)

### 1. Primera instalación con base local (dos contenedores)

```bash
cp .env.example .env          # editá DATABASE_URL, POSTGRES_PASSWORD, DATA_PATH, PUID/PGID (corregí con `id`)
mkdir -p /srv/crm/data        # la carpeta de DATA_PATH
docker volume create crm_pgdata
docker compose up -d --build
docker compose run --rm crm python server.py --check-db      # verifica conexión, migraciones y escritura
```

Abrí `http://IP-DEL-SERVER:8000` e ingresá con `ADMIN_USER` / `ADMIN_PASSWORD`
*(si dejaste la contraseña vacía, se genera y sale en `docker compose logs crm`).*

### 2. Con la base en la nube

En `.env` poné la URL del proveedor con TLS (`...?sslmode=require`), definí `DATA_PATH` y levantá **solo el CRM** (sin el contenedor `db`):

```bash
docker compose up -d crm
docker compose run --rm crm python server.py --check-db
```

Si tu versión de Compose se queja del volumen `crm_pgdata` al usar la nube, comentá el bloque `volumes:` del final del compose.

**Recomendaciones:** región cercana (São Paulo), usuario propio con permisos solo sobre esa base, y restringir el acceso a la IP de tu servidor si el proveedor lo permite.

### 3. Pasar tu crm.db actual (SQLite) a PostgreSQL — una sola vez

Con la base de destino ya creada y el CRM detenido o sin uso:

```bash
docker compose run --rm -v /ruta/a/tu/crm.db:/origen/crm.db:ro crm python migrar_sqlite_a_postgres.py /origen/crm.db
```

Copia usuarios (con sus contraseñas), configuración y todas las órdenes con su número, historial y fotos, y compara las cantidades al final.
Si el destino ya tiene datos, no toca nada. Copiá también tu carpeta vieja `media/` y `comprobantes/` a `DATA_PATH`.

### 4. Si se corta internet (base en la nube)

- La app **sigue funcionando en tu red** con la última información leída (queda en memoria).
- Los cambios en órdenes y configuración se guardan en una cola (`outbox.db`, un SQLite diminuto) y la barra de arriba pasa a naranja con la cantidad pendiente.
- Al volver la conexión se envían solos, en orden, y **`outbox.db` se borra** al quedar vacía.
- Los números de orden salen de un bloque de 10 reservado por adelantado (`reserva.json`): son definitivos. Pueden quedar saltos en la numeración.
- Si se agotan sin conexión, las nuevas órdenes esperan; las existentes se pueden seguir editando.
- No se pueden crear usuarios ni cambiar contraseñas sin conexión.
- **Límite conocido:** si el servidor del CRM se reinicia **mientras** no hay conexión con la base, no puede iniciar (necesita leer usuarios). Los cambios ya encolados no se pierden.

### 5. Actualizar el CRM

```bash
docker compose up -d --build
```

Las migraciones numeradas se aplican solas. Si la base fuera más nueva que el programa, el CRM se niega a arrancar para no dañarla.

### 6. Qué respaldar

1. **La base:** `docker compose exec db pg_dump -U crm crm > crm.sql` (o el respaldo del proveedor en la nube).
2. **La carpeta `DATA_PATH` completa** (`media/` con fotos y firmas, `comprobantes/`).

---

## 🌐 Publicar con Cloudflare Tunnel / Zero Trust

1. Zero Trust > Networks > Tunnels > crear túnel (Docker) y copiar el token.
2. Public hostname `crm.tudominio.com` -> `HTTP` -> `crm:8000`.
3. `.env`: `TUNNEL_TOKEN=...`, `COOKIE_SECURE=1`, `TRUST_PROXY=1`.
4. Agregá al compose:

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN}
```

5. Recomendado: Access > Applications (Self-hosted) con política solo para tus correos.
6. **No abrí puertos en el router.** Si ya no entrás por IP local: `"127.0.0.1:${PORT:-8000}:8000"` en `ports`.

---

## 📱 App instalable (PWA)

Necesita HTTPS (la dirección de Cloudflare). Android/Chrome: botón **📲 Instalar**. iPhone/Safari: Compartir > Agregar a inicio.

Solo se guarda la carcasa; los datos y fotos siempre se piden al servidor.

---

## ⚠️ Si no te deja entrar

- `docker compose logs crm` dice si el usuario no existe o la contraseña es incorrecta.
- `ADMIN_USER` / `ADMIN_PASSWORD` solo se usan la primera vez (cuando no hay usuarios).
- `docker compose exec crm python server.py --list-users`
- `docker compose exec crm python server.py --reset-password admin 'NuevaClave123'`
- En el `.env`, contraseñas con `$`, `#` o espacios van entre comillas simples.

---

## 💻 Sin Docker (pruebas)

```bash
python server.py            # guarda en SQLite: ./crm.db
DATABASE_URL=postgresql://... python server.py
```

Para PostgreSQL hace falta `pip install -r requirements.txt`.

---

## 📦 Imagen en Docker Hub (build en una PC, ejecución en el server)

En la PC donde está el código:

```bash
docker login
docker compose build                    # arma leandrocode/crmtech:<CRM_VERSION>
docker compose push                     # la sube a Docker Hub
# si tu PC es ARM (Apple Silicon) y el server x86:
# docker buildx build --platform linux/amd64 -t leandrocode/crmtech:1.1 --push .
```

En el server solo necesitás `docker-compose.yml` y `.env` (no el código):

```bash
docker compose pull
docker compose up -d
```

Cada versión nueva lleva un número nuevo (`CRM_VERSION=1.2`). No reutilices una versión ya publicada: Docker no la vuelve a descargar. Revisá si tu repositorio de Docker Hub es público o privado.

---

## 🛠️ Estructura del proyecto

```
├── app.js              # Frontend: interfaz completa con gestión de órdenes, PDFs, QR, WhatsApp
├── server.py           # Backend: servidor Python con API REST, autenticación, migraciones PostgreSQL
├── docker-compose.yml  # Despliegue con CRM y base de datos PostgreSQL
├── README.md           # Esta documentación
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Para build personalizado
├── migrar_sqlite_a_postgres.py  # Migración de SQLite a PostgreSQL
├── .env.example      # Ejemplo de variables de entorno
├── .env              # Configuración local (nunca commitear)
└── media/            # Fotos, firmas y comprobantes (ruta configurada en DATA_PATH)
```

---

## 📸 Capturas

_(Añadir capturas de la interfaz aquí)_

---

## 🤝 Contribuir

1. Fork el repositorio
2. Crear una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit los cambios: `git commit -m 'Añadir nueva funcionalidad'`
4. Push a la rama: `git push origin feature/nueva-funcionalidad`
5. Abrir un Pull Request