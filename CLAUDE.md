# POSVENDELO — Contexto

POS retail multi-sucursal para Mexico. Offline-first, CFDI 4.0, inventario, turnos, credito y operacion remota.

## Norte del producto

- POS tipo RustDesk: **multiplataforma**, **plug-and-play** y usable por gente no tecnica.
- La instalacion debe dejar el nodo operativo sin editar archivos manualmente.
- El dueno entra via agente local y `owner-session`, no con tokens crudos visibles.
- UI visible al cliente final en espanol.

## Stack

- Backend: Python 3.13, FastAPI, asyncpg, Pydantic v2, PostgreSQL 15.
- Frontend: Electron, React 19, Vite, TypeScript strict, TailwindCSS.
- Deploy: Docker Compose, GHCR, Watchtower, rollout con updates y rollback.

## Arquitectura

- `backend/`: API local y reglas de negocio.
- `frontend/`: app desktop Electron (preload + renderer). Agente local en `src/main/localAgent.ts`.
- `control-plane/`: bootstrap-config, compose-template, releases, licencias, owner platform, fleet ops.
- `owner-app/`: app desktop del propietario para gestion remota de fleet.
- `installers/`: postinst.sh (Linux .deb), Install-Posvendelo.ps1 (Windows), NSIS.

## Flujo primera ejecucion (desktop)

```
dpkg -i → postinst (Electron + agent.json) → abrir app
→ /seleccionar-modo ("¿Como se usara esta PC?")
  → [PC Principal] → ensureBackend (Docker + PostgreSQL)
    → auto-registro con control-plane (hw fingerprint, prueba 40 dias)
    → /setup-inicial-usuario (wizard first-user) → auto-login
    → /setup-inicial (wizard negocio) → /terminal
  → [Caja secundaria] → /configurar-servidor (IP del principal LAN)
    → /login → /terminal
```

- Desktop auto-configura la URL base = `127.0.0.1:8000` (no muestra "configurar servidor").
- Mobile (APK) muestra `/configurar-servidor` para IP del servidor LAN.
- `checkNeedsFirstUser()` decide si mostrar wizard o login.
- postinst NO instala Docker — lo hace `ensureBackend()` al elegir "PC Principal".

## Contrato plug-and-play

- `control-plane` publica `bootstrap-config` y `compose-template`.
- La app Electron genera `.env`, `docker-compose.yml` al elegir PC Principal, ademas de `posvendelo-agent.json`. Los instaladores (`postinst.sh`, `Install-Posvendelo.ps1`) generan `INSTALL_SUMMARY.txt`.
- Pre-registro por fingerprint de hardware (sin cuenta); periodo de prueba 40 dias vinculado al hardware.
- Nube opcional: se activa desde UI, tunel CF solo al activar nube.
- Discovery LAN: UDP broadcast `:41520` cada 2s (`backend/modules/discovery/broadcast.py`).
- Agente local (`localAgent.ts`): health, licencia, manifest, companion, owner access, Docker manage.
- Bootstrap expone `owner_session_url`, `owner_api_base_url`, `companion_entry_url`, `quick_links`.

## No romper

- Precios: nunca confiar en `item.price` del cliente si hay `product_id`.
- PINs: bcrypt (rounds=12) para hashes nuevos; sha256 hex legacy via `pin_auth.py`.
- Cancelaciones: siempre requieren `manager_pin`.
- Null bytes: `NullByteSanitizer` debe seguir activo.
- Sync: despues de sync, corregir sequences con `fix_all_sequences()`.
- Dinero: `money()` retorna `str` para JSON; `dec()` para aritmetica Decimal. Nunca float.
- postinst.sh: `set -e` solo seccion 0 (Electron); `set +e` seccion 1+ (Docker) — dpkg nunca falla por red.

## Convenciones clave

- Respuestas API: `{"success": true, "data": {...}}`.
- Errores: `HTTPException(detail="espanol")`.
- SQL: `:nombre` con wrapper `DB`; `$N` con asyncpg directo en transacciones.
- Lock ordering: `TURNS -> PRODUCTS -> CUSTOMERS`.
- Timestamps en DB: `NOW()` en SQL, no `datetime` desde Python.
- Serializacion: `sanitize_row()`/`sanitize_rows()` para Records asyncpg a dict (Decimal a str).
- Auth: `auth: dict = Depends(verify_token)` → `get_user_id(auth)` para ID, `auth["role"]` para rol.
- Roles: `PRIVILEGED_ROLES = ("admin", "manager", "owner")`.
- asyncpg: `datetime` para TIMESTAMP, `date` para DATE, `Decimal` para NUMERIC. Nunca strings.

## Error Playbook (ingenieria de contexto agentico)

Cuando un error se encuentra y se resuelve, documentarlo en `memory/error-playbook.md` con:
1. **ID secuencial** (ERR-NNN)
2. **Sintoma**: que ve el usuario o que falla
3. **Causa raiz**: por que pasa realmente
4. **Solucion**: pasos exactos que lo corrigieron
5. **Resultado**: estado final verificado
6. **Leccion**: regla generalizable para evitar recurrencia

Consultar el playbook ANTES de investigar un error nuevo — puede estar resuelto.

## Suites criticas

```bash
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_auth.py tests/test_remote.py tests/test_sales.py tests/test_turns.py tests/test_system.py tests/test_security.py tests/test_products.py tests/test_customers.py tests/test_inventory.py tests/test_expenses.py -q
cd control-plane && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_security.py tests/test_owner.py tests/test_licenses.py tests/test_tenants.py -q
cd frontend && npx vitest run src/renderer/src/__tests__/app-routing.test.tsx src/renderer/src/__tests__/login.test.tsx src/renderer/src/__tests__/posApi.test.ts src/renderer/src/__tests__/offline-queue.test.ts src/renderer/src/__tests__/owner-portfolio-tab.test.tsx
```
