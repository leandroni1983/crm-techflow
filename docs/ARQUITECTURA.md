# Arquitectura

## Capas

```
 navegador (crm/web)  ──HTTP──▶  crm/api  ──▶  crm/orders.py  ──▶  crm/service.py  ──▶  crm/db  ──▶  PostgreSQL / SQLite
   HTML + JS + PWA               rutas y        casos de uso        con/sin conexión     modelos,       (DATABASE_URL)
                                 sesión         (reglas)            cola + sincroniza    migraciones
                                                       └──▶ crm/media.py (fotos y firmas como archivos)
                                                       └──▶ crm/pdf.py, crm/qr.py (comprobantes)
```

Regla de dependencia: cada capa solo conoce a la de la derecha. `api` no habla con la base: llama a `orders` o a `service`.
`db` no sabe nada de HTTP. Todo se arma una sola vez en `app.py` (inyección de dependencias): no hay variables globales
de configuración, por eso las pruebas pueden levantar una aplicación completa en un directorio temporal.

| Módulo | Responsabilidad |
|---|---|
| `config.py` | Lee el entorno una vez y entrega un `Settings` inmutable. |
| `api/handler.py` | Interpreta el pedido HTTP, valida la sesión, responde. Sin reglas de negocio. |
| `orders.py` | Reglas de una orden: fotos a archivos, historial sellado por el servidor, número decidido por el servidor. |
| `service.py` | `DataService`: lee/escribe en la base; sin conexión usa la cola y la copia en memoria; sincroniza al volver. |
| `db/models.py` | Columnas de la orden y su normalización. |
| `db/migrations.py` | Migraciones numeradas. |
| `db/store.py` | `SqliteStore` y `PgStore`: el mismo SQL, con las diferencias aisladas. |
| `media.py` | Fotos/firmas como JPEG en `data/media/<orden>/` (nombre = hash del contenido). |
| `security.py` | PBKDF2, hash de tokens, bloqueo de intentos fallidos. |
| `bootstrap.py` | Primer administrador, migración de fotos viejas, bajada de privilegios en Docker. |

## Decisiones

- **PostgreSQL por `DATABASE_URL`** (local o en la nube, el mismo código). SQLite queda para desarrollo y pruebas.
- **Datos separados del programa.** La base vive en su contenedor/servicio y los archivos en `DATA_PATH`; actualizar la imagen no los toca.
- **Fotos y firmas como archivos**, no dentro de la base: la lista de órdenes sigue liviana. La base guarda solo la ruta.
- **Historial a prueba de falsificación:** el cliente solo puede agregar entradas; fecha y usuario los pone el servidor.
- **Una sola dependencia externa:** el driver `psycopg`. PDF, QR y servidor HTTP están hechos con la biblioteca estándar.
- **Sesiones con cookie `HttpOnly`**; los tokens se guardan hasheados. `Secure` solo cuando la conexión llegó por HTTPS.

## Funcionamiento sin conexión con la base

1. Con conexión, todo va a la base. El servidor mantiene en memoria una copia de lo último leído.
2. Si la base no responde, los cambios de órdenes y de configuración se guardan en `outbox.db` (SQLite diminuto) y se siguen mostrando desde la copia en memoria.
3. Un hilo prueba la conexión cada `SYNC_SECS`. Al volver, envía la cola **en orden**; al vaciarse, **borra `outbox.db`**.
4. Los números de orden salen de un bloque de 10 reservado por adelantado en la secuencia de la base (`reserva.json`), así que el número que se le da al cliente sin conexión es el definitivo.
5. Si la misma orden cambió en la base mientras tanto, gana el cambio más reciente y queda una nota en el historial.
6. Un cambio que falla 5 veces se aparta en la cola (no se pierde) y se avisa en pantalla y en el log.

Límites: sin conexión no se pueden crear usuarios ni cambiar contraseñas; si el servidor se reinicia mientras la base no responde, no arranca.

## Cómo extender

**Agregar un campo a la orden**
1. Sumarlo a `TEXT_COLS` en `crm/db/models.py` (o a `JSON_COLS` si es una lista).
2. Crear una migración nueva en `crm/db/migrations.py` (`m3_...`) que haga `ALTER TABLE ordenes ADD COLUMN ...` y agregarla a `MIGRATIONS`. **No edites migraciones viejas.**
3. Agregarlo al formulario en `crm/web/templates/index.html` y al mapa `CAMPOS` de `crm/web/static/js/app.js`.
4. Si debe salir en los comprobantes, sumarlo a `filasComp` o `filasEntrega` en `app.js`.
5. Una prueba en `tests/` y `make test`.

**Agregar un endpoint:** una rama en `_get`/`_post`/`_delete` de `api/handler.py` que llame a un caso de uso (en `orders.py` o un módulo nuevo), nunca a la base directamente.

**Cambiar de versión:** subir `__version__` en `crm/__init__.py`, anotar en `CHANGELOG.md`, `make build push`.

## Pruebas

| Nivel | Dónde | Qué cubre |
|---|---|---|
| Unitarias | `tests/test_db.py`, `test_security_cli.py`, `test_qr_pdf.py` | migraciones, base vieja, historial, QR legible, PDF, hashes, comandos |
| Servicio | `tests/test_service.py` | cola sin conexión, sincronización, conflictos, números reservados, reinicio |
| API | `tests/test_api.py` | sesión, roles, medios, historial sellado, estáticos seguros, cookies, bloqueo, modo sin conexión |
| Migración | `tests/test_migrate.py` | pasaje de un `crm.db` viejo |
| Navegador | `tests/e2e/` | el flujo completo en Chromium (formulario, firma, PDF, etiqueta, PWA, sin conexión) |

No cubierto automáticamente: ejecución real contra PostgreSQL y construcción de la imagen Docker (se verifican con `check-db` en el primer arranque).
