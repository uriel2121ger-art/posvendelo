# TITAN POS — Changelog Deuda Técnica
**Fecha:** 2026-03-03
**Sesion:** Deuda tecnica backend — integridad de datos, precision monetaria, seguridad, refactoring

---

## Fase 1: Integridad de Datos

### Migracion 035 — Timestamps TEXT → TIMESTAMP

**Archivo:** `backend/migrations/035_timestamp_text_to_timestamp.sql`

Convierte columnas de fecha almacenadas como TEXT a tipos nativos de PostgreSQL.
Todas las conversiones son idempotentes (verifica `data_type` antes de alterar) y
manejan strings vacios/invalidos colocandolos en NULL antes del cast.

**Tablas y columnas migradas:**

| Tabla | Columna | Tipo origen | Tipo destino |
|---|---|---|---|
| `sales` | `timestamp` | TEXT | TIMESTAMPTZ |
| `employees` | `created_at` | TEXT | TIMESTAMP |
| `employees` | `hire_date` | TEXT | DATE |
| `card_transactions` | `timestamp` | TEXT | TIMESTAMP |
| `credit_history` | `timestamp` | TEXT | TIMESTAMP |
| `time_clock_entries` | `timestamp` | TEXT | TIMESTAMP |
| `time_clock_entries` | `entry_date` | TEXT | DATE |
| `attendance` | `date` | TEXT | DATE |

**Vistas recreadas tras la migracion:**
- `v_sales_with_origin` — vista regular de ventas con origen de terminal
- `mv_daily_sales_summary` — materialized view de ventas diarias por sucursal
- `mv_hourly_sales_heatmap` — materialized view de heatmap de ventas por hora/dia

**Indice recreado:** `idx_sales_timestamp ON sales("timestamp")`

**Nota:** `cash_expenses.timestamp` fue omitida intencionalmente — la tabla en produccion
fue renombrada a `cash_movements` y ya fue migrada en migracion 032.

---

### Migracion 036 — Indices faltantes y FK de integridad

**Archivo:** `backend/migrations/036_missing_indexes_and_fk.sql`

Auditoria de indices faltantes en tablas de alta actividad. Todos los indices
usan `CREATE INDEX IF NOT EXISTS` para garantizar idempotencia.

**Indices creados:**

| Tabla | Indice | Razon |
|---|---|---|
| `inventory_movements` | `idx_inv_movements_timestamp` | Consultas LIST con rango de fechas y exportes |
| `cash_movements` | `idx_cash_movements_turn_type(turn_id, type)` | `close_turn()` SUM filtrado por turno y tipo (compuesto) |
| `cash_expenses` | `idx_cash_expenses_turn(turn_id)` | `close_turn()` SELECT WHERE turn_id |
| `cash_expenses` | `idx_cash_expenses_timestamp` | Listado de gastos con filtro de fecha |
| `customers` | `idx_customers_name_lower(LOWER(TRIM(name)))` | Busqueda de duplicados al crear cliente (funcional + parcial `is_active=1`) |
| `users` | `idx_users_role_active(role, is_active)` | Verificacion de PIN en cancelaciones y cierres (parcial `is_active=1 AND pin_hash IS NOT NULL`) |

**Constraint de integridad referencial:**
- `fk_inv_movements_product`: `inventory_movements.product_id → products(id) ON DELETE RESTRICT`
- Agregado con `NOT VALID` + `VALIDATE CONSTRAINT` para evitar lock de escritura en tabla grande (PostgreSQL 12+)

---

### Migracion 037 — Funcion fix_all_sequences() para post-sync

**Archivo:** `backend/migrations/037_fix_sequences_function.sql`

**BUG CONOCIDO:** Despues de operaciones de sync hub-spoke, las secuencias PostgreSQL
pueden quedar con `last_value` inferior al `MAX(id)` real de la tabla, causando
errores de `duplicate key violation` al insertar nuevos registros.

**Solucion implementada:** Funcion reutilizable `fix_all_sequences()` que:
1. Itera todas las tablas con columna `id` y secuencia asociada en el schema `public`
2. Compara `MAX(id)` de cada tabla con `last_value` de la secuencia
3. Ejecuta `setval()` solo cuando detecta drift (secuencia retrasada)
4. Devuelve tabla de resultados: `(tabla TEXT, seq_anterior BIGINT, seq_nuevo BIGINT)`

