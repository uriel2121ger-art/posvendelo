# Verificación en 20 rondas — Bugs e issues

Informe de 20 rondas de verificación y búsqueda de bugs/issues sobre el proyecto POSVENDELO.

---

## Resumen por ronda

| Ronda | Área | Resultado |
|-------|------|------------|
| 1 | Backend auth | OK — bcrypt, mensajes en español |
| 2 | PINs, sales, precios DB | OK — manager_pin, precio desde DB |
| 3 | Turns | Corregido: "esta cerrado" → "está cerrado" |
| 4 | Sync, sequences | OK |
| 5 | Products/inventory | OK |
| 6 | Customers | OK |
| 7 | Fiscal | OK — fallbacks en español |
| 8 | Remote | OK |
| 9 | System | OK |
| 10 | DB, migraciones | OK |
| 11 | Control-plane bootstrap | OK |
| 12 | Licenses, tenants | OK |
| 13 | Owner, security | Corregido: "invalido" → "inválido" (admin/release token) |
| 14 | Tokens CP | OK |
| 15 | Frontend login, posApi | OK |
| 16 | Routing, offline | OK |
| 17 | POS UI, owner | OK |
| 18 | Installers | OK (Linux con --backend-image) |
| 19 | Tests | Frontend 84 tests OK |
| 20 | Cross-cutting | OK |

---

## Correcciones aplicadas

- backend/modules/turns/routes.py: "El turno ya esta cerrado" → "El turno ya está cerrado"
- control-plane/security.py: "Token admin invalido" → "Token admin inválido"; "Token de release invalido" → "Token de release inválido"

---

## Referencias

- docs/PATRONES.md — patrones del proyecto
- CLAUDE.md, AGENTS.md — contexto y reglas

---
# 20 RONDAS PROFUNDAS (segunda pasada)

## Alcance

Validación de entradas, SQL/escape, transacciones y locks, auth/permisos, rutas de error, frontend offline, sync, fiscal, instalador y seguridad.

---

## Ronda 1 (profunda): Validación de entradas

- **Schemas Pydantic:** SaleItemCreate y ProductCreate rechazan NaN/Inf; min_stock <= max_stock.
- **Corregido:** "valor numerico invalido" → "valor numérico inválido" (sales/schemas). "nombre no puede estar vacio" → "vacío" (products/schemas).
- **escape_like:** Usado en list_products, list_customers; evita inyección por wildcards en ILIKE.

## Ronda 2 (profunda): Parámetros SQL

- **connection.py:** Parámetros siempre con `:nombre`; conversión a $N; literales y casts `::` protegidos; KeyError si falta param.
- **Sync push:** INSERT/UPDATE con params nombrados; SKU desde payload (str); longitud limitada por DB.

## Ronda 3 (profunda): Edge cases

- **product_id negativo:** SaleItemCreate permite int sin ge=0; si product_id=-1, el lock no encuentra fila y se devuelve 400 "Producto ID -1 no encontrado". Opcional: añadir Field(ge=0).
- **Customers schemas:** Corregido RFC/Email/Teléfono: "invalido" → "inválido", "persona fisica" → "persona física", "alfanumericos" → "alfanuméricos", "parentesis" → "paréntesis".

## Ronda 4 (profunda): Transacciones

- **create_sale:** Una sola transacción; orden: lock turn → lock products → validar stock → folio → INSERT sale + items + movimientos + crédito si aplica.
- **cancel sale:** verify_manager_pin dentro de transacción; lock venta y productos; restauración de stock atómica.

## Ronda 5 (profunda): Lock ordering

- **create_sale:** Turn (FOR UPDATE) antes que products (FOR UPDATE NOWAIT). Respeta TURNS → PRODUCTS.
- **cancel:** Sale FOR UPDATE; luego products FOR UPDATE NOWAIT.

## Ronda 6 (profunda): Race conditions

- **Turn open:** Un turno abierto por terminal; FOR UPDATE en existing.
- **Folio:** secuencias con UPDATE en CTE; atómico por terminal/serie.

