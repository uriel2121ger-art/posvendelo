# TITAN POS — Esta carpeta es la misma app (rol servidor)

**Importante:** En todas las PCs se instala el mismo software. Una máquina se designa como **servidor** y las demás como **clientes**. Esta carpeta es la misma base de código; el nombre "backend" viene del zip original (servidor, con .venv). En el servidor, esta app expone API, BD y sincronización para las cajas.

## Qué incluye (parte servidor/API de la app)

- **`src/infra/`** — Base de datos (PostgreSQL), esquemas SQL, migraciones, configuración.
- **`src/services/`** — Lógica de negocio: `pos_engine`, módulo fiscal (CFDI, PAC, Facturapi), email.
- **`src/core/`** — Motores: loyalty, gift cards, préstamos, inventario, permisos, promos, reloj checador.
- **`src/api/`** — API (main, ecommerce).
- **`app/api/`** — Admin API, mobile API, WebSocket.
- **`app/services/`** — Servidor HTTP, sync, offline, failover, auditoría, seguridad, inventario, ventas, etc.
- **`app/sync/`** — Sincronización multi-sucursal (extractores, aplicadores, conectividad).
- **`app/repositories/`** — Acceso a datos (productos, turnos, clientes, ventas).
- **`app/models/`** — Modelos y esquemas.
- **`app/config/`** — Configuración del servidor.
- **`migrations/`** — Scripts SQL de migración.
- **`scripts/`** — Herramientas de BD y mantenimiento.
- **`.venv/`** — Entorno virtual Python (dependencias instaladas).

## Cómo ejecutar

```bash
source .venv/bin/activate  # o .venv\Scripts\activate en Windows
python -m app.main
# o levantar el servidor HTTP/API según tu despliegue
```

Requisitos: Python 3.10+, PostgreSQL 14+, ver `requirements.txt`.

## Rol servidor vs cliente

La misma app puede correr como **servidor** (esta PC hace de API/BD/sync) o como **cliente** (caja que se conecta al servidor). El rol se define por configuración. En la PC designada como servidor se usa esta misma instalación con .venv y se levantan los servicios de API/sync.
