# Cambios

## 1.4.0
- **Papelera recuperable**: borrar una orden ya no la pierde; la manda a la papelera desde donde el administrador puede **recuperarla** o **borrarla para siempre** (con sus fotos). El borrado definitivo, la papelera y el respaldo son solo del administrador. Migración de esquema v5: columna `borrada`.
- **Respaldo descargable** desde **⚙️ Configuración → Respaldo** (JSON con configuración, usuarios y órdenes, papelera incluida) y también por consola: `python -m crm backup` y `python -m crm restore archivo.json`.
- **Portal de seguimiento para el cliente**: cada orden tiene un **link privado firmado** (HMAC) que se abre **sin usuario ni contraseña** y muestra el estado, las fechas, el saldo y la línea de tiempo (nunca las notas internas ni la clave del equipo). El botón **🔗 Seguimiento** copia el link para pegar en WhatsApp y la variable `{seguimiento}` está disponible en los mensajes. La dirección pública se configura desde ⚙️.
- **Aviso de equipos sin retirar**: botón **📦 Sin retirar** con la lista de equipos listos esperando retiro, los días que llevan y aviso por WhatsApp (queda anotado en el historial).
- **Inventario de repuestos**: catálogo (nombre, stock, mínimo y costo) que edita el administrador; la **disponibilidad se calcula** restando lo usado en las órdenes activas, así nunca queda desfasada, y avisa cuando hay que **reponer**. Al cargar una orden se elige el repuesto del inventario y completa descripción, cantidad y costo.
- **Datos prolijos**: nuevo campo **Tipo de equipo** con lista fija (y sugerencia automática al escribir el equipo) y **renombre de categorías** de fallas/equipos que actualiza también las órdenes viejas. La estadística "Equipos más frecuentes" ahora usa el tipo, no el texto libre. Migración v4: columna `equipo_tipo`.
- **Seguridad**: cabeceras `Content-Security-Policy` estricta y `Permissions-Policy`; validación de **Origin** (contra CSRF); **límite de tasa** por IP en las rutas sensibles; cookie **`__Host-crm_sid`** bajo HTTPS; aviso cuando la contraseña del administrador es débil.
- **Rendimiento y arquitectura**: el panel pide los **agregados ya calculados** al servidor (`/api/resumen`) y, sin conexión, los calcula local con las mismas reglas; `/api/data` y `/api/resumen` usan **ETag** (304 sin cuerpo); la lista se dibuja **de a 50** con botón "ver más"; `app.js` se dividió en **módulos ES** (`util`, `db`, `comun`, `cat`, `orden`, `lista`, `config`, `panel`, `modo`, `app`) sin empaquetador ni CDN.
- **Automatización**: **GitHub Actions** (lint `ruff` + pruebas en 3.10/3.12 + e2e con Playwright), comandos `make lint/test/e2e`, y **healthcheck** del contenedor Docker.
- **Pagos y caja**: la orden guarda **pagos parciales** (fecha, monto, medio y nota) además de la seña, y el saldo se calcula solo. Botón **💰 Caja** con el **arqueo del día** (cobros y totales por medio).
- **Ficha del cliente**: desde la orden, el botón **👤 Cliente** muestra el historial, la **deuda pendiente** y los equipos de ese cliente.
- **Inventario con movimientos (kardex)**: cada repuesto lleva su **historial de entradas y salidas**; una entrada suma stock, una salida lo descuenta, con nota y fecha.
- **Aprobación del presupuesto por el cliente**: desde su **link de seguimiento**, el cliente puede **aprobar o rechazar** el presupuesto; cambia el estado de la orden y queda registrado quién y cuándo (no pisa una decisión previa).
- **Prioridad y vencimientos**: la orden se puede marcar con **prioridad**; la lista se ordena por prioridad o por deuda y avisa de los equipos **sin retirar** por más días.
- **Permisos finos**: opción para **ocultar los importes** a los técnicos y permiso (solo administrador por defecto) para el **borrado definitivo**.
- **Tareas y recordatorios**: cada orden admite **tareas** con fecha límite opcional, que se marcan como hechas; accesos rápidos **Con tareas** y **Tareas vencidas** en la lista, y quedan anotadas en el historial.
- **Adjuntos**: se pueden adjuntar a la orden **documentos** (PDF, Word/Excel, ZIP, imágenes y texto, hasta 15 MB); se sirven con su tipo real, los que no son imagen se descargan y nunca se ejecutan desde el navegador.
- **Equipos por cliente**: en la ficha del cliente los equipos se agrupan y hay un botón para **repetir la orden con el mismo equipo**.
- **Auditoría global**: bitácora de **quién hizo qué y cuándo** (ingresos, órdenes, configuración, usuarios, respaldo, bajas definitivas y la decisión del cliente en el portal); la ve solo el administrador y guarda los últimos 2000 movimientos.
- **Tiempo real**: si otro usuario cambia algo, la lista del resto **se actualiza sola** (sondeo liviano de un "sello" del servidor cada 5 s), sin pisar lo que estás editando.
- Migraciones de esquema **v6** (pagos y aprobación), **v7** (tareas y adjuntos) y **v8** (auditoría): se aplican solas al iniciar, sin perder datos.
- Pruebas: **54** unitarias/API y **122** comprobaciones de navegador.

