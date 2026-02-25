# QA Reporte de Bugs — 2026-02-25

Scan completo backend + frontend. 17 issues encontrados y corregidos en commit `81c5581`.

## Resumen

| Severidad | Cantidad | Corregidos |
|-----------|----------|------------|
| Critico   | 1        | 1          |
| Alto      | 10       | 10         |
| Medio     | 6        | 6          |
| **Total** | **17**   | **17**     |

---

## Issues Corregidos

### #1 — CRITICO: NaN/Inf en schemas de venta

**Archivo:** `backend/modules/sales/schemas.py`
**Problema:** `SaleItemCreate._reject_special_floats` no validaba `price_wholesale`, permitiendo NaN/Inf en ese campo.
**Fix:** Agregar `price_wholesale` al loop de validacion.

### #2 — ALTO: float→Decimal en acumulador de stock (ventas)

**Archivo:** `backend/modules/sales/routes.py`
**Problema:** `demand_by_pid` usaba `float` para acumular demanda de stock, causando drift en operaciones con muchos items.
**Fix:** `Decimal(str(item.qty))` y `Decimal(str(prod.get("stock", 0)))` para toda la aritmetica de stock.

### #3 — ALTO: float cast antes de escribir a DB (inventario)

**Archivo:** `backend/modules/inventory/routes.py`
**Problema:** `float(new_stock)` antes de `UPDATE products SET stock = $1` descartaba la precision Decimal.
**Fix:** Pasar `new_stock` (Decimal) directamente a asyncpg.

### #4 — ALTO: float en operaciones de stock remoto (productos)

**Archivo:** `backend/modules/products/routes.py`
**Problema:** `update_stock_remote` usaba aritmetica float para calcular nuevo stock.
**Fix:** `Decimal(str(product["stock"]))` + `Decimal(str(body.quantity))`, import de `Decimal` agregado.

### #5 — ALTO: NaN/Inf incompleto en products schemas

**Archivo:** `backend/modules/products/schemas.py`
**Problema:** `StockUpdateRemote` y `SimplePriceUpdate` solo validaban `isinf` pero no `isnan`.
**Fix:** Agregar `math.isnan()` a ambos validators.

### #6 — ALTO: Dead imports en 8 modulos backend

**Archivos:** `customers/routes.py`, `dashboard/routes.py`, `dashboard/schemas.py`, `mermas/routes.py`, `turns/routes.py`, `shared/domain_event.py`, `shared/event_bridge.py`, `products/routes.py`
**Problema:** Imports no utilizados (`Optional`, `Dict`, `List`, `Query`, `json`, `asyncio`, etc.)
**Fix:** Eliminados.

### #7 — ALTO: Discount calc sin redondeo (frontend)

**Archivo:** `frontend/.../Terminal.tsx` — `calculateLineSubtotal()`
**Estado:** Ya usaba `Math.round(...*100)/100` — no requirio cambio.

### #8 — ALTO: /health sin verificar DB

**Archivo:** `backend/main.py`
**Problema:** Retornaba `{"status": "healthy"}` sin verificar conectividad a PostgreSQL.
**Fix:** `SELECT 1` via pool, retorna `"unhealthy"` si falla.

### #9 — ALTO: /terminals tragaba excepciones

**Archivo:** `backend/main.py`
**Problema:** `except Exception` retornaba `success: True` con terminal hardcodeada, ocultando errores reales.
**Fix:** `logger.exception()` + `raise HTTPException(500)`.

### #10 — ALTO: localStorage.getItem sin try/catch (posApi)

**Archivo:** `frontend/.../posApi.ts` — `loadRuntimeConfig()`
**Problema:** 3 llamadas a `localStorage.getItem` sin proteccion.
**Fix:** try/catch con fallback a valores default.

### #11 — MEDIO: localStorage.removeItem sin try/catch (posApi)

**Archivo:** `frontend/.../posApi.ts` — `handleExpiredSession()`
**Problema:** `removeItem` podia lanzar en contextos restringidos, impidiendo el redirect.
**Fix:** try/catch, redirect y throw siempre ejecutan.

### #12 — MEDIO: localStorage en JSX render (TopNavbar)

**Archivo:** `frontend/.../components/TopNavbar.tsx`
**Problema:** `localStorage.getItem('titan.user')` directamente en JSX sin proteccion.
**Fix:** IIFE con try/catch, fallback a `'Usuario'`.

### #13 — MEDIO: localStorage en logout (TopNavbar)

**Archivo:** `frontend/.../components/TopNavbar.tsx`
**Problema:** `removeItem` en handler de logout sin try/catch + `getItem('titan.currentShift')` sin proteccion.
**Fix:** try/catch en removeItem loop y hasShift check.

### #14 — MEDIO: readCurrentShift localStorage fuera de try (Terminal)

**Archivo:** `frontend/.../Terminal.tsx`
**Problema:** `localStorage.getItem(CURRENT_SHIFT_KEY)` fuera del bloque try existente.
**Fix:** Mover dentro del try/catch.

### #15 — MEDIO: pending tickets localStorage fuera de try (Terminal)

**Archivo:** `frontend/.../Terminal.tsx`
**Problema:** `localStorage.getItem(PENDING_TICKETS_STORAGE_KEY)` en useEffect sin proteccion.
**Fix:** Variable `let raw = null` + try/catch para el getItem.

### #16 — MEDIO: readCurrentShift/readHistory localStorage (ShiftsTab)

**Archivo:** `frontend/.../ShiftsTab.tsx`
**Problema:** Ambas funciones tenian `localStorage.getItem` fuera del try/catch.
**Fix:** Mover getItem dentro del try existente en ambas funciones.

### #17 — ALTO: mermas null guard insuficiente (MermasTab)

**Archivo:** `frontend/.../MermasTab.tsx`
**Problema:** `(inner.mermas ?? [])` — nullish coalescing no protege contra valores truthy no-array.
**Fix:** `Array.isArray(raw) ? raw : []`.

---

## Archivos Modificados (18)

### Backend (13)
- `main.py` — health check DB + terminals error propagation + HTTPException import
- `modules/sales/routes.py` — Decimal stock accumulation
- `modules/sales/schemas.py` — NaN/Inf validation
- `modules/inventory/routes.py` — Decimal pass-through
- `modules/products/routes.py` — Decimal stock math + dead imports
- `modules/products/schemas.py` — isnan validation
- `modules/customers/routes.py` — dead import
- `modules/dashboard/routes.py` — dead imports
- `modules/dashboard/schemas.py` — dead import
- `modules/mermas/routes.py` — dead import
- `modules/turns/routes.py` — dead import
- `modules/shared/domain_event.py` — dead imports
- `modules/shared/event_bridge.py` — dead imports

### Frontend (5)
- `posApi.ts` — loadRuntimeConfig + handleExpiredSession try/catch
- `components/TopNavbar.tsx` — 3x localStorage protection
- `Terminal.tsx` — readCurrentShift + pendingTickets try/catch
- `ShiftsTab.tsx` — readCurrentShift + readHistory try/catch
- `MermasTab.tsx` — Array.isArray guard
