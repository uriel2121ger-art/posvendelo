# Auditoría completa del proyecto — TITAN POS

Revisión exhaustiva de backend, control-plane, frontend, instaladores, DB, tests y documentación.

---

## 1. Backend

### 1.1 Módulos revisados
- **auth:** Login bcrypt, rate limit, mensajes "Credenciales inválidas". Logout con revoke JTI.
- **sales:** Precio desde DB para productos no comunes; cancelación con manager_pin; lock ordering TURNS→PRODUCTS; validación stock; folio atómico. SaleItemCreate con product_id Field(ge=0).
- **turns:** NOW() para start_timestamp; mensaje "El turno ya está cerrado".
- **products, customers, inventory:** Parámetros SQL nombrados; escape_like en búsquedas; columnas explícitas para cashier.
- **sync:** fix_sequences para OWNER_ROLES; push con transacción; mensajes en español.
- **fiscal:** Fallbacks de error en español; múltiples rutas con result.get("error"). Servicios internos (timezone_handler, cfdi_service, xml_ingestor, global_invoicing) con mensajes "inválido" corregidos.
- **remote, system, dashboard, employees, expenses, mermas, hardware, sat:** Rutas con verify_token; mensajes en español; schemas con validación.

### 1.2 Schemas (Pydantic) — correcciones aplicadas
| Archivo | Cambio |
|---------|--------|
| sales/schemas.py | valor numérico inválido; product_id Field(None, ge=0) |
| products/schemas.py | nombre vacío → vacío |
| customers/schemas.py | RFC/Email/Teléfono inválido, persona física, alfanuméricos, paréntesis |
| employees/schemas.py | Email/Teléfono inválido, vacío, número finito, paréntesis |
| expenses/schemas.py | número finito, descripción no puede estar en blanco |
| fiscal (varios) | timestamp/fecha/RFC/XML inválido → inválido con tilde |

### 1.3 DB y seguridad
- **connection.py:** Parámetros :nombre → $N; escape_like para ILIKE; DATABASE_URL obligatoria.
- **NullByteSanitizer:** Activo en main.py.
- **SecurityHeadersMiddleware:** X-Content-Type-Options, X-Frame-Options, etc.
- **LicenseEnforcementMiddleware:** Bloqueo por licencia; mensaje "Licencia vencida o inválida".
- **domain_events:** SELECT * en consultas internas (tabla de eventos); aceptable. Uso de datetime.now() en fiscal para lógica/caché; regla "NOW() en SQL" aplica a INSERT/UPDATE de timestamps de negocio.

### 1.4 Patrones prohibidos
- No se usa time.sleep (sí asyncio.sleep).
- No hay @app.on_event; se usa lifespan.
- Credenciales no hardcodeadas en rutas de producción (conftest con valores de test).

---

## 2. Control-plane

- **security.py:** Tokens admin y release con mensaje "inválido" (ya corregido en sesiones anteriores).
- **cloud, branches, licenses, owner:** Mensajes en español; "Token de instalación inválido", "Correo o contraseña inválidos", etc.
- **Bootstrap:** Expone owner_session_url, compose_template_url, etc. URLs desde env (CP_BASE_URL, CP_PUBLIC_URL).

---

## 3. Frontend

- **posApi.ts:** Discovery, timeout, reintentos GET, 401 → handleExpiredSession; mensajes "Sesión expirada", "Tiempo de espera agotado", "No se pudo conectar al servidor" en español.
- **Fallback 127.0.0.1:8000:** Solo cuando no hay config; aceptable.
- **Tests:** 84 tests pasando (login, routing, posApi, offline-queue, owner-portfolio, etc.).

---

## 4. Instaladores

- **install-titan.sh:** set -e, trap cleanup, report_status en fallo. Opción --backend-image documentada en sesiones anteriores (verificar en rama actual).
- **Windows:** No revisado en esta auditoría.

---

## 5. Migraciones

- **backend/migrations:** 39 archivos; nomenclatura NNN_descripcion.sql. Idempotencia con IF NOT EXISTS / IF EXISTS según caso.
- **pin_hash y seguridad:** 033_pin_hash_and_security.sql; 037 fix_sequences.

---

## 6. Tests

- **Frontend:** vitest; 9 archivos, 84 tests OK.
- **Backend/control-plane:** pytest; requieren DB y env; no ejecutados en esta pasada.

---

## 7. Documentación

- **CLAUDE.md, AGENTS.md:** Coherentes con precios desde DB, PINs, null bytes, lock order, suites críticas.
- **docs/PATRONES.md:** Patrones obligatorios y prohibidos.
- **docs/informes/VERIFICACION_20_RONDAS.md:** Informes de rondas anteriores.

---

## 8. Correcciones aplicadas en esta auditoría

| Archivo | Cambio |
|---------|--------|
| backend/modules/employees/schemas.py | Email/Teléfono inválido, vacío, número finito, paréntesis |
| backend/modules/expenses/schemas.py | número finito, descripción no puede estar en blanco |
| backend/modules/fiscal/timezone_handler.py | Formato de timestamp inválido → inválido |
| backend/modules/fiscal/cfdi_service.py | RFC inválido |
| backend/modules/fiscal/xml_ingestor.py | XML inválido |
| backend/modules/fiscal/global_invoicing.py | Formato de fecha inválido |

---

## 9. Recomendaciones

1. **Backend/control-plane tests:** Ejecutar con DB de test y documentar en README o CI.
2. **Fiscal:** Revisar INSERT/UPDATE que usen datetime desde Python para timestamps de negocio; preferir NOW() en SQL cuando aplique.
3. **domain_events SELECT *:** Aceptable para tabla interna; si se añaden columnas sensibles, pasar a columnas explícitas.
4. **Instalador Windows:** Revisar paridad con Linux (--backend-image, mensajes español).
5. **system/routes restore:** Comando pg_restore con 127.0.0.1; considerar parametrizar host desde env si se usa en distintos entornos.
