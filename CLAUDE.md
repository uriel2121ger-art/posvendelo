# POSVENDELO — Contexto

POS retail multi-sucursal para México. Offline-first, CFDI 4.0, inventario, turnos, crédito y operación remota.

## Norte del producto

- POS tipo RustDesk: **multiplataforma**, **plug-and-play** y usable por gente no técnica.
- La instalación debe dejar el nodo operativo sin editar archivos manualmente.
- El dueño debe entrar vía agente local y `owner-session`, no con tokens crudos visibles.
- La UI visible al cliente final debe quedar en español.

## Stack

- Backend: Python 3.13, FastAPI, asyncpg, Pydantic v2, PostgreSQL 15.
- Frontend: Electron, React 19, Vite, TypeScript strict, TailwindCSS.
- Deploy: Docker Compose, GHCR, rollout con updates y rollback.

## Arquitectura útil

- `backend/`: API local y reglas de negocio.
- `frontend/`: app desktop, preload y renderer.
- `control-plane/`: bootstrap, releases, licencias, owner platform y fleet ops.
- `owner-app/`: app desktop del propietario para gestión remota de fleet.
- `installers/`: instalación Windows/Linux del nodo.

## Contrato plug-and-play

- `control-plane` publica `bootstrap-config` y `compose-template`.
- El instalador genera `.env`, `docker-compose.yml`, `titan-agent.json` e `INSTALL_SUMMARY.txt`.
- Pre-registro por fingerprint de hardware (sin cuenta); trial 120 días vinculado al hardware.
- Nube opcional: se activa desde UI, túnel CF solo al activar nube.
- Discovery LAN: UDP broadcast `:41520` cada 2s para autodescubrimiento de terminales.
- El agente local resuelve health, licencia, manifest, companion y owner access.
- El bootstrap debe exponer `owner_session_url`, `owner_api_base_url`, `companion_entry_url` y `quick_links`.

## No romper

- Precios: nunca confiar en `item.price` del cliente si hay `product_id`.
- PINs: bcrypt (rounds=12) para hashes nuevos; sha256 hex legacy soportado via `pin_auth.py`.
- Cancelaciones: siempre requieren `manager_pin`.
- Null bytes: `NullByteSanitizer` debe seguir activo.
- Sync: después de sync, corregir sequences con `setval()` cuando aplique.
- Dinero: `money()` retorna `str` para JSON; `dec()` para aritmética Decimal. Nunca float.

## Convenciones clave

- Respuestas API: `{"success": true, "data": {...}}`.
- Errores: `HTTPException(detail="español")`.
- SQL: `:nombre` con wrapper `DB`; `$N` con asyncpg directo en transacciones.
- Lock ordering: `TURNS -> SALES -> PRODUCTS -> CUSTOMERS`.
- Para timestamps actuales en DB usar `NOW()` en SQL, no `datetime` desde Python.
- Serialización: `sanitize_row()`/`sanitize_rows()` para convertir Records asyncpg a dict (Decimal a str).
- Auth: `auth: dict = Depends(verify_token)` → `get_user_id(auth)` para ID, `auth["role"]` para rol.
- Roles: `PRIVILEGED_ROLES = ("admin", "manager", "owner")` para checks de permisos.

## Suites críticas

```bash
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_auth.py tests/test_remote.py tests/test_sales.py tests/test_turns.py tests/test_system.py tests/test_security.py tests/test_products.py tests/test_customers.py tests/test_inventory.py tests/test_expenses.py -q
cd control-plane && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_security.py tests/test_owner.py tests/test_licenses.py tests/test_tenants.py -q
cd frontend && npx vitest run src/renderer/src/__tests__/app-routing.test.tsx src/renderer/src/__tests__/login.test.tsx src/renderer/src/__tests__/posApi.test.ts src/renderer/src/__tests__/offline-queue.test.ts src/renderer/src/__tests__/owner-portfolio-tab.test.tsx
```
