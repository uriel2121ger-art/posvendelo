# Investigación a fondo: Internal Server Error al cerrar turno

## 1. Síntoma

Al pulsar **"Cerrar turno"** en el modal `ShiftStartupModal`, el backend respondía **500 Internal Server Error** y el turno no se cerraba.

---

## 2. Flujo afectado

1. **Frontend:** `ShiftStartupModal` → `handleCloseSubmit` → `closeTurn(cfg, turnId, { final_cash })` (posApi.ts).
2. **Backend:** `POST /api/v1/turns/{turn_id}/close` → `close_turn()` en `modules/turns/routes.py`.
3. **Base de datos:** `UPDATE turns SET ... end_timestamp = $6 ... WHERE id = $7`.

El fallo ocurría en el `conn.execute()` del `UPDATE`, al enlazar el parámetro correspondiente a `end_timestamp`.

---

## 3. Comportamiento de asyncpg con fechas/hora

### 3.1 Fuentes (issues y código)

- **Issue #138** (asyncpg): al pasar un **datetime con timezone** (aware) a un parámetro tipado como `::TIMESTAMP` (sin TZ), asyncpg falla con:
  ```text
  TypeError: can't subtract offset-naive and offset-aware datetimes
  ```
  (asyncpg/protocol/codecs/datetime.pyx). Para `$1::TIMESTAMP`, el codec espera un valor que pueda convertir a “timestamp sin zona”; internamente hace operaciones que mezclan naive y aware y disparan ese error.

- **Issue #791** (asyncpg + SQLAlchemy): el tipo del parámetro debe coincidir con la columna. Si el driver/ORM infiere `TIMESTAMP` (sin TZ) y se pasa un aware, mismo error. Si se declara explícitamente `TIMESTAMP(timezone=True)` (TIMESTAMPTZ), los datetimes aware funcionan.

- **Documentación / convención**:
  - Columna **TIMESTAMP WITHOUT TIME ZONE** → pasar **datetime naive** (sin `tzinfo`) para evitar el error del codec.
  - Columna **TIMESTAMP WITH TIME ZONE** → pasar **datetime aware** (p. ej. `datetime.now(timezone.utc)`).

### 3.2 Paradoja en nuestro caso

En nuestro código estábamos pasando un **datetime naive**:

```python
now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive
# ...
end_timestamp = $6  # now
```

y aun así obtuvimos **"can't subtract offset-naive and offset-aware datetimes"**.

Hipótesis coherente con el codec de asyncpg:

- El codec que escribe un valor en una columna `TIMESTAMP` (sin TZ) puede usar la **zona horaria de la sesión** (o del servidor) para normalizar.
- Esa zona suele estar representada como **aware** en Python.
- Si en esa normalización se hace algo del estilo “restar offset” o “convertir a sesión”, se mezcla nuestro valor **naive** con un valor **aware** y se produce el `TypeError`.

Por tanto el bug no es solo “aware a TIMESTAMP”, sino que **cualquier paso de un datetime Python a una columna TIMESTAMP (sin TZ)** puede tocar esa ruta del codec y, según versión de asyncpg y de Python, fallar. La única forma totalmente segura que no depende del codec es **no enviar un datetime desde Python** para ese campo.

### 3.3 Envío de string

Al enviar un **string** (p. ej. `'2026-03-04 04:36:33'`) con `$6::timestamp`:

```text
asyncpg.exceptions.DataError: invalid input for query argument $6: '2026-03-04 04:36:33'
(expected a datetime.date or datetime.datetime instance, got 'str')
```

Para parámetros de tipo fecha/hora, asyncpg espera **objetos `date` o `datetime`**; no acepta `str` en este camino de binding (no hay parsing automático en ese punto).

---

## 4. Patrón seguro: usar NOW() / CURRENT_TIMESTAMP en SQL

Para **escribir** la hora actual en columnas `TIMESTAMP` o `TIMESTAMPTZ` sin tocar el codec de asyncpg:

- **No** pasar desde Python ni `datetime` ni `str` para ese campo.
- En el SQL usar la función del servidor: **`NOW()`** o **`CURRENT_TIMESTAMP`**.

Ventajas:

- No se usa el codec de datetime de asyncpg para ese parámetro → se evita el bug naive/aware y el rechazo de strings.
- La hora es la del servidor PostgreSQL, coherente con el resto de la BD.
- Mismo criterio que en otras partes del proyecto (gastos, reportes, etc.) que ya usan `CURRENT_TIMESTAMP` / `NOW()` en SQL.

### 4.1 Dónde se aplicó en este proyecto

