# Revisión del POS TITAN (sin tocar código)

Revisión de los zips en **CLIENTE** y **SERVIDOR** de tu punto de venta en producción. Solo lectura; no se modificó ningún archivo.

---

## 1. Qué hay en cada carpeta

| Carpeta   | Archivo ZIP              | Tamaño aprox. | Contenido |
|----------|---------------------------|---------------|-----------|
| **CLIENTE**  | `titan_pos_client.zip`   | ~253 MB       | Código de la app POS (sin `.venv`) |
| **SERVIDOR** | `titan_dist_server.zip` | ~250 MB       | Misma app + `.venv` (Python 3.13) y dependencias |

Ambos zips descomprimen en **`titan_dist/`**. Es el **mismo código base**: en cliente va solo el código; en servidor va código + entorno virtual para ejecutar.

---

## 2. Stack técnico

- **Lenguaje:** Python 3.10+ (en el zip del servidor aparece 3.13).
- **UI:** PyQt6.
- **Base de datos:** PostgreSQL 14+ (también hay referencias a SQLite en esquemas legacy).
- **API:** FastAPI + Uvicorn.
- **Fiscal / CFDI:** lxml, satcfdi, pyOpenSSL, integración con Facturapi y PAC.
- **Otros:** pandas, reportlab, qrcode, bcrypt, JWT, requests, httpx, etc.

El `README_INSTALACION.md` del cliente indica: Python 3.10+, PostgreSQL 14+, PyQt6 y ejecución con `python -m app.main`.

---

## 3. Estructura del proyecto (raíz `titan_dist/`)

### 3.1 Núcleo compartido (`src/`)

- **`src/infra/`** — Base de datos y esquemas:
  - `database.py`, `database_central.py`, `database_config.py`, `query_converter.py`
  - Schemas: `schema.sql`, `schema_postgresql.sql`, `schema_postgresql_optimized_sales.sql`, `schema_sqlite_reverse_engineered.sql`, `loyalty_schema.sql`, `inventory_transfers_schema.sql`, migraciones.
- **`src/services/`** — Lógica de negocio:
  - **`pos_engine.py`** (~125 KB) — Motor principal del POS.
  - **`fiscal/`** — Módulo fiscal amplio: CFDI, PAC, Facturapi, CSD, devoluciones, reportes, PDF, validación RFC, catálogos SAT, etc.
  - `email_service.py`
- **`src/core/`** — Reglas de negocio:
  - `loyalty_engine.py`, `gift_card_engine.py`, `loan_engine.py`, `time_clock_engine.py`, `inventory_manager.py`, `permission_engine.py`, `promo_engine.py`, `ledger.py`, `finance.py`
- **`src/api/`** — API:
  - `main.py`, `ecommerce_api.py`
- **`src/ui/`** (en `src`) — Wizard y dashboard web:
  - `first_run_wizard.py`, `web/dashboard.html`
- **`src/config.py`**, **`src/utils/`**, **`src/ai/brain.py`**

### 3.2 Aplicación desktop y servidor (`app/`)

- **`app/entry.py`** — Punto de entrada: carga fuentes (Poppins), icono, y llama a `run_app(core, ...)` con `POSCore`.
- **`app/core.py`** — Fachada del POS: singleton `POSCore`, inicializa DB (PostgreSQL), `pos_engine`, motores de loyalty, gift card, loan; integra con `src/`.
- **`app/api/`** — APIs adicionales:
  - `admin_api.py`, `mobile_api.py`, `websocket_server.py`
- **`app/services/`** — Servicios de aplicación:
  - HTTP: `http_server.py` (y `http_server_MERGED.py`), `websocket_server`
  - Sincronización: `sync_engine.py`, `auto_sync_exhaustivo.py`, `offline_worker.py`, `network_failover.py`, `sentinel_signal.py`
  - Negocio: `sales_service.py`, `product_service.py`, `inventory_service.py`, `customer_service.py`, `cash_expenses.py`, `monedero_service.py`
  - Seguridad/operación: `panic_wipe.py`, `contingency_mode.py`, `hardware_shield.py`, `yubikey_auth.py`, `biometric_kill.py`, `privacy_shield.py`, `audit_safe.py`, `network_lockdown.py`, etc.
  - Otros: `update_manager.py`, `federation_dashboard.py`, `whatsapp_ticket.py`, `stock_alerts.py`, `purchase_forecast.py`, `product_classifier.py`, etc.
