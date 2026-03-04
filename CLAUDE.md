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
- RBAC: `if auth.get("role") not in ("admin","manager","owner"): raise 403`
- User ID: `get_user_id(auth)` | Timezone core: UTC naive | Timezone fiscal: local (SAT)
- Migraciones: siempre IF NOT EXISTS / ON CONFLICT DO NOTHING
- asyncpg + TIMESTAMP: escribir hora actual con `NOW()` en SQL; no pasar datetime desde Python (bug naive/aware). Ver docs/bug-investigation-cierre-turno-500.md
- CORS: `CORS_ALLOWED_ORIGINS` env var (main.py auto-agrega null + LAN IPs)
- Frontend: posApi.ts(apiFetch 3s / apiFetchLong 15s), localStorage(titan.*), localhost en discovery

## Reglas de Seguridad (anti-regresion)
- **Precios**: NUNCA confiar en `item.price` del payload para productos con `product_id`. Siempre usar `prod["price"]` del SELECT FOR UPDATE.
- **PINs**: Almacenar como `sha256` hex en `users.pin_hash`. Verificar con `hashlib.sha256(pin.encode()).hexdigest()`. NUNCA comparar PINs en texto plano.
- **Cancelaciones**: `cancel_sale()` SIEMPRE requiere `SaleCancelRequest(manager_pin)`. Sin excepciones.
- **Null bytes**: El middleware `NullByteSanitizer` DEBE estar activo. PG TEXT no acepta `\x00`.
- **PIN queries**: Usar tabla `users` (no `employees`) para verificar PINs con `role IN ('admin','manager','owner')`.

## Arquitectura hub-spoke
- Hub-and-spoke: nodos locales + gateway central en homelab
- Offline-first: FastAPI + PostgreSQL local por sucursal
- Sync: periódico via Tailscale VPN al gateway
- Clientes: Novedades Lupita, 2 sucursales en Mérida, Yucatán
- Device fingerprinting: MAC + CPU ID + nombre de equipo

## Reglas de sync
- BUG CONOCIDO: después de sync ejecutar `SELECT setval()` para corregir secuencias PostgreSQL — de lo contrario duplicate key violations
- Nunca romper compatibilidad de sync sin versionar el protocolo
- La DB local es fuente de verdad mientras el nodo está offline

## Herramientas disponibles
- **Context7 MCP**: Documentación actualizada de FastAPI, asyncpg, Pydantic — prefijo `use context7`
- **PostgreSQL MCP** (`postgres-titan`): Consultas directas a la DB local (read-only) — diagnóstico sin salir de Claude
- **GitHub MCP**: Ver issues, PRs, crear PRs desde Claude
- **Sequential Thinking MCP**: Planear antes de ejecutar en refactors grandes o cambios multi-archivo
- **Pre-commit review**: `/pre-commit-review` — 9 revisores paralelos (haiku) antes de commit

## Delegación — equipos de agentes (Swarm Mode)
Para tareas complejas, usar agent teams con estos patrones:
- **Feature completa**: api-dev (endpoints) + db-dev (migraciones) + test-dev (tests)
- **Debug producción**: investigator (reproduce) + fixer (implementa fix)
- **Code review**: security-reviewer + performance-reviewer + coverage-reviewer
- Teammates implementación → modelo sonnet | Teammates revisión → modelo haiku

## Comandos
```bash
# Backend dev
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m uvicorn main:app --host 0.0.0.0 --port 8090 --reload

# Tests backend
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/ -v

# Tests frontend
cd frontend && npx vitest run

# Sync manual
python -m src.sync.manual

# Migraciones
cd backend && python3 -m db.migrate
```