**Endpoint expuesto:** `GET /api/v1/sync/fix-sequences` (rol admin/owner requerido)

```python
# Invocar desde backend (sync/routes.py)
rows = await db.fetch("SELECT tabla, seq_anterior, seq_nuevo FROM fix_all_sequences()")
```

---

## Fase 2: Precision Monetaria

### Migraciones 038-040 — DOUBLE PRECISION → NUMERIC

**Motivacion:** PostgreSQL `DOUBLE PRECISION` (IEEE 754 float de 64 bits) introduce
errores de redondeo en sumas acumuladas. Para dinero y cantidades comerciales se
requiere `NUMERIC` con precision fija. Convencion del proyecto: NUMERIC(12,2) para
montos, NUMERIC(12,4) para cantidades, NUMERIC(5,4) para tasas/porcentajes.

---

#### Migracion 038 — Tablas principales de ventas

**Archivo:** `backend/migrations/038_numeric_sales.sql`

Vistas y materialized views dropeadas al inicio y recreadas al final (mismo patron
que migracion 035). Cada columna verifica `data_type` antes de alterar.

**Tabla `sales` — 11 columnas convertidas a NUMERIC(12,2):**
`total`, `subtotal`, `tax`, `discount`, `cash_received`, `change_given`,
`mixed_cash`, `mixed_card`, `mixed_transfer`, `mixed_wallet`, `mixed_gift_card`

**Tabla `sale_items` — 5 columnas:**
- `price`, `subtotal`, `total`, `discount` → NUMERIC(12,2)
- `qty` → NUMERIC(12,4) (soporta fracciones: 1.5 kg, etc.)

**Vistas recreadas:** `v_sales_with_origin`, `mv_daily_sales_summary`,
`mv_hourly_sales_heatmap`, `mv_product_sales_ranking`

---

#### Migracion 039 — Tablas operacionales core

**Archivo:** `backend/migrations/039_numeric_operations.sql`

**Resumen por tabla:**

| Tabla | Columnas convertidas |
|---|---|
| `products` | `price`, `cost`, `cost_price`, `cost_a`, `cost_b`, `price_wholesale` → NUMERIC(12,2); `stock`, `min_stock`, `max_stock`, `shadow_stock`, `qty_from_a`, `qty_from_b` → NUMERIC(12,4); `tax_rate` → NUMERIC(5,4) |
| `customers` | `credit_balance`, `credit_limit`, `wallet_balance` → NUMERIC(12,2) |
| `turns` | `initial_cash`, `final_cash`, `system_sales`, `difference` → NUMERIC(12,2) |
| `cash_movements` | `amount` → NUMERIC(12,2) |
| `cash_expenses` | `amount` → NUMERIC(12,2) |
| `cash_extractions` | `amount` → NUMERIC(12,2) |
| `credit_movements` | `amount`, `balance_after` → NUMERIC(12,2) |
| `credit_history` | `amount`, `balance_before`, `balance_after` → NUMERIC(12,2) |
| `turn_movements` | `amount` → NUMERIC(12,2) |

**Total migracion 039:** 26 columnas en 9 tablas

---

#### Migracion 040 — Tablas secundarias (helper idempotente)

**Archivo:** `backend/migrations/040_numeric_secondary.sql`

Introduce helper temporal `_migrate_to_numeric(table, column, precision, scale)`
que verifica `data_type = 'double precision'` antes de ejecutar el ALTER,
evitando re-conversiones. El helper se elimina con `DROP FUNCTION` al final.

**Tablas cubiertas (40 tablas, ~75 columnas):**

