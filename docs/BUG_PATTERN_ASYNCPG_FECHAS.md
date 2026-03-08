# Patrón de bug: asyncpg y tipos fecha/hora

Este documento resume **dos patrones** de error con asyncpg y parámetros de fecha/hora en TITAN POS, y cómo están mitigados.

---

## 1. Parámetros DATE: `toordinal` / `invalid input for query argument`

### Síntoma

```text
asyncpg.exceptions.DataError: invalid input for query argument $1: '2026-03-05'
('str' object has no attribute 'toordinal')
```

### Causa

- En PostgreSQL, cuando un parámetro se usa en un **contexto DATE** (columna `DATE`, o en SQL `CAST(... AS DATE)`, `::date`, `BETWEEN :d1 AND :d2` con comparación a fecha), asyncpg espera un objeto **`datetime.date`** de Python.
- Si se pasa un **`str`** (p. ej. `'2026-03-05'`), el codec de asyncpg intenta usar el valor y en algún punto se llama `.toordinal()`, que solo existe en `date`/`datetime`, no en `str` → **DataError**.

### Dónde ocurre

Cualquier consulta que enlace un parámetro a un tipo DATE, por ejemplo:

| Archivo | Consulta / uso | Params |
|---------|----------------|--------|
| `modules/fiscal/global_invoicing.py` | `CAST(s.timestamp AS DATE) BETWEEN :d1 AND :d2` | `d1`, `d2` (ya parseados con `_parse_date`) |
| `modules/fiscal/returns_engine.py` | `created_at::date BETWEEN :d1 AND :d2` | `d1`, `d2` (ya `datetime.strptime(..., '%Y-%m-%d').date()`) |
| `modules/fiscal/cfdi_sync_service.py` | `fecha_emision::date BETWEEN :d1::date AND :d2::date` | `d1`, `d2` (strings; mitigado en capa DB) |
| `modules/fiscal/smart_withdrawal.py` | `expense_date >= :m_start::date` | `m_start` (string `YYYY-MM-DD`; mitigado en capa DB) |
| `modules/fiscal/liquidity_bridge.py` | `expense_date >= :ys::date`, `created_at::date = :today` | `ys`, `ye`, `today`, `week_start` (algunos ya `.date()`, otros string; mitigado en capa DB) |

### Mitigación actual

1. **En módulos concretos:** Convertir a `date` antes de pasar al driver:
   - `global_invoicing.py`: `_parse_date(start_date)` → `date`.
   - `returns_engine.py`: `datetime.strptime(start, '%Y-%m-%d').date()`.
   - `liquidity_bridge.py`: `datetime.strptime(today, '%Y-%m-%d').date()` donde aplica.

2. **En la capa DB (`db/connection.py`):** En `_named_to_positional`, cualquier argumento que sea **string** con forma `YYYY-MM-DD` (o inicio ISO `YYYY-MM-DDT...`) se convierte a `datetime.strptime(..., "%Y-%m-%d").date()` antes de pasarlo a asyncpg. Así, cualquier ruta que siga pasando un string de fecha en un contexto DATE queda cubierta.

### Regla para nuevo código

- Si un parámetro se usa en un **contexto DATE** (columna DATE, `::date`, `CAST(... AS DATE)`), pasar siempre un **`datetime.date`** (p. ej. `datetime.strptime(s, '%Y-%m-%d').date()`), no un `str`.
- No confiar en que “el frontend envía YYYY-MM-DD” sin convertir en backend.

---

## 2. Parámetros TIMESTAMP: naive/aware y strings

### Síntoma

- `TypeError: can't subtract offset-naive and offset-aware datetimes` (codec asyncpg).
- O bien: `expected a datetime.date or datetime.datetime instance, got 'str'`.

### Causa

- Columnas **TIMESTAMP** (sin zona): el codec de asyncpg puede mezclar valores naive/aware y fallar.
- Para “ahora”, pasar `datetime` o `str` desde Python es frágil; asyncpg no convierte strings a datetime en ese camino.

### Mitigación

- **No** pasar `datetime` ni `str` desde Python para “el momento actual”.
- En SQL usar **`NOW()`** o **`CURRENT_TIMESTAMP`** para escribir en columnas TIMESTAMP/TIMESTAMPTZ.

Documentación detallada: **`docs/bug-investigation-cierre-turno-500.md`** (cierre de turno, `end_timestamp`, movimientos de caja, etc.).

---

## 3. Resumen de issues / referencias

