# TITAN POS Backend — API v2.0

Sistema de Punto de Venta para retail. Backend FastAPI con asyncpg (SQL directo) y PostgreSQL 15.

## Stack

| Componente | Tecnología |
|-----------|-----------|
| Framework | FastAPI (Python 3.12) |
| Base de datos | PostgreSQL 15 (Docker, puerto 5433) |
| Driver DB | asyncpg (raw SQL, sin ORM) |
| Validación | Pydantic v2 |
| Auth | JWT (PyJWT) + bcrypt |
| Tests | pytest + pytest-asyncio + httpx (181 tests) |
| Rate limit | slowapi (requerido) |

## Inicio rápido

### Con Docker Compose (recomendado)

```bash
cd "<ruta-del-proyecto>"
cp .env.example .env   # Editar credenciales
docker compose up -d   # Levanta PostgreSQL + API
```

Servicios:
- **PostgreSQL**: `localhost:5433`
- **API**: `localhost:8000`
- **Docs**: `localhost:8000/docs` (solo con `DEBUG=true`)

### Desarrollo local (sin Docker para la API)

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt   # Incluye defusedxml para Parsear XML (Fiscal)

# Asegurar que PostgreSQL esté corriendo (Docker o local)
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Importante:** La funcionalidad **Parsear XML** (Fiscal → Facturación) requiere **defusedxml**. Viene en `requirements.txt`; si instalas solo algunas dependencias, incluye `defusedxml>=0.7.1`. Ver `docs/referencia/PARSEAR_XML_FISCAL.md`.

## Estructura

```
backend/
├── main.py                  # App factory, CORS, routers, lifespan
├── db/
│   └── connection.py        # Pool asyncpg, clase DB, conversión :named → $N
├── modules/                 # 14 módulos de negocio
│   ├── auth/                # POST /login, GET /verify (1 endpoint)
│   ├── products/            # CRUD, scan barcode, stock, categories (12)
│   ├── customers/           # CRUD, crédito, historial ventas (7)
│   ├── sales/               # Crear venta (saga), cancelar, search (9)
│   ├── inventory/           # Movimientos, alertas, ajuste stock (3)
│   ├── turns/               # Abrir/cerrar turno, cash movements (6)
│   ├── employees/           # CRUD empleados (5)
│   ├── expenses/            # Summary mensual, registrar gasto (2)
│   ├── mermas/              # Pérdidas: pendientes, aprobar/rechazar (2)
│   ├── dashboard/           # Quick, RESICO, wealth, AI, executive (6)
│   ├── sync/                # Pull/push con cursor, bulk upsert (6)
│   ├── remote/              # Control remoto PWA: drawer, notif, prices (7)
│   ├── sat/                 # Búsqueda catálogos SAT (2)
│   ├── fiscal/              # CFDI 4.0, Facturapi, emisores, facturas (40)
│   └── shared/              # auth.py (verify_token), rate_limit.py
├── migrations/              # 18 archivos SQL (001→025)
├── tests/                   # 181 tests de integración
│   ├── conftest.py          # Fixtures: DB, auth, seeds
│   ├── test_sales.py        # 25 tests (saga, cancel, search)
│   ├── test_products.py     # 25 tests (CRUD, stock, scan)
│   └── ... (14 archivos más)
├── fiscal/                  # Utilidades fiscales (CFDI)
├── assets/                  # Recursos estáticos
├── Dockerfile               # Build de producción
├── pyproject.toml           # Config pytest
└── requirements.txt         # Dependencias Python
```

## API

**Base URL**: `http://localhost:8000`

### Endpoints principales (110 total)