- **`app/ui/`** — Interfaz PyQt6:
  - Pestañas: ventas, productos, inventario, clientes, empleados, reportes, fiscal, tiempo, turnos, configuración, etc.
  - Componentes: temas, iconos, animaciones, toasts, sidebar, atajos.
  - Wizards: configuración, migración, importación, exportación.
- **`app/wizards/`** — `setup_wizard.py`, `migration_wizard.py`, `import_wizard.py`, `export_wizard.py`
- **`app/startup/`** — `bootstrap.py`, `single_instance.py`, `crash_handler.py`
- **`app/sync/`** — `sync_manager.py`, `data_extractors.py`, `data_appliers.py`, `fk_validator.py`, `connectivity.py`
- **`app/turns/`** — `turn_manager.py`
- **`app/logistics/`** — lógica de ubicaciones, proveedores, “ghost” carrier/procurement, “black hole”
- **`app/repositories/`** — capa de datos: productos, turnos, clientes, ventas, base
- **`app/models/`**, **`app/config/`**, **`app/window/`**

### 3.3 Datos y despliegue

- **`data/`** — `config/` (config.json, database.json, feature_flags.json), `pos_config.json`, `temp/` (p. ej. `cart_state.json`).
- **`migrations/`** — Scripts SQL numerados (001–019) y un script Python para audit log.
- **`pwa-package/`** — `manifest.json`, `index.html` (posible uso PWA o pantalla secundaria).
- **`scripts/`** — Herramientas (fix PostgreSQL, permisos, `db_manual_tool.py`, etc.).

---

## 4. Puntos de entrada y flujo

- **Ejecución indicada en README:** `python -m app.main` (no se abrió `app/main.py` en esta revisión; podría ser un wrapper de `app/entry.py`).
- **Entry real:** `app/entry.py` → `run_app(core, ...)` con `POSCore` desde `app/core.py`.
- **Core:** `app/core.py` (POSCore) usa `src.infra.database.initialize_db`, `src.services.pos_engine.pos_engine` y los motores en `src.core.*`.
- **Servidor HTTP:** `app/services/http_server.py` (y opcionalmente `http_server_MERGED.py`) sirve la API para múltiples terminales y sincronización.

---

## 5. Funcionalidades que se deducen (solo lectura)

- **Ventas:** carrito, teclado, cortes, turnos.
- **Inventario:** gestión, transferencias, alertas, “shadow inventory”, clasificador de productos.
- **Fiscal (México):** CFDI 4.0, PAC, Facturapi, CSD, devoluciones, complemento de pago, reportes, PDF, catálogos SAT, RESICO, múltiples emisores.
- **Clientes:** CRM, apartados (layaways), programa de lealtad (y anónimo), tarjetas de regalo, préstamos (loan_engine).
- **Empleados:** reloj checador (time_clock), permisos.
- **Sincronización:** multi-sucursal, modo offline, cola de sincronización, failover de red, “federation dashboard”.
- **Seguridad/operación:** modo contingencia, panic wipe, YubiKey, biometría, privacidad, auditoría, bloqueo de red.
- **Extras:** gastos de caja, monedero, WhatsApp para tickets, pronóstico de compras, actualizaciones, PWA.

---

## 6. Resumen

- **Un solo código base** (“titan_dist”) empaquetado como **cliente** (solo código) y **servidor** (código + `.venv`).
- **Arquitectura:** app PyQt6 + FastAPI, capa `src/` (infra, servicios, core, api) y capa `app/` (UI, servicios de app, sync, wizards, repositorios).
- **Base de datos:** PostgreSQL como principal; esquemas y migraciones bien presentes.
- **Fiscal:** módulo fiscal muy completo (CFDI, PAC, Facturapi, reportes, múltiples emisores).
- **Multi-terminal y resiliencia:** sincronización, offline, failover, turnos y controles de seguridad avanzados.

No se modificó ningún archivo; esta revisión solo describe contenido y estructura a partir de los zips en CLIENTE y SERVIDOR.
