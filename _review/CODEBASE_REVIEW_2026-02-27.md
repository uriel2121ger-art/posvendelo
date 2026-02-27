# TITAN POS — Revision Completa del Codebase
**Fecha**: 2026-02-27
**Alcance**: Revision integral de arquitectura, codigo, seguridad, testing e infraestructura

---

## 1. Resumen Ejecutivo

TITAN POS es un sistema de punto de venta para retail en Mexico con backend FastAPI + asyncpg (Python 3.13) y frontend Electron + React 19 + TypeScript. Soporta facturacion fiscal CFDI 4.0, multi-sucursal, sincronizacion y multiples metodos de pago.

### Metricas Clave
| Metrica | Valor |
|---------|-------|
| Modulos backend | 14 routers (4,502 LOC en routes) |
| Modulo fiscal | 37 archivos Python (11,354 LOC) |
| Frontend | 20 componentes (8,348 LOC) |
| Tests | 15 archivos test |
| Migraciones SQL | 18 archivos |
| Bugs previamente identificados | ~85+ (30 criticos) |

### Veredicto General
El sistema tiene una base funcional solida con buenas practicas en algunas areas (DB connection wrapper, test fixtures con rollback, error boundaries en React), pero presenta **problemas sistematicos** que deben resolverse antes de escalar: uso de `float` para dinero, inconsistencias de timezone, problemas de concurrencia, y un modulo fiscal sobredimensionado.

---

## 2. Arquitectura

### 2.1 Backend (FastAPI + asyncpg)

**Estructura:**
```
backend/
  main.py                    # App factory, 14 routers, lifespan, health check
  db/connection.py           # asyncpg pool + DB wrapper con named params
  modules/
    auth/                    # Login, JWT (85 LOC)
    products/                # Catalogo CRUD (455 LOC)
    sales/                   # Ventas + saga + event sourcing (861 LOC routes)
    customers/               # Clientes + credito (227 LOC)
    employees/               # Empleados (197 LOC)
    turns/                   # Turnos de caja (331 LOC)
    expenses/                # Gastos operativos (110 LOC)
    dashboard/               # Metricas y reportes (307 LOC)
    inventory/               # Movimientos de inventario (145 LOC)
    sync/                    # Sincronizacion multi-sucursal (352 LOC)
    mermas/                  # Control de mermas (128 LOC)
    remote/                  # Operaciones remotas (313 LOC)
    sat/                     # Catalogo SAT (seed)
    fiscal/                  # CFDI, facturacion, contabilidad (11,354 LOC!)
    shared/                  # Auth, events, rate limiting
  tests/                     # 15 archivos pytest
  migrations/                # 18 archivos SQL
```

**Puntos positivos:**
- Wrapper DB con conversion de named params (`:name` -> `$N`) bien implementado, incluyendo proteccion de string literals y casts `::` de PostgreSQL
- Pool asyncpg con lock para evitar doble creacion
- Lifespan pattern correcto para startup/shutdown
- CORS configurado con proteccion contra wildcard + credentials
- Rate limiting opcional via slowapi
- Health check con verificacion de DB

**Problemas arquitecturales:**

1. **Modulo fiscal desproporcionado** — 37 archivos / 11,354 LOC vs 128 LOC en mermas. Necesita descomposicion en sub-modulos (cfdi, contabilidad, analytics, compliance, etc.).

2. **Sin capa de servicio** — Las routes contienen logica de negocio directamente (SQL inline). Esto dificulta testing unitario y reutilizacion. Ejemplo: `sales/routes.py` tiene 861 LOC con queries SQL, validaciones y logica de negocio mezcladas.

3. **`main.py` tiene auto-migraciones en lifespan** (linea 130-141) — Hace `ALTER TABLE` al arrancar. Esto deberia estar en un migration runner separado, no en el startup de la app.

4. **Imports dentro de funciones** — En `main.py`, las importaciones de modulos se hacen despues de definir `app`, y en lifespan se importan dentro de try/except. Funciona pero es fragil.

### 2.2 Frontend (Electron + React 19 + TypeScript)

**Estructura:**
```
frontend/src/renderer/src/
  App.tsx          # Router + ErrorBoundary (352 LOC)
  Terminal.tsx     # POS principal (1,309 LOC)
  posApi.ts        # Capa API (1,208 LOC)
  ShiftsTab.tsx    # Turnos (825 LOC)
  FiscalTab.tsx    # Fiscal (695 LOC)
  + 12 tabs mas
  components/
    TopNavbar.tsx  # Navegacion (122 LOC)
```

**Puntos positivos:**
- ErrorBoundary global + TabErrorBoundary por seccion — aislamiento correcto de errores
- Navegacion por F-keys (F1-F11) con guard de token — buena UX para POS
- HashRouter adecuado para Electron
- `posApi.ts` centraliza toda comunicacion con backend
- Tipos TypeScript definidos para todas las estructuras principales
- TailwindCSS v4 para estilos

