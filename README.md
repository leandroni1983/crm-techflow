# CRM Técnico

Órdenes de servicio para un taller de reparaciones: ingreso con checklist, fotos y firma; presupuestos y avisos por
WhatsApp; comprobantes de ingreso y de entrega en PDF con QR; garantía; panel de estadísticas (dashboard) con
gráficos y exportación a Excel; lista de órdenes compacta (una línea por orden que se despliega al tocarla);
tipo de falla y tipo de equipo con listas que el administrador edita desde Configuración; **portal de seguimiento
para el cliente** por link privado; **inventario de repuestos** con alerta de reposición; **papelera recuperable** y
respaldo descargable; usuarios con roles; app instalable (PWA) y funcionamiento sin conexión con la base.

## Inicio rápido (Docker)

```bash
cp .env.example .env            # editá DATABASE_URL, POSTGRES_PASSWORD, DATA_PATH, PUID/PGID, ADMIN_PASSWORD
sudo mkdir -p /srv/crm/data
docker volume create crm_pgdata
docker compose up -d
docker compose exec crm python -m crm check-db      # debe decir "Motor: PostgreSQL"
```
Abrí `http://IP-DEL-SERVER:8000`. Más detalle (base en la nube, migrar tu `crm.db`, Cloudflare, actualizar): [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).

## Desarrollo

```bash
make run        # servidor local con SQLite en ./data (http://localhost:8000)
make test       # 49 pruebas unitarias y de API (solo necesita Python)
make lint       # revisa errores reales del código (ruff)
make e2e        # prueba de navegador con Playwright (funciona en Windows, Linux y macOS)
make help       # todos los comandos
```
Sin Docker ni PostgreSQL alcanza con Python 3.10+. Para usar PostgreSQL: `pip install -r requirements.txt` y `DATABASE_URL=postgresql://...`.
El proyecto usa [GitHub Actions](.github/workflows/ci.yml): en cada push corre el lint, las 49 pruebas y la prueba de navegador.

## Estructura

```
crm-tecnico/
├── crm/                      el programa (paquete de Python)
│   ├── config.py             configuración leída del entorno (un solo objeto Settings)
│   ├── cli.py, __main__.py   comandos: serve, check-db, list-users, reset-password, backup, restore, migrate-sqlite, version
│   ├── app.py                arma las piezas (base, medios, servicio, límite de logins)
│   ├── api/                  capa HTTP: rutas, sesión, archivos estáticos (sin lógica de negocio)
│   ├── orders.py             casos de uso de órdenes (guardar, borrar)
│   ├── service.py            datos con y sin conexión: cola de pendientes y sincronización
│   ├── resumen.py            agregados del panel de estadísticas (los pide /api/resumen)
│   ├── seg.py                portal de seguimiento: token firmado por orden
│   ├── backup.py             respaldo y restauración (config + usuarios + órdenes)
│   ├── db/                   modelos, migraciones numeradas y motores (SQLite / PostgreSQL)
│   ├── media.py, pdf.py, qr.py, security.py, bootstrap.py, migrate.py, log.py
│   └── web/                  lo que ve el navegador
│       ├── templates/        index.html, login.html, seguimiento.html
│       ├── static/js/        módulos ES: util, db, comun, cat, orden, lista, config, panel, modo, app
│       ├── static/{css,img}/
│       └── sw.js, manifest.webmanifest
├── tests/                    pruebas unitarias, de API y de navegador (e2e/)
├── docs/                     ARQUITECTURA.md, DESPLIEGUE.md
├── Dockerfile, docker-compose.yml, .env.example
├── Makefile, pyproject.toml, requirements*.txt
└── CHANGELOG.md
```

## Comandos útiles

| Qué | Comando |
|---|---|
| Verificar base y archivos | `docker compose exec crm python -m crm check-db` |
| Ver usuarios | `docker compose exec crm python -m crm list-users` |
| Restablecer una contraseña | `docker compose exec crm python -m crm reset-password admin 'NuevaClave123'` |
| Pasar un `crm.db` viejo a PostgreSQL | `docker compose run --rm -v /ruta/crm.db:/origen/crm.db:ro crm python -m crm migrate-sqlite /origen/crm.db` |
| Descargar un respaldo | `docker compose exec crm python -m crm backup` |
| Restaurar un respaldo (no borra nada) | `docker compose exec crm python -m crm restore data/respaldo-2026-01-01.json` |
| Ver logs | `docker compose logs -f crm` |