| Archivo | Operación | Columna | Cambio |
|--------|-----------|---------|--------|
| `modules/turns/routes.py` | `close_turn` | `turns.end_timestamp` | `end_timestamp = NOW()` en el `UPDATE`; se deja de enviar un parámetro datetime. |
| `modules/turns/routes.py` | `open_turn` | `turns.start_timestamp` | `VALUES (..., NOW(), 0)` en el `INSERT`; se deja de enviar un parámetro datetime. |
| `modules/turns/routes.py` | registro de movimiento de caja | `cash_movements.timestamp` | `VALUES (..., NOW())` en el `INSERT`; se deja de enviar un parámetro datetime. |

Además se eliminó el import no usado de `datetime` y `timezone` en `turns/routes.py`.

---

## 5. Regla para el codebase (patrón del bug)

**Regla:** Al escribir en columnas **TIMESTAMP** (con o sin time zone) con **asyncpg**, evitar pasar un `datetime` (o string) desde Python para el “momento actual”. Usar en el SQL `NOW()` o `CURRENT_TIMESTAMP`.

**Puntos de riesgo** (otros sitios que hoy pasan `datetime` a asyncpg para columnas de timestamp):

- **`modules/expenses/routes.py`** – `register_expense`: inserta en `cash_movements` con `:now` (naive). Mismo tipo de columna que el movimiento de caja en turns; podría sufrir el mismo fallo según versión/entorno. Recomendación: usar `NOW()` en el `INSERT` y quitar el parámetro `now`.
- **`modules/sales/saga.py`** – usa `now` naive en escrituras. Revisar si esas columnas son TIMESTAMP sin TZ y, si es “hora actual”, valorar usar `NOW()` en SQL.
- **`modules/employees/routes.py`** – usa `now` naive. Revisar columnas afectadas y aplicar el mismo criterio.

No hace falta cambiar lecturas: al **leer**, asyncpg devuelve naive para `TIMESTAMP` y aware para `TIMESTAMPTZ`; eso no dispara el bug.

---

## 6. Esquema y convenciones del proyecto

- **turns:** `start_timestamp` y `end_timestamp` son **TIMESTAMP** (sin TZ) en schema.sql y en migración 032.
- **cash_movements:** `timestamp` es **TIMESTAMP** (sin TZ) (migración 032).
- **sales:** `timestamp` pasó a **TIMESTAMPTZ** en migración 035; para escrituras con timezone se puede seguir pasando datetime aware o usar `NOW()` según diseño.

En comentarios del repo ya se documenta: para columnas TIMESTAMP sin TZ “pass naive datetimes”; para TIMESTAMPTZ, datetime con timezone. El bug muestra que, al **escribir** en TIMESTAMP sin TZ, incluso el naive puede fallar por la lógica interna del codec, por eso se fija la regla de usar `NOW()` para “hora actual”.

---

## 7. Resumen de errores observados (orden cronológico)

| Intento | Qué se pasaba | Error |
|--------|----------------|-------|
| 1 | `datetime` naive (`replace(tzinfo=None)`) | `can't subtract offset-naive and offset-aware datetimes` |
| 2 | String ISO (`now_str`) con `$6::timestamp` | `expected a datetime.date or datetime.datetime instance, got 'str'` |
| 3 | **Solución** | `end_timestamp = NOW()` en SQL, sin parámetro desde Python → sin error |

---

## 8. Referencias

- [asyncpg #138](https://github.com/MagicStack/asyncpg/issues/138) – error al pasar datetime aware a `::TIMESTAMP`.
- [asyncpg #791](https://github.com/MagicStack/asyncpg/issues/791) – tipo del parámetro (TIMESTAMP vs TIMESTAMPTZ) y SQLAlchemy.
- Comentarios en repo: `modules/dashboard/routes.py` (cash_movements vs sales timestamp), `modules/expenses/routes.py` (naive para TIMESTAMP).
- Migraciones: `032_fix_timestamp_text_columns.sql`, `035_timestamp_text_to_timestamp.sql`.
- asyncpg: codec en `protocol/codecs/datetime.pyx` (encode para parámetros de tipo timestamp).

---

## 9. Cómo verificar la corrección

1. Reconstruir y levantar la API:  
   `docker compose up -d --build api`
2. En el frontend: abrir turno, cerrar turno (botón “Cerrar turno” con efectivo en caja).
3. Comprobar respuesta 200 y en BD que el turno tenga `status = 'closed'` y `end_timestamp` no nulo.
4. Opcional: registrar un movimiento de caja en un turno abierto y comprobar que el `INSERT` con `NOW()` en `cash_movements.timestamp` funciona sin 500.