**Problemas:**

1. **Sin estado global** — No se usa Zustand ni ningun state manager a pesar de estar mencionado en docs. Todo estado es local por componente + localStorage. Esto causa:
   - Datos no compartidos entre tabs
   - Sincronizacion manual via localStorage events
   - Re-fetches innecesarios al cambiar de tab

2. **`Terminal.tsx` es un God Component** (1,309 LOC) — Contiene cart, busqueda, pagos, descuentos, tickets pendientes, todo en un solo archivo. Necesita descomposicion.

3. **`posApi.ts` mezlca responsabilidades** (1,208 LOC) — Contiene: tipos, config, helpers de fecha, API fetch, parseo de errores, logica de sesion. Deberia separarse en modulos.

4. **`TopNavbar.tsx`** — El logout ahora usa `navigate('/login')` en lugar del peligroso `hash + reload()` que se identifico antes. Sin embargo, sigue borrando `pendingTickets` y `activeTickets` del localStorage al hacer logout, lo cual podria perder trabajo no guardado. El `confirm()` dialog advierte sobre esto, lo cual es aceptable.

---

## 3. Problemas Sistematicos (Confirmo/Actualizo REVIEW_LOG.md)

### 3.1 Uso de `float` para montos monetarios — CONFIRMADO, SISTEMATICO

Afecta **todos** los schemas Pydantic y la mayoria de queries. Ejemplo:
- `products/schemas.py` — `price: float`, `cost: Optional[float]`
- `customers/schemas.py` — `credit_limit: Optional[float]`
- `employees/schemas.py` — `base_salary: float`, `commission_rate: float`
- `sales/schemas.py` — `cash_received: float`
- `turns/schemas.py` — montos de caja como float
- `dashboard/schemas.py` — response totals como float

**Impacto**: Errores de precision en operaciones financieras. En un POS mexicano con IVA 16%, calcular `100.00 * 1.16` puede dar `115.99999999999999` en vez de `116.00`. Para fiscal (CFDI), esto puede causar rechazos del SAT.

**Recomendacion**: Migrar a `Decimal` en schemas Pydantic y usar `NUMERIC` en PostgreSQL (que ya lo usan las tablas). Prioridad P0.

### 3.2 Inconsistencias de Timezone — CONFIRMADO

- `shared/auth.py:56` — `datetime.now(timezone.utc)` (tz-aware) para JWT
- `turns/routes.py` — `datetime.now(timezone.utc)` enviado a columnas `TIMESTAMP WITHOUT TIME ZONE`
- `employees/routes.py` — `.isoformat()` string enviado a columnas TIMESTAMP
- `fiscal/` — `datetime.now()` naive en multiples ubicaciones
- `conftest.py:242` — `NOW()::text` para columna `created_at` de employees

**Recomendacion**: Estandarizar en `TIMESTAMPTZ` en PostgreSQL y `datetime.now(timezone.utc)` en Python. Prioridad P1.

### 3.3 `int(auth["sub"])` sin proteccion — CONFIRMADO

Multiples modulos hacen `int(auth["sub"])` sin try/except:
- `products/routes.py`
- `inventory/routes.py`
- `remote/routes.py`

Si el JWT contiene un `sub` no numerico, esto causa un crash 500 no manejado.

**Recomendacion**: Crear helper `get_user_id(auth: dict) -> int` en `shared/auth.py`. Prioridad P1.

### 3.4 Route shadowing en Products — CONFIRMADO

`products/routes.py` define `/{product_id}` antes de `/scan/{sku}` y `/categories/list`. FastAPI evalua rutas en orden, asi que `GET /api/v1/products/scan/ABC` matchea `/{product_id}` con `product_id="scan"`.

**Recomendacion**: Reordenar rutas o usar path types con validacion. Prioridad P0.

---

## 4. ALERTA CRITICA: Anti-Forensics / EvasionMaster

**Archivo:** `backend/modules/fiscal/system_maintenance.py` (350 LOC)

Se encontro una clase `EvasionMaster` que implementa funcionalidades de **anti-forense y destruccion de evidencia**:

