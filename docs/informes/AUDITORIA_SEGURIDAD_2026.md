# Auditoría de seguridad — POSVENDELO

**Fecha:** 2026-03-12  
**Alcance:** Backend (FastAPI), control-plane, frontend (Electron/React).  
**Criterios:** OWASP Top 10, reglas de proyecto (CLAUDE.md/AGENTS.md), autenticación, SQL, CORS, rate limiting, NullByteSanitizer, licencia, headers de seguridad.

---

## Resumen ejecutivo

| Área        | Estado   | Hallazgos críticos | Altos | Medios | Bajos |
|------------|----------|--------------------|-------|--------|-------|
| Backend    | Correcto | 0                  | 0     | 0      | 1     |
| Control-plane | Correcto | 0               | 0     | 0      | 1     |
| Frontend   | Correcto | 0                  | 0     | 0      | 1     |
| OWASP Top 10 | Correcto | 0               | 0     | 0      | 0     |

**Conclusión:** No se identificaron vulnerabilidades críticas ni altas. Las reglas de negocio (precio desde DB, cancelación con manager_pin, NullByteSanitizer activo, sin credenciales hardcodeadas) se cumplen. Los hallazgos son menores y de mejora.

---

## 1. Backend (FastAPI)

### 1.1 Autenticación JWT

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Secreto desde env | `backend/modules/shared/auth.py` | `JWT_SECRET` / `SECRET_KEY` desde `os.getenv`; fallback con warning si no está definido. |
| Algoritmo | `backend/modules/shared/auth.py` | `ALGORITHM = "HS256"`. |
| Claims obligatorios | `backend/modules/shared/auth.py` | `sub`, `role`, `jti` validados; rechazo si falta `jti`. |
| Expiración | `backend/modules/shared/auth.py` | `TOKEN_EXPIRE_MINUTES = 60`. |

**Resultado:** Correcto.

### 1.2 Revocación JTI

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Tabla de revocaciones | `backend/db/schema.sql`, migración `046_jti_revocations.sql` | Tabla `jti_revocations` con `jti`, `expires_at`. |
| Logout persiste JTI | `backend/modules/auth/routes.py` (logout) | Llama a `revoke_token(jti, expires_at)`. |
| Verificación en cada request | `backend/modules/shared/auth.py` | `verify_token` llama a `is_token_revoked(jti)` antes de aceptar el token. |
| Limpieza de expirados | `backend/main.py` (lifespan) | Tarea `_jti_cleanup_loop` ejecuta `cleanup_expired_revocations()`. |

**Resultado:** Correcto.

### 1.3 PINs (bcrypt / SHA-256 legado)

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Verificación | `backend/modules/shared/pin_auth.py` | `verify_manager_pin`: bcrypt para `$2b$`/`$2a$`; SHA-256 con `hmac.compare_digest` para legado. |
| Timing | `pin_auth.py` | Itera todos los usuarios; no early return para evitar enumeración por tiempo. |
| Uso en cancelación | `backend/modules/sales/routes.py` (cancel) | `verify_manager_pin(body.manager_pin, conn)` antes de cancelar. |
| Rate limit PIN | `backend/modules/shared/rate_limit.py` | `check_pin_rate_limit(client_ip)`: 5 intentos / 5 min por IP (10 en DEBUG). |

**Resultado:** Correcto; regla "cancelaciones siempre con manager_pin" cumplida.

### 1.4 Rate limiting

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Global | `backend/main.py` | slowapi con `_get_real_client_ip` (ignora X-Forwarded-For). Límite por defecto 5/min (25/min en DEBUG). |
| Login | `backend/modules/auth/routes.py` | `limiter.limit(_login_rate)` con `LOGIN_RATE_LIMIT` (30/min prod, 120/min debug). |
| PIN | `check_pin_rate_limit` en cancel y rutas fiscales | 5 intentos / 5 min por IP. |
| needs-setup | `backend/modules/auth/routes.py` | `limiter.limit("10/minute")`. |

**Resultado:** Correcto.

### 1.5 CORS

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Orígenes | `backend/main.py` | `CORS_ALLOWED_ORIGINS` (CSV); fallback desde `POSVENDELO_DEV_*` y detección LAN. |
| Credentials | `backend/main.py` | `allow_credentials=False` si hay `*` en orígenes (evita violación del estándar). |
| Origen null | `backend/main.py` | Comentario explícito: no se permite `null` para evitar bypass en file://. |

**Resultado:** Correcto.

### 1.6 Parámetros SQL (asyncpg, sin concatenar)

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Wrapper DB | `backend/db/connection.py` | `_named_to_positional` convierte `:name` a $N; literales y `::` manejados de forma segura. |
| Búsquedas ILIKE | Varios módulos | Uso de `escape_like(search)` y parámetros nombrados (ej. `params["search"] = f"%{escape_like(search)}%"`). |
| SET dinámicos | products, customers, hardware, cfdi | Columnas construidas desde whitelists (`_ALLOWED_COLUMNS`, `_CFDI_ALLOWED_COLS`, `_HW_COLUMNS`). |
| global_invoicing | `backend/modules/fiscal/global_invoicing.py` | `IN (placeholders)` con diccionario de IDs; sin concatenar entrada de usuario. |

