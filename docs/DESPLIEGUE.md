# Despliegue

## 1. Base local (dos contenedores)

```bash
cp .env.example .env            # DATABASE_URL (host "db"), POSTGRES_PASSWORD, DATA_PATH, PUID/PGID, ADMIN_PASSWORD
sudo mkdir -p /srv/crm/data
docker volume create crm_pgdata # una sola vez: protege la base de un `down -v`
docker compose up -d
docker compose exec crm python -m crm check-db
```
La clave de `DATABASE_URL` y la de `POSTGRES_PASSWORD` tienen que ser la misma. El host de la URL es **`db`**, no `localhost`.

## 2. Base en la nube

En `.env`: `DATABASE_URL=postgresql://usuario:clave@host:5432/base?sslmode=require` (símbolos de la clave codificados: `@`→`%40`, `#`→`%23`, `/`→`%2F`).
Levantá solo el CRM: `docker compose up -d crm`. Si Compose se queja del volumen `crm_pgdata`, comentá el bloque `volumes:` del final.
Elegí una región cercana, un usuario con permisos solo sobre esa base y, si el proveedor lo permite, limitá el acceso a la IP del servidor.
Con la base en la nube, un corte de internet activa el modo sin conexión (ver `ARQUITECTURA.md`).

## 3. Pasar tu `crm.db` (SQLite) a PostgreSQL — una sola vez

Con la base de destino creada y **antes** de abrir el CRM por primera vez:
```bash
docker compose run --rm -v /ruta/a/tu/crm.db:/origen/crm.db:ro crm python -m crm migrate-sqlite /origen/crm.db
```
Copia usuarios (con sus contraseñas), configuración, órdenes con su número, historial y fotos, y compara cantidades. Si el destino ya tiene datos no toca nada.
Copiá también tus carpetas `media/` y `comprobantes/` a `DATA_PATH`.

## 4. Imagen en Docker Hub

En la PC con el código: `make push` (arma `leandrocode/crmtech:<versión>` y la sube). Si tu PC es ARM y el server x86:
`docker buildx build --platform linux/amd64 -t leandrocode/crmtech:<versión> --push .`
En el server solo hacen falta `docker-compose.yml` y `.env`: `docker compose pull && docker compose up -d`.
Cada cambio de código lleva una versión nueva (`CRM_VERSION` en `.env`); nunca reutilices una ya publicada ni uses `latest`.

## 5. Actualizar

**Antes de pasar a 1.4 hacé un respaldo de la base** (`pg_dump`, ver más abajo): esa versión agrega tablas y columnas y agrupa tus órdenes existentes en clientes y equipos la primera vez que arranca. Es automático y se puede repetir sin riesgo, pero una base modificada no se vuelve a la versión anterior sin restaurar el respaldo.

```bash
# .env: CRM_VERSION=<nueva versión>
docker compose pull && docker compose up -d
```
Las migraciones se aplican solas. Si la base fuera más nueva que el programa, el CRM se niega a arrancar para no dañarla.

## 6. Qué respaldar

1. La base: `docker compose exec db pg_dump -U crm crm > crm.sql` (o el respaldo del proveedor en la nube).
2. La carpeta `DATA_PATH` completa (`media/` con fotos y firmas, `comprobantes/`).

## 7. Inspeccionar la base

```bash
docker compose exec db psql -U techflow -d techflow     # usá tu POSTGRES_USER / POSTGRES_DB
```
`\dt` lista tablas; `SELECT seq, cliente, estado FROM ordenes ORDER BY seq DESC LIMIT 10;`; `SELECT * FROM schema_version;`.
No publiques el puerto 5432 hacia afuera; para una herramienta gráfica usá un túnel SSH.

## 8. Cloudflare Tunnel / Zero Trust

1. Zero Trust > Networks > Tunnels > crear túnel (Docker) y copiar el token.
2. Public hostname `crm.tudominio.com` -> `HTTP` -> `crm:8000`.
3. `.env`: `TUNNEL_TOKEN=...`, `COOKIE_SECURE=1`, `TRUST_PROXY=1`.
4. Agregar al compose:
```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN}
```
5. Recomendado: Access > Applications (Self-hosted) con una política solo para tus correos.
6. No abras puertos en el router. Si ya no entrás por IP local: `"127.0.0.1:${PORT:-8000}:8000"` en `ports`.

La app instalable (PWA) necesita HTTPS: usá la dirección de Cloudflare. Android/Chrome: botón **📲 Instalar**; iPhone/Safari: Compartir > Agregar a inicio.

## 9. Si no te deja entrar o no conecta

- `docker compose logs crm` dice si el usuario no existe, si la contraseña es incorrecta o por qué no conecta con la base.
- `ADMIN_USER` / `ADMIN_PASSWORD` solo se usan la primera vez (cuando no hay usuarios).
- `docker compose exec crm python -m crm reset-password admin 'NuevaClave123'`
- `failed to resolve host 'db'`: el contenedor `db` no está corriendo (`docker compose ps`) o la URL usa `localhost` en vez de `db`.
- Contraseñas con `$`, `#` o espacios van entre comillas simples en el `.env`.
- `check-db` dice `Motor: SQLite`: el contenedor no recibió `DATABASE_URL` (revisá `docker compose config | grep DATABASE_URL`).
