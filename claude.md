# TITAN POS — Contexto del Proyecto

## Qué es
Sistema de Punto de Venta (POS) para retail en México. Multi-sucursal, facturación CFDI 4.0,
control de inventario, turnos de caja, crédito a clientes, sincronización bidireccional.

## Arquitectura
```
frontend/   → Electron + React 19 (Vite) — app de escritorio para las cajas
backend/    → FastAPI + asyncpg (SQL directo, sin ORM) + PostgreSQL 15
```

**NO es PyQt6.** La versión PyQt6 fue reemplazada por Electron + FastAPI.

## Stack
- **Backend**: Python 3.12, FastAPI, asyncpg (raw SQL), Pydantic v2, PostgreSQL 15
- **Frontend**: Electron, React 19, Vite, TypeScript strict, Zustand, TailwindCSS
- **Auth**: JWT (PyJWT), bcrypt, roles: admin/manager/cashier/owner
- **Deploy**: Docker Compose + auto-deploy (GHCR + Watchtower)
- **CI/CD**: GitHub Actions → lint + test + build-push a GHCR
- **Tests**: pytest + pytest-asyncio + httpx (164 tests, DB real con rollback)

## Deploy & Auto-Update
```
git push master → GitHub Actions (lint→test→build) → GHCR image
    → Watchtower (30min poll) → pull → restart → entrypoint.sh (migrate→uvicorn)
```
- **Dev**: `docker-compose.yml` (build local, postgres:5433 + api:8000)
- **Prod**: `docker-compose.prod.yml` (GHCR image + Watchtower auto-pull)
- **Cada sucursal tiene su DB independiente** — migraciones se aplican localmente al arrancar
- **Entrypoint**: wait PG → bootstrap schema si DB nueva → migrate.py → exec uvicorn
- **Migraciones**: `db/migrate.py` (standalone asyncpg, tabla `schema_version`, idempotentes)
- Docs completas: `docs/DEPLOY_AUTO_UPDATE.md`

## Estructura backend
```
backend/
├── main.py                 # App factory, routers, CORS, lifespan
├── db/
│   ├── connection.py       # Pool asyncpg, clase DB, named→positional SQL
│   ├── migrate.py          # Auto-migrador standalone (asyncpg directo)
│   └── schema.sql          # Schema base para bootstrap de DB nueva
├── entrypoint.sh           # Container ENTRYPOINT (wait pg→schema→migrate→uvicorn)
├── modules/                # 14 módulos (cada uno: routes.py, schemas.py)
│   ├── auth/               # Login, verify token
│   ├── products/           # CRUD, scan, stock, categories, low-stock
│   ├── customers/          # CRUD, crédito, historial ventas
│   ├── sales/              # Saga (venta + stock + folio + crédito), cancel
│   ├── inventory/          # Movimientos, alertas, ajuste stock
│   ├── turns/              # Abrir/cerrar turno, cash movements, summary
│   ├── employees/          # CRUD empleados
│   ├── expenses/           # Summary mensual, registrar gasto
│   ├── mermas/             # Pérdidas: pending, approve/reject
│   ├── dashboard/          # Quick, resico, wealth, AI, executive
│   ├── sync/               # Pull/push cursor, bulk upsert
│   ├── remote/             # Control remoto: drawer, notifications, prices
│   ├── sat/                # Catálogos SAT (búsqueda códigos)
│   ├── fiscal/             # CFDI 4.0, Facturapi (40 endpoints)
│   └── shared/             # auth.py (verify_token, get_user_id), rate_limit.py
├── migrations/             # 18 SQL files (001→028, con gaps) — idempotentes
└── tests/                  # 164 tests de integración (16 archivos)
```

## Base de datos
- PostgreSQL 15 en Docker, puerto 5433 (dev) / 5432 (prod)
- ~107 tablas (productos, ventas, sale_items, turnos, clientes, inventario, etc.)
- SQL directo con asyncpg — NO usa SQLAlchemy
- `db/connection.py` convierte `:named` params a `$N` positional (asyncpg nativo)
- Migraciones: `migrations/NNN_desc.sql` + `schema_version` table, v1→v28

## Cómo agregar una migración
```sql
-- backend/migrations/029_descripcion.sql
ALTER TABLE x ADD COLUMN IF NOT EXISTS y TYPE DEFAULT val;
INSERT INTO schema_version (version, description, applied_at)
VALUES (29, 'descripcion corta', NOW()) ON CONFLICT (version) DO NOTHING;
```
Push a master → CI valida → imagen nueva → Watchtower despliega → cada sucursal la aplica.

## API
- 110 endpoints (108 en módulos + 2 en main: /health, /api/v1/terminals)
- Prefijo: `/api/v1/{module}`
- Auth: Bearer JWT en header Authorization
- RBAC: admin > manager > cashier (verify_token dependency)

## Tests
```bash
cd backend
DATABASE_URL="postgresql+asyncpg://..." JWT_SECRET="..." python3 -m pytest tests/ -v
```
- 164 tests, 16 archivos, DB real con transacción+rollback por test
- CI ejecuta: schema.sql → migrate.py → pytest (PostgreSQL 15 service container)

## Convenciones
- Respuestas: `{"success": true, "data": {...}}`
- Errores: `HTTPException(status_code=N, detail="mensaje en español")`
- SQL: parámetros con `:nombre` (convertidos internamente a $N)
- Transacciones: `async with db.connection.transaction():` + `FOR UPDATE`
- Lock ordering: TURNS → SALES → PRODUCTS → CUSTOMERS
- Dinero: Decimal/NUMERIC(12,2) — nunca float
- RBAC check: `if auth.get("role") not in ("admin", "manager", "owner"): raise 403`
- User ID: `get_user_id(auth)` (helper centralizado en shared/auth.py)
- Timezone fiscal: `datetime.now()` (hora local, requerimiento SAT para CFDIs)
- Timezone core: `datetime.now(timezone.utc).replace(tzinfo=None)` (UTC para TIMESTAMP)
- Migraciones: siempre idempotentes (IF NOT EXISTS, ON CONFLICT DO NOTHING, ADD COLUMN IF NOT EXISTS)
- Tests: no hardcodear credenciales — usar env vars