| Grupo | Tablas |
|---|---|
| RRHH | `employees` (4 cols), `employee_loans` (3), `loan_payments` (2) |
| Devoluciones | `returns` (5 cols), `return_items` (2) |
| Facturacion | `invoices` (3 cols), `cfdis` (3) |
| Apartados | `layaways` (3 cols), `layaway_items` (3), `layaway_payments` (1) |
| Compras | `purchases` (3), `purchase_orders` (3), `purchase_order_items` (3), `purchase_costs` (1) |
| Historial precios | `price_change_history` (6 cols) |
| Inventario | `inventory_log` (2), `inventory_movements` (1), `inventory_transfers` (2), `transfer_items` (3), `loss_records` (3) |
| Kits | `kit_components` (1), `kit_items` (1) |
| E-commerce | `online_orders` (4), `order_items` (3), `payments` (1) |
| Pagos/Wallet | `gift_cards` (2), `wallet_transactions` (1), `card_transactions` (2) |
| Promociones | `promotions` (3), `loyalty_accounts` (3), `loyalty_ledger` (4), `loyalty_rules` (3), `loyalty_fraud_log` (1) |
| Misc | `self_consumption` (2), `personal_expenses` (1), `product_lots` (1), `bin_locations` (1), `branch_inventory` (3) |
| Asistencia | `attendance_summary` (1), `attendance_rules` (1) |
| Analytics | `analytics_conversions` (1), `invoice_ocr_history` (1) |
| Logistica | `transfer_suggestions` (1), `shelf_audits` (1), `warehouse_pickups` (1), `cart_items` (2) |
| Bundles | `resurrection_bundles` (3) |

**Exclusiones explícitas:** `ghost_*`, `shadow_*`, `anonymous_*`, `crypto_*` (modulo fiscal, manejo especial)

**Total migracion 040:** ~75 columnas en ~40 tablas

---

**Resumen total fase NUMERIC (038-040):**
- Tablas afectadas: ~52 tablas
- Columnas convertidas: ~115 columnas
- DOUBLE PRECISION eliminado de toda la logica de negocio

---

## Fase 3: Security Hardening

### JTI — Revocacion de tokens JWT

**Archivo modificado:** `backend/modules/shared/auth.py`

Implementacion de diccionario de revocacion de JTI (JSON Token Identifier) en memoria:
- Cada token emitido incluye claim `jti` con `secrets.token_hex(16)`
- Logout/desactivacion de cuenta llama `revoke_token(jti, expires_at)`
- `verify_token()` verifica el JTI contra el diccionario antes de aceptar el token
- Eviccion automatica por TTL + cap de 10,000 entradas (`_evict_revoked()`)
- Thread-safe con `threading.Lock()`

```python
# Emision de token con JTI
jti = secrets.token_hex(16)
payload = {"sub": user_id, "role": role, "jti": jti, ...}

# Verificacion en cada request
jti = payload.get("jti")
if jti and _is_revoked(jti):
    raise HTTPException(status_code=401, detail="Token revocado")
```

---

### Rate Limiting — slowapi obligatorio

**Archivos modificados:** `backend/modules/shared/rate_limit.py`, `backend/main.py`,
`backend/modules/auth/routes.py`

Slowapi ahora es dependencia obligatoria (no opcional). Si no esta instalada,
la aplicacion falla al iniciar en lugar de funcionar sin limitacion.

**Limites configurados:**
- Default global: `5/minute` en produccion, `25/minute` en DEBUG (tests E2E)
- Login endpoint: `5/minute` prod / `25/minute` DEBUG (rate limit independiente)
- PIN brute-force: `5 intentos / 5 minutos` por IP, `10 en DEBUG`
  - 4-digit PINs = 10,000 combinaciones — proteccion estricta esencial

**Deteccion de IP real:** Se usa `request.client.host` (TCP directo) en lugar de
`X-Forwarded-For` — el POS opera en LAN sin reverse proxy, los headers podrian ser
falsificados.

---

### Credenciales en tests

**Archivo modificado:** `backend/tests/conftest.py`

- Eliminadas credenciales hardcodeadas del archivo de configuracion de tests
- `DATABASE_URL` ahora se lee exclusivamente de variables de entorno (falla con
  `RuntimeError` si no esta configurada, en lugar de usar fallback inseguro)
- `JWT_SECRET` usa `TEST_JWT_SECRET` env var o fallback con warning claro
- IDs de test movidos al rango 90,000+ para evitar colisiones con datos reales

---

## Fase 4: Refactoring — Modulos Compartidos

### Nuevo modulo: `modules/shared/pin_auth.py`

**Archivo:** `backend/modules/shared/pin_auth.py`