| Prefijo | Módulo | Endpoints | Descripción |
|---------|--------|-----------|-------------|
| `/health` | main | 1 | Health check |
| `/api/v1/terminals` | main | 1 | Lista de sucursales |
| `/api/v1/auth` | auth | 1 | Login (POST /login) |
| `/api/v1/products` | products | 12 | CRUD, scan, stock, categories |
| `/api/v1/customers` | customers | 7 | CRUD, crédito, historial |
| `/api/v1/sales` | sales | 9 | Venta, cancelación, búsqueda |
| `/api/v1/inventory` | inventory | 3 | Movimientos, alertas, ajuste |
| `/api/v1/turns` | turns | 6 | Turnos de caja |
| `/api/v1/employees` | employees | 5 | CRUD empleados |
| `/api/v1/expenses` | expenses | 2 | Gastos |
| `/api/v1/mermas` | mermas | 2 | Pérdidas/mermas |
| `/api/v1/dashboard` | dashboard | 6 | Dashboards y KPIs |
| `/api/v1/sync` | sync | 6 | Sincronización multi-sucursal |
| `/api/v1/remote` | remote | 7 | Control remoto (PWA) |
| `/api/v1/sat` | sat | 2 | Catálogos SAT |
| `/api/v1/fiscal` | fiscal | 40 | Facturación CFDI 4.0 |

### Autenticación

Todos los endpoints (excepto `/health` y `/api/v1/auth/login`) requieren JWT:

```
Authorization: Bearer <token>
```

Roles: `admin` > `manager` > `cashier` > `owner`

### Formato de respuesta

```json
// Éxito
{"success": true, "data": { ... }}

// Error
{"detail": "Mensaje de error en español"}
```

## Base de datos

- **PostgreSQL 15** en Docker (puerto 5433)
- ~107 tablas
- SQL directo con asyncpg (sin ORM)
- Parámetros nombrados `:param` convertidos internamente a `$N`
- Transacciones explícitas con `FOR UPDATE` para operaciones críticas

### Migraciones

18 archivos SQL en `migrations/`. Se aplican automáticamente al iniciar la app (lifespan).

## Tests

```bash
cd backend && source .venv/bin/activate

# Correr todos (181 tests)
DATABASE_URL="postgresql+asyncpg://titan_user:PASSWORD@localhost:5433/titan_pos" \
JWT_SECRET="tu-secret" \
python3 -m pytest tests/ -v

# Un módulo específico
python3 -m pytest tests/test_sales.py -v

# Con output detallado
python3 -m pytest tests/ -v --tb=long -s
```

### Cobertura por módulo

| Archivo | Tests | Qué prueba |
|---------|-------|-----------|
| test_db_utils.py | 13 | Conversión SQL :named→$N, escape_like |
| test_health.py | 3 | Health check, terminals |
| test_auth.py | 11 | Login, verify, RBAC |
| test_products.py | 25 | CRUD, scan, stock, categories, price history |
| test_customers.py | 12 | CRUD, crédito, historial ventas |
| test_sales.py | 25 | Saga completa, cancelación, IVA, folio |
| test_turns.py | 14 | Abrir/cerrar, cash movements, summary |
| test_inventory.py | 8 | Movimientos, alertas, ajuste stock |
| test_employees.py | 9 | CRUD empleados |
| test_expenses.py | 7 | Summary mensual, registro |
| test_mermas.py | 6 | Pending, approve/reject con stock |
| test_dashboard.py | 8 | Quick, RESICO, wealth, AI, executive |
| test_sync.py | 10 | Pull cursor, push upsert |
| test_remote.py | 9 | Live sales, notifications, change price |
| test_sat.py | 4 | Búsqueda catálogos SAT |
| test_security.py | 7 | PIN, null bytes, sanitización |
| test_xml_parse.py | 5 | Parsear XML CFDI 4.0 (ingestor + API: 403, 400, 200; requiere defusedxml) |
| **Total** | **181** | |

### Aislamiento

Cada test corre dentro de una transacción que se revierte al finalizar (BEGIN → test → ROLLBACK).
Los datos de la DB real no se contaminan.

## Variables de entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | Conexión PostgreSQL | `postgresql+asyncpg://user:pass@host:5433/titan_pos` |
| `JWT_SECRET` | Secreto para firmar JWT | (cadena larga aleatoria) |
| `DEBUG` | Habilita /docs Swagger | `true` / `false` |
| `CORS_ALLOWED_ORIGINS` | Orígenes permitidos (CSV) | `http://localhost:3000,http://localhost:5173` |
| `ADMIN_API_USER` | Usuario admin API | `admin` |
| `ADMIN_API_PASSWORD` | Password admin API | (secreto) |
| `POSTGRES_PASSWORD` | Password PostgreSQL (Docker) | (secreto) |
