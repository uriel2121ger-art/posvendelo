# POSVENDELO — Contexto

POS retail multi-sucursal para México. Offline-first, CFDI 4.0, inventario, turnos, crédito y operación remota.

## Norte del producto

- POS tipo RustDesk: **multiplataforma**, **plug-and-play** y usable por gente no técnica.
- La instalación debe dejar el nodo operativo sin editar archivos manualmente.
- El dueño debe entrar vía agente local y `owner-session`, no con tokens crudos visibles.
- La UI visible al cliente final debe quedar en español.

## Stack

- Backend: Python 3.12, FastAPI, asyncpg, Pydantic v2, PostgreSQL 15.
- Frontend: Electron, React 19, Vite, TypeScript strict, TailwindCSS.
- Deploy: Docker Compose, GHCR, rollout con updates y rollback.

## Arquitectura útil

- `backend/`: API local y reglas de negocio.
- `frontend/`: app desktop, preload y renderer.
- `control-plane/`: bootstrap, releases, licencias, owner platform y fleet ops.
- `installers/`: instalación Windows/Linux del nodo.

## Contrato plug-and-play

- `control-plane` publica `bootstrap-config` y `compose-template`.
- El instalador genera `.env`, `docker-compose.yml`, `titan-agent.json` e `INSTALL_SUMMARY.txt`.
- El agente local resuelve health, licencia, manifest, companion y owner access.
- El bootstrap debe exponer `owner_session_url`, `owner_api_base_url`, `companion_entry_url` y `quick_links`.

## No romper

- Precios: nunca confiar en `item.price` del cliente si hay `product_id`.
- PINs: siempre `sha256` hex en `users.pin_hash`; nunca texto plano.
- Cancelaciones: siempre requieren `manager_pin`.
- Null bytes: `NullByteSanitizer` debe seguir activo.
- Sync: después de sync, corregir sequences con `setval()` cuando aplique.

## Convenciones clave

- Respuestas API: `{"success": true, "data": {...}}`.
- Errores: `HTTPException(detail="español")`.
- SQL con parámetros nombrados `:nombre`.
- Lock ordering: `TURNS -> SALES -> PRODUCTS -> CUSTOMERS`.
- Para timestamps actuales en DB usar `NOW()` en SQL, no `datetime` desde Python.

## Suites críticas

```bash
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_auth.py tests/test_remote.py tests/test_sales.py tests/test_turns.py tests/test_system.py -q
cd control-plane && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_security.py tests/test_owner.py tests/test_licenses.py tests/test_tenants.py -q
cd frontend && npx vitest run src/renderer/src/__tests__/app-routing.test.tsx src/renderer/src/__tests__/login.test.tsx src/renderer/src/__tests__/posApi.test.ts src/renderer/src/__tests__/offline-queue.test.ts src/renderer/src/__tests__/owner-portfolio-tab.test.tsx
```