Funcion `verify_manager_pin(pin, conn)` extraida y reutilizable:
- Consulta usuarios activos con `role IN ('admin', 'manager', 'owner')` y PIN configurado
- Soporte dual de hash: bcrypt (moderno, `$2b$`/`$2a$`) con fallback a SHA-256 legacy
- Comparacion SHA-256 con `hmac.compare_digest()` (timing-safe, previene timing attacks)
- Raises `HTTPException(403)` si ningun PIN coincide

**Consumidores:** `sales/routes.py` (cancelaciones), `turns/routes.py` (cierres de turno)

---

### Nuevo modulo: `modules/shared/turn_service.py`

**Archivo:** `backend/modules/shared/turn_service.py`

Funcion `calculate_turn_summary(turn_id, initial_cash, conn)` extraida:
- Calcula efectivo esperado al cierre del turno
- Ventas en efectivo (cash puro + parte cash de pagos mixtos)
- Movimientos de entrada y salida de caja
- Ventas por metodo de pago (para desglose en reporte)
- Toda la aritmetica usa `Decimal` con `ROUND_HALF_UP` — nunca float

**Consumidores:** `turns/routes.py`, `hardware/routes.py` (reporte de turno para impresora)

---

### Refactoring: `modules/dashboard/routes.py`

**Cambio:** Queries que filtraban por fecha ahora pasan objetos `datetime` nativos
en lugar de strings ISO, aprovechando que `sales.timestamp` ya es `TIMESTAMPTZ`
(migracion 035). Elimina el casting implicito que ocultaba el tipo de dato.

---

### Refactoring: `modules/sync/routes.py`

**Cambio:** Nuevo endpoint `GET /api/v1/sync/fix-sequences` que expone
`fix_all_sequences()` (migracion 037) via HTTP para ejecucion remota post-sync.
Solo accesible para roles `admin`/`owner`.

---

## Fase 5: Columnas Duplicadas en customers

### Migracion 041 — Drop columnas duplicadas de customers

**Archivo:** `backend/migrations/041_drop_duplicate_customer_columns.sql`

Auditoria con `information_schema` + grep en codigo confirmo 5 columnas duplicadas
en la tabla `customers` que no son referenciadas por ningun endpoint activo.
Antes del DROP, se ejecuta safety copy (UPDATE canonical FROM deprecated WHERE canonical IS NULL).

**Columnas eliminadas:**

| Columna eliminada | Columna canonica (conservada) | Razon |
|---|---|---|
| `loyalty_points` | `points` | Renombrada en migracion anterior |
| `loyalty_level` | `tier` | Renombrada en migracion anterior |
| `ciudad` | `city` | Estandarizacion a ingles |
| `estado` | `state` | Estandarizacion a ingles |
| `codigo_postal` | `postal_code` | Estandarizacion a ingles |

---

## Fase 6: Fixes de Regresion post-migracion

Las migraciones TEXT→TIMESTAMP/DATE (035) rompieron codigo que pasaba strings
a asyncpg donde ahora se esperan objetos Python nativos.

### Fix: remote/routes.py — CURRENT_DATE::text

**Problema:** `WHERE timestamp >= CURRENT_DATE::text` fallaba porque `sales.timestamp`
es ahora TIMESTAMPTZ y no se puede comparar con TEXT.

**Solucion:** Removido `::text` cast — TIMESTAMPTZ se compara directo con `CURRENT_DATE`.
Tambien cambiado `(CURRENT_DATE + 1)::text` → `CURRENT_DATE + INTERVAL '1 day'`.

### Fix: employees/routes.py — hire_date y created_at

**Problema:** `hire_date` se pasaba como string `"2026-03-03"` a una columna DATE,
y `created_at` se pasaba como `.isoformat()` string a una columna TIMESTAMP.
asyncpg requiere objetos nativos (`datetime.date` / `datetime`).

**Solucion:**
- `hire_date`: `datetime.strptime(value, "%Y-%m-%d").date()` antes del INSERT/UPDATE
- `created_at`: Pasar el `datetime` directo en lugar de `.isoformat()`

### Fix: sync/routes.py — param since como datetime