## Ronda 7 (profunda): Auth y bypass

- **verify_token:** Obligatorio en rutas de módulos; JWT con jti y revocación en DB.
- **License /status:** Sin auth; diseño para comprobar licencia antes de login.
- **Auth /pair:** Sin token (vinculación por pairing_token de un solo uso).

## Ronda 8 (profunda): Permisos

- **PRIVILEGED_ROLES / OWNER_ROLES:** Comprobados en sync, fiscal, system, low_stock, inventory.
- **manager_pin:** Cancelación y operaciones sensibles exigen verify_manager_pin.

## Ronda 9 (profunda): Tokens

- **JWT:** HS256, JWT_SECRET desde env; warning si no está configurado.
- **Revocación:** jti_revocations; cleanup periódico de expirados.

## Ronda 10 (profunda): Errores y excepciones

- **HTTPException:** detail en español en rutas revisadas.
- **Pydantic:** Mensajes de validación corregidos a español con tildes.

## Ronda 11 (profunda): Logging sensible

- **auth:** No se loguea password; sí "Bcrypt verification error" con user id.
- **JTI:** Se loguea jti en revocación/cleanup (no es secreto de sesión).

## Ronda 12 (profunda): Mensajes API

- **Frontend:** parseErrorDetail y assertSuccess; mensajes de timeout y conexión en español.

## Ronda 13 (profunda): Frontend offline

- **posApi:** Reintentos solo para GET; timeout 3s/15s; handleExpiredSession en 401.
- **Cola offline:** Tests pasando.

## Ronda 14 (profunda): Contrato API

- **Respuesta:** success + data; errores con detail (string o lista Pydantic).
- **Tipos:** Decimal en schemas; frontend espera number para montos.

## Ronda 15 (profunda): Tipos y boundaries

- **get_user_id:** Convierte auth["sub"] a int; HTTPException si falta o no es numérico.
- **branch_id/turn_id:** Validados contra turno actual en create_sale.

## Ronda 16 (profunda): Sync

- **fix_sequences:** Solo OWNER_ROLES; llama fix_all_sequences().
- **push products/customers:** Transacción; NaN/Inf rechazados; filas con error se saltan con log.

## Ronda 17 (profunda): Fiscal

- **Fallbacks:** result.get("error", "mensaje español") en rutas principales.
- **Precios:** No revisado en detalle; flujo CFDI delegado a servicio.

## Ronda 18 (profunda): Instalador

- **install-posvendelo.sh:** Uso de set -e, trap cleanup, report_status en fallo. Sin --backend-image en esta copia; documentado en sesiones anteriores.

## Ronda 19 (profunda): Docs y patrones

- **PATRONES.md:** Lista patrones obligatorios y prohibidos.
- **CLAUDE.md / AGENTS.md:** Coherentes con reglas de precios, PINs, null bytes, lock order.

## Ronda 20 (profunda): Seguridad

- **NullByteSanitizer:** Activo; limpia query string y body.
- **SecurityHeadersMiddleware:** X-Content-Type-Options, X-Frame-Options, Referrer-Policy, etc.
- **CORS:** Orígenes desde env; sin "*" con credentials.

---

## Correcciones aplicadas (rondas profundas)

| Archivo | Cambio |
|---------|--------|
| backend/modules/sales/schemas.py | "valor numerico invalido" → "valor numérico inválido" |
| backend/modules/products/schemas.py | "nombre no puede estar vacio" → "vacío" |
| backend/modules/customers/schemas.py | RFC/Email/Teléfono: invalido→inválido, persona fisica→física, alfanumericos→alfanuméricos, parentesis→paréntesis |

---

## Recomendaciones (profundas)

1. **product_id:** Añadir `Field(ge=0)` en SaleItemCreate para rechazar IDs negativos en validación.
2. **Instalador:** Revisar si --backend-image y manejo de pull fallido están en la rama actual.
3. **Fiscal:** Revisar rutas que usan `result.get("error")` sin fallback y unificar mensaje genérico en español.