**Resultado:** Correcto; no se encontró concatenación de entrada de usuario en SQL.

### 1.7 Credenciales y secretos

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| JWT_SECRET | `backend/modules/shared/auth.py` | Solo desde env; warning si falta. |
| CSD_MASTER_KEY | `backend/modules/fiscal/csd_vault.py` | Desde `os.getenv('CSD_MASTER_KEY')`; comentario explícito de no usar valor por defecto hardcodeado. |
| Contraseñas de usuario | `backend/modules/auth/routes.py` | bcrypt; hash no expuesto en respuestas. |

**Resultado:** Correcto.

### 1.8 NullByteSanitizer

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Middleware | `backend/main.py` | Clase `NullByteSanitizer`: limpia `%00` y `\x00` en query string y body (incl. `\u0000` en JSON). |
| Orden | `backend/main.py` | Añadido antes de otros middlewares de aplicación. |

**Resultado:** Activo y correcto.

### 1.9 LicenseEnforcementMiddleware y SecurityHeadersMiddleware

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| LicenseEnforcementMiddleware | `backend/main.py` | Bloquea con 402 cuando licencia restringida; rutas exentas: `/health`, login, verify, license/status, docs. |
| SecurityHeadersMiddleware | `backend/main.py` | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `X-XSS-Protection`, `Permissions-Policy`. |

**Resultado:** Correcto.

### 1.10 Precio desde DB (regla de negocio)

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Creación de venta | `backend/modules/sales/routes.py` | `_calculate_item`: productos con `product_id` usan siempre precio de `locked_map` (DB); solo productos comunes/SKU COM- usan precio del cliente. |

**Resultado:** Correcto; no se confía en `item.price` del cliente cuando hay `product_id`.

### 1.11 Hallazgo backend (bajo)

| Severidad | Categoría | Archivo:línea | Descripción | Recomendación |
|-----------|-----------|----------------|-------------|----------------|
| Baja | Documentación / consistencia | `backend/modules/system/routes.py:184` | El plan de restore devuelve un array `commands` con un ejemplo de `pg_restore` que usa host y usuario fijos (`127.0.0.1`, `posvendelo_user`). No se ejecuta en servidor, es solo guía. | Opcional: construir la línea de comando desde `DATABASE_URL` o variables de entorno para no sugerir credenciales/host fijos en la documentación. |

---

## 2. Control-plane

### 2.1 Tokens admin y release

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Admin | `control-plane/security.py` | `verify_admin`: token desde `CP_ADMIN_TOKEN`; comparación con `hmac.compare_digest`. |
| Release | `control-plane/security.py` | `verify_release_publisher`: token desde `CP_RELEASES_TOKEN`; mismo patrón. |
| Arranque | `control-plane/main.py` | No se exige token en arranque; rutas sensibles usan `Depends(verify_admin)` o equivalente. |

**Resultado:** Correcto.

### 2.2 Bootstrap y endpoints públicos

| Endpoint | Auth | Comentario |
|----------|------|------------|
| `GET /api/v1/branches/bootstrap-config` | Query `install_token` (obligatorio) | El token actúa como secreto; sin token no se devuelve config. Diseño aceptable. |
| `GET /api/v1/branches/compose-template` | Query `install_token` | Igual; 404 si token inválido. |
| `GET /api/v1/licenses/resolve` | Query/header `install_token` | Rate limit 20/min; requiere install_token. |
| `POST /api/v1/heartbeat` | `Depends(verify_install_token)` | No público. |
| `GET /api/v1/releases/resolve` | Ninguno | Público; parámetros opcionales `branch_id`, `platform`, `artifact`. Devuelve metadatos de release, no secretos. |
| `GET /api/v1/releases/manifest` | `branch_id` o `install_token` | Requiere uno de los dos; sin auth adicional (el token identifica sucursal). |
| `GET /api/v1/cloud/discover` | Ninguno | Público; solo URLs y versión. Por diseño. |

**Resultado:** Correcto; endpoints que requieren install_token o admin están protegidos.

### 2.3 Hallazgo control-plane (bajo)

| Severidad | Categoría | Archivo:línea | Descripción | Recomendación |
|-----------|-----------|----------------|-------------|----------------|
| Baja | Control de acceso / información | `control-plane/modules/releases/routes.py`: `GET /resolve` | Cualquiera puede llamar con `branch_id` opcional y obtener metadatos de release (canal, versiones). No expone secretos. | Opcional: rate limit específico o exigir `install_token` si se quiere limitar quién consulta por branch. |

---

## 3. Frontend

