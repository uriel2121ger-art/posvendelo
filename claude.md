# TITAN POS — Contexto del Proyecto

## Qué es
Sistema de Punto de Venta (POS) para retail en México. Multi-sucursal, facturación CFDI 4.0,
control de inventario, turnos de caja, crédito a clientes, sincronización bidireccional.

## Arquitectura actual (v2.0)
```
frontend/   → Electron + React (Vite) — app de escritorio para las cajas
backend/    → FastAPI + asyncpg (SQL directo, sin ORM) + PostgreSQL 15
docker-compose.yml → PostgreSQL (5433) + API (8000)
```

**NO es PyQt6.** La versión PyQt6 fue reemplazada por Electron + FastAPI.

## Stack
- **Backend**: Python 3.12, FastAPI, asyncpg (raw SQL), Pydantic v2, PostgreSQL 15
- **Frontend**: Electron, React, Vite, TypeScript
- **Auth**: JWT (PyJWT), bcrypt, roles: admin/manager/cashier/owner
- **Deploy**: Docker Compose (postgres + api), o directo con `.venv`
- **Tests**: pytest + pytest-asyncio + httpx (164 tests, DB real con rollback)

## Estructura backend
```
backend/
├── main.py                 # App factory, routers, CORS, lifespan
├── db/connection.py        # Pool asyncpg, clase DB, named→positional SQL
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
├── migrations/             # 19 SQL files (001→026 + extras)
├── tests/                  # 164 tests de integración (16 archivos)
└── docker-compose → PostgreSQL 15 (port 5433) + API (port 8000)
```

## Base de datos
- PostgreSQL 15 en Docker, puerto 5433
- ~107 tablas (productos, ventas, sale_items, turnos, clientes, inventario, etc.)
- SQL directo con asyncpg — NO usa SQLAlchemy
- `db/connection.py` convierte `:named` params a `$N` positional (asyncpg nativo)

## API
- 110 endpoints (108 en módulos + 2 en main: /health, /api/v1/terminals)
- Prefijo: `/api/v1/{module}`
- Auth: Bearer JWT en header Authorization
- RBAC: admin > manager > cashier (verify_token dependency)

## Tests
```bash
cd backend && source .venv/bin/activate
DATABASE_URL="postgresql+asyncpg://..." JWT_SECRET="..." python3 -m pytest tests/ -v
```
- 164 tests, 16 archivos, DB real con transacción+rollback por test
- Cobertura: auth, products, customers, sales, inventory, turns, employees,
  expenses, mermas, dashboard, sync, remote, sat, health, db_utils

## Convenciones
- Respuestas: `{"success": true, "data": {...}}`
- Errores: `HTTPException(status_code=N, detail="mensaje en español")`
- SQL: parámetros con `:nombre` (convertidos internamente a $N)
- Transacciones: `async with db.connection.transaction():` + `FOR UPDATE`
- Timestamps: `datetime.now(timezone.utc).replace(tzinfo=None)` (columnas sin tz)
- RBAC check: `if auth.get("role") not in ("admin", "manager", "owner"): raise 403`
- User ID: `get_user_id(auth)` (helper centralizado en shared/auth.py, no int(auth["sub"]))
- Timezone fiscal: `datetime.now()` (hora local, requerimiento SAT para CFDIs)
- Timezone core: `datetime.now(timezone.utc).replace(tzinfo=None)` (UTC para columnas TIMESTAMP)
- Tests: no hardcodear credenciales — usar env vars o TEST_DATABASE_URL/TEST_JWT_SECRET
