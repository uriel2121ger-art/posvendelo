# TITAN POS Backend — Guía técnica

Detalles de arquitectura interna para desarrolladores.

## Capa de base de datos (`db/connection.py`)

El backend NO usa ORM. Usa **asyncpg directamente** con una clase wrapper `DB`:

```python
class DB:
    """Wrapper sobre asyncpg connection con conversión automática :named → $N."""

    async def fetch(sql, params=None)     # → List[Record]
    async def fetchrow(sql, params=None)  # → Record | None
    async def fetchval(sql, params=None)  # → scalar
    async def execute(sql, params=None)   # → str (status)
```

### Conversión de parámetros

Se escribe SQL con `:nombre` y el wrapper convierte a `$N` para asyncpg:

```python
# Escribes:
await db.fetchrow("SELECT * FROM products WHERE sku = :sku", {"sku": "ABC"})
# Se ejecuta como:
await conn.fetchrow("SELECT * FROM products WHERE sku = $1", "ABC")
```

Cuidados:
- `::jsonb` (cast PostgreSQL) no se confunde con `:param` (doble colon = cast)
- Strings entre comillas simples `':name'` no se reemplazan
- Un mismo `:param` repetido reutiliza el mismo `$N`

### Pool y dependencias

```python
get_db()         # FastAPI Depends → yield DB(connection)
get_connection() # Context manager para módulos que manejan tx manualmente (sales, expenses)
get_pool()       # Retorna el pool asyncpg (usado solo por health check)
```

## Estructura de módulos

Cada módulo en `modules/{name}/` tiene:

```
modules/sales/
├── __init__.py     # (vacío o re-exports)
├── routes.py       # Endpoints FastAPI (APIRouter)
├── schemas.py      # Pydantic v2 models (request/response)
└── saga.py         # (solo sales) Lógica de negocio compleja
```

### Patrones comunes en routes.py

```python
router = APIRouter()

@router.post("/")
async def create_thing(
    body: ThingCreate,                    # Pydantic schema
    auth: dict = Depends(verify_token),   # JWT decoded → {sub, role}
    db=Depends(get_db),                   # DB wrapper
):
    # RBAC check
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos")

    # SQL directo
    row = await db.fetchrow(
        "INSERT INTO things (name) VALUES (:name) RETURNING id",
        {"name": body.name},
    )
    return {"success": True, "data": {"id": row["id"]}}
```

### Transacciones

Para operaciones multi-tabla:

```python
async with db.connection.transaction():
    product = await db.fetchrow(
        "SELECT * FROM products WHERE id = :id FOR UPDATE",  # Lock
        {"id": pid},
    )
    await db.execute("UPDATE products SET stock = stock - :qty WHERE id = :id", {...})
    await db.execute("INSERT INTO inventory_movements ...", {...})
```

## Módulo de ventas (`modules/sales/`)

El más complejo. La creación de venta es una **saga** (`saga.py`):

1. Validar turno abierto
2. Obtener/crear secuencia de folio (serie + terminal)
3. Por cada item:
   - Calcular precio (retail vs wholesale)
   - Extraer o agregar IVA según `price_includes_tax`
   - Aplicar descuento
4. Insertar venta + sale_items
5. Deducir stock (excepto SKU `COM-*`)
6. Registrar inventory_movements
7. Si es crédito: actualizar credit_balance del cliente
8. Generar folio visible (serie + número)

La cancelación revierte todo: stock, crédito, folio.

## Autenticación (`modules/shared/auth.py`)

```python
def create_token(sub: str, role: str) -> str:
    """Genera JWT con sub (user_id) y role."""

async def verify_token(authorization: str = Header(...)) -> dict:
    """Dependency que decodifica JWT y retorna {sub, role}."""
```

Roles: `admin`, `manager`, `cashier`, `owner`

## Convenciones importantes

| Tema | Convención |
|------|-----------|
| Timestamps | `datetime.now(timezone.utc).replace(tzinfo=None)` — columnas sin timezone |
| Soft delete | `is_active = 0` (no DELETE físico) |
| Respuestas | `{"success": True, "data": {...}}` |
| Errores | `HTTPException(detail="texto en español")` |
| IDs de test | Rango 90000+ para evitar colisiones con datos reales |
| Decimal → JSON | `float(valor)` o `model_dump(mode="json")` |
| RBAC | Verificar `auth.get("role")` al inicio del endpoint |
| Stock locks | `FOR UPDATE` en SELECT antes de modificar stock |

## Migraciones

SQL puro en `migrations/`. Se aplican automáticamente en el lifespan de la app.
No hay herramienta de migración (no Alembic). Cada archivo es un script SQL idempotente.

```
migrations/
├── 001_schema_version.sql
├── 002_sync_columns.sql
├── 006_performance_indexes.sql
├── ...
└── 025_folio_index_and_defaults.sql
```

## Tests

Framework: pytest + pytest-asyncio + httpx

### Aislamiento por transacción

Cada test obtiene una conexión asyncpg directa (sin pool), abre `BEGIN`, ejecuta el test,
y hace `ROLLBACK`. Esto permite usar la DB real sin contaminar datos.

```python
@pytest.fixture
async def db_conn():
    conn = await asyncpg.connect(dsn=_DSN)
    tx = conn.transaction()
    await tx.start()
    yield conn
    await tx.rollback()
    await conn.close()
```

### Monkeypatching triple

El fixture `client` override 3 puntos de entrada DB:
1. `get_db` (FastAPI dependency) → DB wrapper sobre la conexión transaccional
2. `get_connection` (context manager) → misma conexión
3. `get_pool` (health check) → mock pool que siempre retorna la misma conexión

### Seeds

Fixtures que insertan datos mínimos para cada tipo de test:
- `seed_branch` → branch id=90001
- `seed_users` → admin + cashier + manager (bcrypt hash de "test1234")
- `seed_product` → 2 productos (con stock y sin stock)
- `seed_customer` → cliente con crédito
- `seed_turn` → turno abierto para admin
- `seed_employee` → empleado de prueba
- `seed_all` → todo lo anterior (para tests de ventas)