### 3.1 Almacenamiento del token

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Dónde se guarda | `frontend/src/renderer/src/posApi.ts`, Login, etc. | `localStorage` (`pos.token`, `pos.baseUrl`, `pos.terminalId`, etc.). |
| Limpieza en 401 | `frontend/src/renderer/src/posApi.ts` | `handleExpiredSession()` elimina `pos.token`, `pos.user`, `pos.currentShift` y redirige a login. |
| Logout | `posApi.ts`, TopNavbar | `serverLogout()` revoca JTI en backend y luego se limpia localStorage. |

**Riesgo conocido:** En contexto web, localStorage es accesible por script si hubiera XSS. En Electron la superficie es menor; en el código revisado no se inyecta HTML desde datos de usuario (sin uso de APIs que permitan inyección de markup).

**Resultado:** Aceptable; regla de no exponer secretos en código cumplida. Mejora opcional: usar safeStorage de Electron para el token si la API lo permite.

### 3.2 Llamadas API y validación

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Cabecera de auth | `frontend/src/renderer/src/posApi.ts` | `Authorization: Bearer` con token de `loadRuntimeConfig()`. |
| 401 | `posApi.ts` | `apiFetchOnce`: si `res.status === 401` se llama `handleExpiredSession()`. |
| Formato de respuestas | `posApi.ts` | `assertSuccess` para cuerpo con `success: false`; `parseErrorDetail` para mensajes de error. |
| Timeout | `posApi.ts` | AbortSignal.timeout en logout; timeouts en `apiFetch`. |

**Resultado:** Correcto; no se encontraron llamadas API sin validación de sesión o manejo de 401.

### 3.3 Sanitización y XSS

| Aspecto | Ubicación | Estado |
|---------|-----------|--------|
| Caracteres de control en inputs | Terminal, InventoryTab, App, CustomersTab, EmployeesTab | `replace` de rango de caracteres de control en campos de búsqueda. |
| CSV | `frontend/src/renderer/src/utils/csv.ts` | Eliminación de caracteres de control y escape de celdas. |
| React | Búsqueda en código | No se usa inyección de HTML desde datos de usuario. |

**Resultado:** Correcto.

### 3.4 Hallazgo frontend (bajo)

| Severidad | Categoría | Archivo:línea | Descripción | Recomendación |
|-----------|-----------|----------------|-------------|----------------|
| Baja | Almacenamiento | Frontend: `localStorage` para `pos.token` | Riesgo teórico de robo de token por XSS. En Electron y sin vectores XSS detectados el riesgo es bajo. | Documentar la decisión; si en el futuro se refuerza seguridad, valorar Electron safeStorage para token. |

---

## 4. OWASP Top 10 (revisión breve)

| Riesgo | Comprobación | Resultado |
|--------|----------------|-----------|
| Inyección SQL | Parámetros nombrados, `escape_like` en ILIKE, SET/columnas desde whitelists. | Correcto. |
| XSS | Sin inyección de HTML desde datos de usuario; sanitización de caracteres de control en inputs. | Correcto. |
| CSRF | API con Bearer en cabecera; CORS restringe orígenes; app Electron. | Aceptable. |
| Exposición de datos sensibles | Secretos desde env; hashes y PINs no devueltos; install_token solo en server-to-server. | Correcto. |
| Auth bypass | `verify_token`/Depends en rutas sensibles; JTI revocado en logout; manager_pin en cancelación. | Correcto. |
| Configuración incorrecta | CORS y credentials configurados; null origin no permitido; security headers. | Correcto. |
| Componentes vulnerables | No evaluado en esta auditoría (requiere escaneo de dependencias). | Fuera de alcance. |

---

## 5. Reglas del proyecto (CLAUDE.md / AGENTS.md)

| Regla | Verificación | Estado |
|-------|----------------|--------|
| Nunca confiar en `item.price` del cliente si hay `product_id` | `backend/modules/sales/routes.py`: precio desde `locked_map` (DB) para no comunes. | Cumplida. |
| Cancelaciones siempre con `manager_pin` | Cancelación de venta y rutas remotas exigen `verify_manager_pin`. | Cumplida. |
| NullByteSanitizer activo | Middleware en `backend/main.py` activo. | Cumplida. |
| No hardcodear credenciales ni IPs | Secretos desde env; IPs en ejemplos/restore son documentación (ver hallazgo bajo). | Cumplida. |

---

## 6. Resumen de hallazgos y prioridad de corrección

- **Críticos / Altos:** 0.  
- **Medios:** 0.  
- **Bajos:** 3 (consistencia de documentación restore, opcional endurecer releases/resolve, documentar uso de localStorage para token).

**Acciones recomendadas (opcionales):**

1. **Backend:** En `backend/modules/system/routes.py`, construir la línea de ejemplo de `pg_restore` a partir de `DATABASE_URL` o variables de entorno.
2. **Control-plane:** Valorar rate limit o requisito de `install_token` en `GET /api/v1/releases/resolve` si se quiere limitar consultas por branch.
3. **Frontend:** Documentar en desarrollo/seguridad el uso de localStorage para el token y la posibilidad futura de usar Electron safeStorage.

---

*Auditoría realizada según alcance indicado; no incluye pruebas de penetración ni escaneo automatizado de dependencias.*