## 1.3.0
- El **panel de estadísticas (dashboard)** pasa a ser la pantalla principal al iniciar sesión: indicadores del período (ingresadas, entregadas, facturado, costo de repuestos, ganancia, ticket promedio, sin retirar) y gráficos sin librerías externas (evolución mensual, facturado vs. ganancia, distribución por estado, por técnico, equipos y fallas más comunes).
- Desde el panel se puede **crear una orden nueva** y, justo debajo, la sección **Órdenes** muestra **todas** las órdenes con búsqueda por palabra y filtro por estado/técnico.
- La lista de órdenes es **compacta (una línea por orden)**: al tocar una línea se **despliega el detalle completo** (acordeón, una a la vez) y el botón **Editar** abre el formulario entero.
- Filtro por período de las estadísticas: un mes, últimos 3/6/12 meses, este año o todo el historial.
- Exportar a Excel (CSV) las órdenes del período desde el panel, además del export completo de siempre.
- Front-end renovado: encabezado, tarjetas, botones, chips, formularios y lista de órdenes tipo acordeón, con modo oscuro y mejor comportamiento en celular.
- App instalable (PWA): el botón **📲 Instalar** aparece también en iPhone/iPad con los pasos para agregarla a la pantalla de inicio (en Android/Chrome usa el aviso nativo del navegador).
- Nuevo campo **Tipo de falla** en la orden: lista fija (No enciende, No carga/batería, Líquido/mojado, Pantalla rota, etc.) con **sugerencia automática** al escribir la falla reportada. La estadística **"Fallas más comunes"** ahora cuenta esas categorías —antes contaba palabras sueltas del diagnóstico, como "debe" o "reemplazar"— y las órdenes viejas figuran como *Sin clasificar*. El tipo de falla también se exporta en el Excel (CSV).
- Migración de esquema v3: nueva columna `falla_tipo` (se agrega sola al iniciar, sin perder datos).
- La **lista de tipos de falla** se puede editar desde **⚙️ Configuración → Tipos de falla** (uno por línea) y **solo el administrador** puede cambiarla: el técnico no ve esa sección y el servidor rechaza (403) el intento. Afecta al desplegable de la orden y a la estadística de "Fallas más comunes". Si una falla ya usada se cambia de nombre, las órdenes anteriores siguen con el nombre viejo y se ven como una categoría aparte.

## 1.2.0
- Proyecto reorganizado como paquete de Python (`crm/`) con capas separadas: configuración, HTTP, casos de uso, servicio de datos, base de datos, web.
- Línea de comandos unificada: `python -m crm [serve|check-db|list-users|reset-password|migrate-sqlite|version]` (reemplaza `server.py` y `migrar_sqlite_a_postgres.py`).
- Archivos del navegador movidos a `/static/...`; las páginas a `crm/web/templates/`.
- Pruebas incluidas en el repositorio (36 unitarias/API + prueba de navegador).
- La marca de última modificación de una orden pasa a milisegundos (detección de conflictos al sincronizar).
- `/health` informa la versión. `OPEN_BROWSER=0` evita que se abra el navegador al arrancar en local.
- Por defecto, sin Docker, los datos van a `./data` (antes, junto al código).

## 1.1.0
- PostgreSQL con `DATABASE_URL`, migraciones numeradas, modo sin conexión con cola que se borra al sincronizar,
  números de orden reservados, login con usuarios y roles, PWA, fotos como archivos, comprobante de entrega, técnico asignado.
