# Clasificación Frontend / Backend — TITAN POS

**Modelo real de instalación:** Todas las PCs instalan la misma aplicación. Una se designa como **servidor** y las demás como **clientes**. No hay dos instaladores distintos. Las carpetas `frontend/` y `backend/` en el repo son la misma base de código (copiada desde los zips cliente/servidor); la diferencia en producción es solo el rol (servidor vs cliente) por configuración.

Resumen de qué partes del código son “cara al usuario” (UI) vs “servidor/API”:

---

## Parte “frontend” (UI / caja) — carpeta `frontend/` (o cualquier instalación en modo cliente)

Aplicación de escritorio que corre en cada terminal. Todo lo que el usuario toca y ve.

| Ruta | Descripción |
|------|-------------|
| `app/entry.py` | Entrada: fuentes, icono, `run_app()` |
| `app/core.py` | Fachada POS (singleton), enlace UI ↔ lógica |
| `app/ui/` | Pantallas PyQt6: ventas, productos, inventario, clientes, reportes, fiscal, turnos, configuración, empleados, tiempo |
| `app/ui/components/` | Componentes: temas, botones, toasts, sidebar, atajos, animaciones |
| `app/ui/themes/` | Temas, colores, iconos |
| `app/window/` | Ventana principal, navegación, gestor de servidor |
| `app/wizards/` | Asistentes: setup, migración, importación, exportación |
| `src/ui/` | Wizard primera ejecución, dashboard web (HTML) |
| `assets/` | Fuentes (Poppins), iconos, recursos gráficos |
| `pwa-package/` | PWA: manifest.json, index.html |

**Compartido:** `src/` (motores, servicios, infra) está en la misma app; en una PC cliente se usa en local y se habla con el servidor para sync; en la PC servidor ese mismo código expone API y sync.

---

## Parte “backend” (servidor / API) — carpeta `backend/` (o la PC designada como servidor)

Servidor: API, base de datos, sincronización, lógica que sirve a varias cajas.

| Ruta | Descripción |
|------|-------------|
| `src/infra/` | Base de datos (PostgreSQL), esquemas SQL, migraciones, `database.py`, `database_central.py`, `query_converter.py` |
| `src/services/` | `pos_engine`, módulo `fiscal/` (CFDI, PAC, Facturapi, reportes, PDF, RFC, SAT), `email_service` |
| `src/core/` | Motores: loyalty, gift cards, préstamos, inventario, permisos, promos, reloj checador, ledger, finance |
| `src/api/` | `main.py`, `ecommerce_api.py` |
| `src/config.py` | Configuración |
| `src/utils/` | Utilidades, cache, paths, logs |
| `app/api/` | `admin_api.py`, `mobile_api.py`, `websocket_server.py` |
| `app/services/` | HTTP server, sync engine, offline, failover, auditoría, inventario, ventas, clientes, seguridad (panic wipe, YubiKey, etc.) |
| `app/sync/` | Sincronización: `sync_manager`, `data_extractors`, `data_appliers`, `fk_validator`, `connectivity` |
| `app/repositories/` | Capa de datos: productos, turnos, clientes, ventas |
| `app/models/` | Modelos y esquemas |
| `app/config/` | Configuración del servidor |
| `app/startup/` | Bootstrap, single instance, crash handler |
| `app/turns/` | Gestión de turnos |
| `app/logistics/` | Ubicaciones, proveedores, logística |
| `migrations/` | Scripts SQL (001–019, etc.) |
| `scripts/` | Herramientas BD y mantenimiento |
| `.venv/` | Entorno virtual y dependencias |

---

## Resumen

- **Misma app en todas las PCs.** Una PC = servidor (API, BD, sync), el resto = clientes (cajas). Rol por configuración.
- **frontend/** y **backend/** en el repo = misma base de código; se duplicó por el origen de los zips. Para desarrollar, se puede trabajar en una sola carpeta y tener la otra como copia o unificar más adelante.
- Los zips en **CLIENTE/** y **SERVIDOR/** son respaldo del mismo proyecto.