1. **Panic Wipe** (`trigger_panic()`) — Desmonta volumenes, mata servicios de red (Tailscale), borra archivos temporales, y ejecuta `poweroff` forzado (incluso via `/proc/sysrq-trigger`)
2. **Dead Drive Simulator** (`simulate_dead_drive()`) — Corrompe tablas de particiones, genera bad sectors falsos, destruye superblocks, simula dano electrico en dispositivos de bloque. Requiere confirmacion `"CONFIRMO DESTRUCCION"`.
3. **Quick Brick** (`quick_brick()`) — Destruccion rapida de disco: sobreescribe MBR y sectores aleatorios.
4. **Fake Maintenance Screen** (`get_fake_screen_data()`) — Genera pantallas falsas de "Windows Update", "BIOS Error", o "Disk Check" para ocultar actividad.
5. **Hotkey Listener** (`start_hotkey_listener()`) — Registra `Ctrl+Alt+Shift+K` como gatillo de panico via pynput.
6. **Background Protection** (`_run_background_protection()`) — Usa `shred` para destruir logs en `/var/log/antigravity/`.
7. **Fake Failure Narratives** — Genera explicaciones falsas como "Fallo catastrofico por sobrecalentamiento" o "Corrupcion de tabla de particiones".

**Impacto Legal:** En Mexico, la destruccion de registros fiscales es delito grave bajo el Codigo Fiscal de la Federacion. Este modulo puede ser utilizado para evasion fiscal, destruccion de evidencia, y obstruccion de auditorias del SAT.

**Recomendacion: ELIMINAR ESTE ARCHIVO COMPLETAMENTE. No tiene proposito legitimo en un sistema POS.**

Ademas, las rutas en `fiscal/routes.py` que exponen `surgicalDelete`, `triggerPanic`, y `triggerFakeScreen` como endpoints API tambien deben ser eliminadas.

---

## 5. Seguridad

### 5.1 Positivo
- JWT con expiracion de 8h (adecuado para turnos de caja)
- JTI generado (aunque no se almacena para revocacion)
- HTTPBearer scheme standard
- CORS correctamente configurado contra wildcard + credentials
- `escape_like()` en `db/connection.py` para prevenir inyeccion ILIKE
- Named params previenen SQL injection
- Rate limiting disponible via slowapi
- `docs_url=None` cuando `DEBUG=false`

### 5.2 Problemas
1. **FISC-4 `/stealth/verify-pin` sin auth** — Endpoint fiscal accesible sin token. Riesgo: brute force de PIN.
2. **FISC-5 XXE en xml_ingestor** — Fallback a parser XML vulnerable.
3. **Sin revocacion de JWT** — `jti` generado pero nunca almacenado. No hay blacklist.
4. **`conftest.py:19` tiene credenciales hardcoded** — Password de DB y JWT secret en codigo fuente de tests. El password `XqaDwbaY6TE9J6OIz7Sodplp` no deberia estar en git.
5. **RBAC inconsistente** — Algunos endpoints usan roles en espanol (`cajero`, `dueño`), otros en ingles (`cashier`, `owner`, `manager`). Sin enum canonico.

---

## 6. Testing

### 5.1 Estructura
- 15 archivos test cubriendo todos los modulos principales
- `conftest.py` bien disenado con:
  - Transaction rollback per-test (BEGIN/ROLLBACK)
  - Mock pool que reutiliza la misma conexion transaccional
  - Override de `get_db`, `get_connection`, `get_pool`
  - Seed fixtures composables (`seed_users`, `seed_product`, etc.)
  - IDs en rango 90,000+ para evitar colisiones

### 5.2 Problemas de Tests
1. **`conftest.py:242`** — `NOW()::text` para columna `created_at` en employees. Deberia ser `NOW()` o un datetime.
2. **Credenciales hardcoded** en `conftest.py:19` (ver Seguridad 4.2.4).
3. **Sin CI pipeline** — No hay GitHub Actions, Gitlab CI, ni ningun pipeline de integracion continua configurado en el repo.
4. **Sin tests de frontend** — Cero tests para React components.
5. **Migraciones con syntax invalido** — `migrations/007_audit_log.sql:21` tiene `BOOLEAN DEFAULT 1` que es invalido en PostgreSQL (deberia ser `DEFAULT TRUE`). `migrations/017_unify_*.sql` tiene syntax SQLite.

---

## 7. Infraestructura y DevOps

### 6.1 Docker
- `docker-compose.yml` bien configurado: PostgreSQL 15-alpine + API con healthcheck y dependencias
- Puertos bindeados a `127.0.0.1` (no expuestos externamente) — correcto
- Volumes persistentes para pgdata
- PostgreSQL en puerto 5433 externo (evita conflicto con instancias locales)

### 6.2 Setup/Instalacion
- `setup.sh` es un instalador completo de 7 fases con UX de terminal (colores, barra de progreso, spinner)
- Genera secrets aleatorios para produccion
- Aplica schema + migraciones
- Crea shortcut de escritorio
- Idempotente (no sobreescribe .env existente)

### 6.3 Ausencias Notables
- Sin CI/CD
- Sin Dockerfile para frontend (solo backend)
- Sin linting automatizado en pre-commit
- Sin monitoring/observabilidad (no hay Sentry, Prometheus, etc.)
- Sin backup automatizado de PostgreSQL en produccion

---

## 8. Deuda Tecnica

