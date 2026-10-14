# Cambios

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