| Tema | Referencia |
|------|------------|
| asyncpg datetime aware → TIMESTAMP | [asyncpg #138](https://github.com/MagicStack/asyncpg/issues/138) |
| Tipo TIMESTAMP vs TIMESTAMPTZ en parámetros | [asyncpg #791](https://github.com/MagicStack/asyncpg/issues/791) |
| Cierre de turno 500 (TIMESTAMP) | `docs/bug-investigation-cierre-turno-500.md` |
| CFDI global / reportes (DATE toordinal) | Este doc + `db/connection.py` (normalización de params) |

---

## 4. Checklist al tocar consultas con fechas

- [ ] ¿El parámetro se usa en un contexto **DATE**? → Pasar `date` (o confiar en la normalización en `connection.py` para strings `YYYY-MM-DD`).
- [ ] ¿Se escribe “ahora” en una columna **TIMESTAMP**? → Usar `NOW()` / `CURRENT_TIMESTAMP` en SQL, no parámetro desde Python.
- [ ] ¿Se lee una fecha de la API (query params, body)? → Convertir a `date` en backend antes de usarla en una consulta con tipo DATE.

---

## 5. Issues / puntos de atención

- **Normalización en `connection.py`:** Convierte cualquier param que *parezca* `YYYY-MM-DD` (incl. `YYYY-MM-DDTHH:MM:SS`) a `date`. Si ese param se usa en una columna **TIMESTAMP** (no DATE), se pierde la hora. Hoy los usos conocidos con `::date` o `CAST(... AS DATE)` están bien; si en el futuro se pasa el mismo param a una columna TIMESTAMP, valorar no normalizar ahí o pasar `datetime` desde el módulo.
- **CFDI individual:** No usa rangos DATE en consultas; solo INSERT/UPDATE con columnas TIMESTAMP. No se ha observado el error toordinal en ese flujo.
- **Auditoría:** Revisar cualquier nuevo endpoint que reciba `start_date`/`end_date` (o similar) y los use en SQL: asegurar que se conviertan a `date` en el módulo o que el valor sea ya `date` antes de llegar a la DB.
- **Dashboard (`modules/dashboard/routes.py`):** `get_ai_dashboard` pasa `thirty_days_ago` (datetime con timezone) a `timestamp >= :since_date`. Es **lectura** (WHERE), no escritura. El codec naive/aware puede afectar según entorno; si en algún entorno se viera error, valorar usar `NOW() - INTERVAL '30 days'` en SQL en lugar de parámetro desde Python.

---

## 6. Revisión ampliada — módulos con parámetros fecha

| Módulo | Uso de fechas en consultas | Estado |
|--------|----------------------------|--------|
| `global_invoicing.py` | `:d1`, `:d2` en BETWEEN DATE | ✅ `_parse_date()` en módulo |
| `returns_engine.py` | `:d1`, `:d2` en BETWEEN DATE | ✅ `strptime(...).date()` |
| `cfdi_sync_service.py` | `:d1`, `:d2` en BETWEEN fecha_emision::date | ✅ Normalizer en `connection.py` |
| `smart_withdrawal.py` | `:m_start` en expense_date::date, extraction_date | ✅ Normalizer (string YYYY-MM-DD) |
| `liquidity_bridge.py` | `:ys`, `:ye`, `:today`, `:week_start` en ::date | ✅ Mix de `.date()` en módulo + normalizer |
| `cash_flow_manager.py` | `:ys`, `:ye` en extraction_date; `:dt`, `:ts` en INSERT | ✅ Normalizer para ys/ye; INSERT usa string en tabla que puede ser TEXT (schema dinámico) |
| `enterprise_dashboard.py` | `:ys`, `:ye` en extraction_date, timestamp | ✅ Normalizer para comparaciones DATE |
| `fiscal_forecast.py` | `:ms` en purchase_date, created_at, timestamp | ✅ Normalizer (month_start_str YYYY-MM-DD) |
| `wealth_dashboard.py` | `:df` en TO_CHAR(extraction_date::timestamp,'YYYY-MM') = :df | ✅ :df es string tipo "2025-03", no param DATE |
| `reconciliation_monitor.py` | `:df`, `:year` en TO_CHAR/EXTRACT | ✅ :df string, :year int; no param DATE |
| `sales/routes.py` | start_date/end_date en timestamp >= / < | ✅ `date.fromisoformat` + datetime con tz para params |
| `employees/routes.py` | hire_date en INSERT/UPDATE | ✅ `strptime(..., '%Y-%m-%d').date()` en módulo |
| `dashboard/routes.py` | thirty_days_ago en timestamp >= :since_date | ⚠️ datetime con tz; ver punto de atención arriba |

### Posibles escrituras TIMESTAMP con string (`:ts` / `:now`)

Varios módulos hacen `INSERT` con `created_at` o `timestamp` usando `:ts` = `datetime.now().isoformat()` (string). Si la columna en BD es **TIMESTAMP**, asyncpg puede devolver `expected a datetime.date or datetime.datetime instance, got 'str'`. La mitigación recomendada (como en `bug-investigation-cierre-turno-500.md`) es usar **`NOW()`** o **`CURRENT_TIMESTAMP`** en el SQL y no pasar el valor desde Python. Archivos a revisar si se observan fallos al insertar:

- `modules/fiscal/cash_flow_manager.py` — `related_persons.created_at`, `cash_extractions.created_at` (el módulo crea tablas con `created_at TEXT`; si se usa el schema principal con TIMESTAMP, conviene cambiar a NOW()).
- `modules/fiscal/dual_inventory.py` — `shadow_movements.created_at`.
- `modules/fiscal/self_consumption.py` — `self_consumption.created_at`.
- `modules/fiscal/cfdi_service.py` — `shadow_movements.created_at`.
- `modules/fiscal/shrinkage_tracker.py` — `loss_records` (created_at).
- `modules/fiscal/reconciliation_monitor.py` — `personal_expenses.created_at`.
- `modules/fiscal/transaction_normalizer.py` — ventas `timestamp`.
- `modules/fiscal/liquidity_bridge.py` — ya usa `NOW()` y `CURRENT_DATE` en el INSERT de `cash_expenses`.
