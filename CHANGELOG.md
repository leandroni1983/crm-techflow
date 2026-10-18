# Cambios

## 1.5.0
- **Clientes y equipos como registros propios.** Se crean solos al cargar una orden (el mismo teléfono es el mismo cliente, aunque se escriba distinto;
  el mismo número de serie, el mismo equipo) y se editan desde la nueva pantalla **Clientes**: ficha con datos de contacto, equipos y la línea de
  tiempo de reparaciones de cada equipo, con aviso cuando un equipo vuelve dentro de la garantía. Cambiar el teléfono o el nombre de un cliente
  (o los datos de un equipo) los actualiza también en sus órdenes. Las órdenes ya cargadas se agrupan automáticamente al actualizar (migraciones 3 y 4).
- **Catálogo de fallas comunes** (editable en ⚙️). Cada orden marca las fallas que corresponden y el tablero cuenta la falla completa
  ("No enciende") en lugar de palabras sueltas. Las órdenes viejas se clasifican por coincidencia con el catálogo o quedan como "Sin clasificar".
- **El PDF del ingreso ya no incluye las fotos del equipo** (siguen guardadas en la orden). La firma sí se mantiene.
- Clientes y equipos también funcionan sin conexión con la base (van a la misma cola de pendientes).
- Corrección: el service worker no guardaba uno de los scripts y la app instalada no abría sin conexión.
- **Nota de la 1.5.0**: esta versión sustituye a la 1.4.0 que estaba publicada en el repositorio, que incluía papelera con
  respaldo descargable, portal de seguimiento para el cliente, pagos y caja, kardex, tareas, adjuntos, auditoría global,
  inventario de repuestos y sondeo de cambios en tiempo real. Esas funciones no forman parte de esta versión; siguen
  disponibles en el historial del repositorio.

## 1.3.0
- Interfaz rediseñada: tablero de indicadores del mes (facturado, ganancia, ticket promedio, margen, activas, entregadas, ingresadas,
  tiempo medio, por cobrar, presupuestos pendientes), gráfico de seis meses, órdenes por etapa, "requiere atención" y listas de
  equipos, fallas y técnicos. Reemplaza al diálogo "Resumen".
- Listado en forma de tabla con tira de avance de siete etapas, importe y saldo, filas expandibles, orden y "mostrar más".
- Barra superior con búsqueda siempre visible (atajo `/`), estado de la conexión y menú de la cuenta.
- Nueva identidad visual (verde de placa electrónica), modo oscuro y diseño para celular.
- El JavaScript se reparte en archivos con una sola responsabilidad (`util`, `dominio`, `comprobantes`, `dashboard`, `lista`, `orden`, `config`, `app`).
- `scripts/seed_demo.py` carga órdenes de ejemplo en un servidor de desarrollo. Pruebas de coherencia de la parte web.

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