**Problema:** Param `since` se convertia a string con `.strftime()` antes de
pasarlo como param SQL contra `sales.timestamp` (TIMESTAMPTZ).

**Solucion:** Pasar el `datetime` directo: `params["since"] = since_dt.replace(tzinfo=None)`

### Fix: conftest.py — seed_employee y rate limiter

**Problema dual:**
1. `NOW()::text` en fixture de empleado rompia INSERT en columna TIMESTAMP
2. Rate limiter de PIN acumulaba intentos entre tests, causando 429 en tests de seguridad

**Solucion:**
1. `NOW()::text` → `NOW()` en seed_employee fixture
2. Nueva funcion `reset_pin_attempts()` en rate_limit.py, llamada en fixture `client`

---

## Resumen de Impacto

### Migraciones

| # | Descripcion | Tablas | Columnas |
|---|---|---|---|
| 035 | TEXT → TIMESTAMP | 5 tablas | 8 columnas |
| 036 | Indices y FK | 5 tablas | 6 indices + 1 FK |
| 037 | Funcion fix_all_sequences | — | Funcion PG |
| 038 | NUMERIC ventas | 2 tablas | 16 columnas |
| 039 | NUMERIC operacional | 9 tablas | 26 columnas |
| 040 | NUMERIC secundario | ~40 tablas | ~75 columnas |
| 041 | Drop columnas duplicadas customers | 1 tabla | 5 columnas eliminadas |

**Total migraciones:** 7 migraciones (035–041)
**Total columnas de tipo corregido:** ~125 columnas
**Total tablas tocadas:** ~57 tablas

### Modulos Python

| Archivo | Tipo | Descripcion |
|---|---|---|
| `modules/shared/pin_auth.py` | NUEVO | Verificacion PIN centralizada |
| `modules/shared/turn_service.py` | NUEVO | Calculo financiero de turno |
| `modules/shared/auth.py` | MOD | JTI revocation + normalize role |
| `modules/shared/rate_limit.py` | MOD | slowapi obligatorio + PIN brute-force |
| `modules/auth/routes.py` | MOD | Rate limit con slowapi |
| `modules/dashboard/routes.py` | MOD | datetime objects nativos |
| `modules/sync/routes.py` | MOD | Endpoint fix-sequences |
| `modules/turns/routes.py` | MOD | Usa shared/pin_auth + turn_service |
| `modules/hardware/routes.py` | MOD | Usa shared/turn_service |
| `modules/sales/routes.py` | MOD | Usa shared/pin_auth, create_sale 400→90 lines |
| `modules/employees/routes.py` | MOD | hire_date string→date, created_at datetime |
| `modules/remote/routes.py` | MOD | Removido ::text cast en query TIMESTAMPTZ |
| `tests/conftest.py` | MOD | Credenciales de env, IDs 90k+, reset rate limiter |

### Seguridad

- **JTI revocation:** Los tokens JWT ahora pueden invalidarse explicitamente en logout
- **Rate limiting obligatorio:** slowapi aplicado en login y endpoints de PIN
- **Brute-force PIN:** Maximo 5 intentos por IP en 5 minutos (PINs de 4 digitos = 10,000 combinaciones)
- **Timing-safe PIN:** `hmac.compare_digest` previene timing attacks en PINs SHA-256 legados
- **Credenciales en tests:** Eliminadas todas las credenciales hardcodeadas de conftest.py

### Calidad de datos

- **Tipos correctos en DB:** Fechas como TIMESTAMP, dinero como NUMERIC — queries de agregacion
  y comparacion de fechas funcionan correctamente sin casts implicitos
- **Indices de rendimiento:** 6 nuevos indices en tablas de alta actividad
- **Integridad referencial:** FK en `inventory_movements.product_id` previene datos huerfanos
- **Secuencias post-sync:** `fix_all_sequences()` corrige el BUG CONOCIDO de duplicate key
  despues de operaciones de sync hub-spoke

---

### Tests

- **Backend:** 177 tests pasando (pytest + httpx, DB real con rollback)
- **Frontend:** 69 tests pasando (vitest)
- **Cero regresiones** despues de aplicar 7 migraciones y 13+ archivos modificados

---

*Generado automaticamente al finalizar la sesion de deuda tecnica — 2026-03-03*
