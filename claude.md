# TITAN POS — Contexto

POS retail México. Multi-sucursal, CFDI 4.0, inventario, turnos, crédito, sync bidireccional.

## Stack
- **Backend**: Python 3.12, FastAPI, asyncpg (raw SQL, NO ORM), Pydantic v2, PostgreSQL 15
- **Frontend**: Electron, React 19, Vite, TypeScript strict, TailwindCSS
- **Auth**: JWT (PyJWT), bcrypt | Roles: admin/manager/cashier/owner
- **Deploy**: Docker Compose → GHCR → Watchtower auto-pull → entrypoint.sh (migrate→uvicorn)
- **Tests**: pytest+httpx 164 tests (DB real con rollback) | Vitest 83 tests frontend

## Estructura
```
backend/
├── main.py              # App factory, routers, CORS, lifespan
├── db/                  # connection.py (pool+:named→$N), migrate.py, schema.sql
├── modules/             # 15 módulos (cada uno: routes.py, schemas.py)
│   └── auth, products, customers, sales, inventory, turns, employees,
│       expenses, mermas, dashboard, sync, remote, sat, fiscal, shared
├── migrations/          # NNN_desc.sql (idempotentes, schema_version table)
└── tests/               # 16 archivos integración

frontend/src/
├── main/                # Electron main process
├── preload/             # Context bridge (API vacía — todo es HTTP)
└── renderer/src/        # React app: posApi.ts + 27 componentes .tsx
```

## Convenciones
- Respuestas: `{"success": true, "data": {...}}` | Errores: `HTTPException(detail="español")`
- SQL: `:nombre` params (→$N interno) | Transacciones: `async with conn.transaction()` + `FOR UPDATE`
- Lock ordering: TURNS → SALES → PRODUCTS → CUSTOMERS
- Dinero: Decimal/NUMERIC(12,2) nunca float | Fechas: TIMESTAMP nunca TEXT
- RBAC: `if auth.get("role") not in ("admin","manager","owner"): raise 403`
- User ID: `get_user_id(auth)` | Timezone core: UTC naive | Timezone fiscal: local (SAT)
- Migraciones: siempre IF NOT EXISTS / ON CONFLICT DO NOTHING
- CORS: `CORS_ALLOWED_ORIGINS` env var (main.py auto-agrega null + LAN IPs)
- Frontend: posApi.ts(apiFetch 3s / apiFetchLong 15s), localStorage(titan.*), localhost en discovery

## Reglas de Seguridad (anti-regresion)
- **Precios**: NUNCA confiar en `item.price` del payload para productos con `product_id`. Siempre usar `prod["price"]` del SELECT FOR UPDATE.
- **PINs**: Almacenar como `sha256` hex en `users.pin_hash`. Verificar con `hashlib.sha256(pin.encode()).hexdigest()`. NUNCA comparar PINs en texto plano.
- **Cancelaciones**: `cancel_sale()` SIEMPRE requiere `SaleCancelRequest(manager_pin)`. Sin excepciones.
- **Null bytes**: El middleware `NullByteSanitizer` DEBE estar activo. PG TEXT no acepta `\x00`.
- **PIN queries**: Usar tabla `users` (no `employees`) para verificar PINs con `role IN ('admin','manager','owner')`.

## Tests
```bash
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/ -v
cd frontend && npx vitest run
```