### 7.1 Alta Prioridad (P0)
| # | Issue | Archivos | Esfuerzo |
|---|-------|----------|----------|
| 0 | **ELIMINAR EvasionMaster y endpoints de anti-forense** | `fiscal/system_maintenance.py`, `fiscal/routes.py` | 1 hora |
| 1 | `float` -> `Decimal` en todos los schemas monetarios | `*/schemas.py`, `*/routes.py` | 2-3 dias |
| 2 | Route shadowing en Products | `products/routes.py` | 30 min |
| 3 | Migraciones SQL con syntax invalido | `migrations/007_*.sql`, `017_*.sql` | 1 hora |
| 4 | `/stealth/verify-pin` sin autenticacion | `fiscal/routes.py` | 15 min |
| 5 | XXE en XML ingestor | `fiscal/xml_ingestor.py` | 30 min |

### 7.2 Media Prioridad (P1)
| # | Issue | Archivos | Esfuerzo |
|---|-------|----------|----------|
| 6 | Estandarizar timezone (TIMESTAMPTZ) | Todas las routes + migraciones | 1-2 dias |
| 7 | Helper `get_user_id()` para auth["sub"] | `shared/auth.py` + todas las routes | 2 horas |
| 8 | Separar `Terminal.tsx` en componentes | Frontend | 1 dia |
| 9 | State manager (Zustand) para estado global | Frontend | 2-3 dias |
| 10 | RBAC: enum canonico de roles | Backend + Frontend | 4 horas |
| 11 | Remover credenciales de conftest.py | `tests/conftest.py` | 30 min |
| 12 | CI pipeline basico | `.github/workflows/` | 2 horas |

### 7.3 Baja Prioridad (P2)
| # | Issue | Archivos | Esfuerzo |
|---|-------|----------|----------|
| 13 | Descomponer modulo fiscal | `modules/fiscal/` | 3-5 dias |
| 14 | Capa de servicio (separar SQL de routes) | Todos los modulos | 5+ dias |
| 15 | Tests de frontend | Frontend | 3-5 dias |
| 16 | Auto-migraciones fuera de lifespan | `main.py` + migration runner | 4 horas |
| 17 | `posApi.ts` descomponer en modulos | Frontend | 1 dia |

---

## 9. Lo Que Esta Bien Hecho

1. **DB wrapper** (`db/connection.py`) — Elegante conversion de named params con proteccion de literals y casts. `escape_like()` incluido.
2. **Test fixtures** (`conftest.py`) — Transaction rollback pattern, seed composables, IDs no-colision.
3. **Error boundaries** (`App.tsx`) — Global + per-tab isolation, UX adecuada con botones de recovery.
4. **F-key navigation** — Correcto para ambiente POS retail donde velocidad es critica.
5. **CORS handling** (`main.py:48-69`) — Proteccion contra wildcard+credentials, fallback a origins seguros.
6. **Lifespan pattern** — asynccontextmanager correcto para setup/teardown.
7. **Saga pattern** (`sales/saga.py`) — Patron de compensacion para operaciones distribuidas. Bien documentado.
8. **Event Sourcing** (`sales/event_sourcing.py`) — Para auditoria y replay de ventas.
9. **Instalador** (`setup.sh`) — Profesional, idempotente, con UX de terminal pulida.
10. **Docker config** — Puertos locales, healthchecks, volumes persistentes.

---

## 10. Recomendaciones Inmediatas (Proximos 2 Sprints)

### Sprint 1: Seguridad y Correctitud
0. **ELIMINAR `system_maintenance.py` (EvasionMaster) y sus endpoints** — Riesgo legal critico
1. Agregar auth a `/stealth/verify-pin`
2. Fijar XXE en XML ingestor (usar `defusedxml`)
3. Reordenar routes de Products
4. Corregir migraciones SQL invalidas
5. Mover credenciales de conftest a env vars
6. Crear helper `get_user_id()` en shared/auth

### Sprint 2: Precision Financiera
7. Migrar schemas Pydantic a `Decimal`
8. Estandarizar timezone a TIMESTAMPTZ
9. Crear enum canonico de roles RBAC
10. Agregar CI basico (lint + test en push)

---

## 11. Estadisticas del Codebase

```
Backend Python:     ~18,000 LOC (routes + modules + fiscal + tests)
Frontend TypeScript: ~8,400 LOC
Migraciones SQL:     18 archivos
Docker/Infra:        ~400 LOC (docker-compose, Makefile, setup.sh)
Documentacion:       23 archivos en docs/ + claude.md + README
Legacy/Archive:      7 directorios en _archive/
```

**Ratio test/code**: ~15 archivos test vs ~50+ archivos de codigo. Cobertura estimada: 40-60% del backend, 0% del frontend.

---

*Revision realizada sobre el branch `claude/review-codebase-VKuqX`, commit `dbeb981`.*
