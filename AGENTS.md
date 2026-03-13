# POSVENDELO — Instrucciones para Agentes

## Prioridades

- Mantener el enfoque RustDesk-like: multiplataforma, plug-and-play y simple.
- Evitar pasos manuales para el usuario final.
- Toda UI y mensaje visible al cliente debe quedar en español.

## No romper

- Precios desde DB, nunca desde el cliente si hay `product_id`.
- PINs en `users.pin_hash` con `sha256` hex.
- Cancelaciones siempre con `manager_pin`.
- `NullByteSanitizer` debe seguir activo.
- Después de sync, corregir sequences con `setval()` cuando aplique.

## Contrato operativo

- `control-plane` entrega `bootstrap-config` y `compose-template`.
- El nodo instalado debe terminar con `.env`, `docker-compose.yml`, `posvendelo-agent.json` e `INSTALL_SUMMARY.txt`.
- El agente local es la fuente para health, licencia, updates, companion y owner access.
- Si una URL ya existe en `bootstrap-config`, no reconstruirla a mano.

## Reglas de implementación

- Backend: FastAPI async, asyncpg, Pydantic v2, SQL parametrizado.
- Frontend: no emojis; usar solo SVG (o iconos basados en SVG, p. ej. Lucide) para iconos e ilustraciones. Mantener consistencia visual existente.
- API: `{"success": true, "data": {...}}` y errores en español.
- Lock ordering: `TURNS -> SALES -> PRODUCTS -> CUSTOMERS`.
- Para hora actual en DB usar `NOW()`; no mandar `datetime` desde Python.
- No hardcodear credenciales, IPs, rutas ni enlaces.

## Cuándo probar

- Si tocas backend crítico: auth, remote, sales, turns, system.
- Si tocas control-plane, licensing, owner, companion o bootstrap.
- Si tocas app desktop, login, routing, offline queue o posApi.

## Suites críticas

```bash
cd control-plane && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_security.py tests/test_owner.py tests/test_licenses.py tests/test_tenants.py -q
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_auth.py tests/test_remote.py tests/test_sales.py tests/test_turns.py tests/test_system.py -q
cd frontend && npx vitest run src/renderer/src/__tests__/app-routing.test.tsx src/renderer/src/__tests__/login.test.tsx src/renderer/src/__tests__/posApi.test.ts src/renderer/src/__tests__/offline-queue.test.ts src/renderer/src/__tests__/owner-portfolio-tab.test.tsx
```
