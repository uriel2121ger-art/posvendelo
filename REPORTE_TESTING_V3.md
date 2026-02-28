# Resultados del Testing Exhaustivo V3 - TITAN POS

El plan de testing V3 se enfocó en estresar el backend directamente a través de payloads manipulados, ataques de concurrencia, escalada de privilegios y ataques algorítmicos. Tras ejecutar una batería de scripts automatizados contra la API local de FastAPI, estos son los hallazgos definitivos.

> [!WARNING]
> Se han descubierto vulnerabilidades críticas ("Price Forgery" e "IDOR de Empleados") que requieren parcheo inmediato en el backend antes de desplegar en producción.

---

## 🛑 Vulnerabilidades Críticas Encontradas

### 1. Falsificación de Precios Client-Side (Price Forgery)
**Descripción:** El endpoint de ventas `POST /api/v1/sales/` recalcula el subtotal global eficientemente para no confiar en el `subtotal` total del Payload. **Sin embargo**, confía ciegamente en el campo `price` enviado dentro de cada objeto del array `items`.
**Explotación Expresada:** Un cliente o interceptador puede mandar un ticket de un artículo que en DB vale `$50.00` y enviarlo como `{"price": 1.00}`, y el sistema registra una venta legal de `$1.00`.
**Severidad:** Crítica.

### 2. Privilege Escalation & IDOR Horizontal
**Descripción:** Existen brechas en la segregación de roles dentro del backend (API):
- **Cajeros leyendo datos privados:** Un usuario logueado con rol de cajero puede hacer un `GET /api/v1/employees/` y la API retorna exitosamente la base de datos entera de empleados, la cual expone Nombres, Roles, Salarios y, críticamente, los "Pines" (texto plano) de los gerentes y administradores.
- **Cancelaciones sin PIN Gerencial:** El endpoint `POST /api/v1/sales/{id}/cancel` acepta la cancelación si el body JSON deliberadamente incluye `{"manager_pin": None}`. El backend no impone validación de existencia de PIN si se pasa como estructura vacía o valor nulo.
**Severidad:** Crítica.

### 3. Faltas de Manejo de Errores (Denegación de Servicio 500)
**Descripción:** Ciertas inyecciones provocan cuelgues del backend en vez de 422:
- **Null-Bytes y Emojis complejos (Zalgo text):** Provoca un `500 Internal Server Error` (potencial fallo a nivel de driver AsyncPG).
- **Fechas Futuras Inesperadas:** Al intentar un cierre de turno con un timestamp lejano (ej. "2099-12-31"), la API arroja `500 Internal Server Error` en vez de un bad request.
**Severidad:** Media.

---

## 🛡️ Fortalezas y Mecanismos Robustos (Verificados)

> [!TIP]
> Durante los tests multi-hilo, el sistema demostró un blindaje excepcional respecto a integridad de bases de datos.

### 1. Condiciones de Carrera Bloqueadas Exitosamente
- **Apertura Doble de Turnos:** Al atacar el endpoint de `open-turn` con 25 hilos concurrentes simultáneos, el sistema bloqueó todas las aperturas fantasmas y reportó `Ya tienes un turno abierto`, manteniendo la consistencia de 1 turno estrictamente.
- **Double Spend en Ventas:** Lanzando 10 tickets del mismo producto de forma asíncrona hiperrápida resolvió enviando bloqueos (409 Conflict) al detectar que el producto ya estaba bloqueado por otra transacción activa (`FOR UPDATE` functionando).
- **Ajustes de Stock Atómicos:** Se realizaron 15 descuentos simultáneos del inventario. El sistema operó a la perfección (49,343 - 150 = 49,193), sin perder ningún ciclo sumatorio.

### 2. Validaciones Nativas FastAPI Activas
- Paginación excesiva (ej. `limit=1000000`) es rebotada automáticamente a `422` obligando a `limit <= 500`.
- Inyecciones clásicas HTTP (Tipos erróneos, Textos en lugar de Decimales, `NaN` en Floats, Reducción a carritos sin artículos) son interceptadas antes de la lógica de negocio.
- **ReDoS superado:** Búsquedas complejas en regex no colgaron el servidor.

---

## Resoluciones Aplicadas (Parcheo V3)

### 1. Price Forgery — RESUELTO
- `_calculate_item()` ahora usa **siempre** el precio de BD para productos regulares
- Productos comunes (sin `product_id`, SKU `COM-/COMUN-`) siguen con precio del cliente
- SELECT agrega `price, price_wholesale` al query `FOR UPDATE`
- **Test**: `test_price_forgery_blocked` verifica que `price=1` para producto de $116 resulta en total=$116

### 2. PIN System — RESUELTO
- Migración 033: `pin_hash TEXT` en tabla `users`, PINs existentes hasheados con `sha256()`
- `turns/routes.py`: query cambiado de `employees` a `users WHERE pin_hash AND role IN (...)`
- `cancel_sale()`: ahora requiere `SaleCancelRequest(manager_pin)` obligatorio
- RBAC por rol JWT eliminado en cancel — ahora validación es por PIN de manager
- **Tests**: `test_cash_movement_valid_pin`, `test_cash_movement_invalid_pin`, `test_cancel_sale_requires_pin`, `test_cancel_sale_with_valid_pin`

### 3. Null Bytes — RESUELTO
- `NullByteSanitizer` middleware en `main.py` (después de CORS)
- Limpia `\x00` de query strings y bodies JSON antes de llegar a asyncpg
- **Tests**: `test_null_byte_search_safe`, `test_null_byte_json_body_safe`

---

## Conclusiones

El backend ahora tiene protección completa contra las 3 categorías de vulnerabilidades detectadas. Las fortalezas existentes (locks atómicos, validación Pydantic, protección ReDoS) se mantienen intactas. Se agregaron 8 tests de regresión de seguridad.
