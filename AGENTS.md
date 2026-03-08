# TITAN POS — Instrucciones para Agentes de Código

## Stack
- **Backend**: Python 3.12, FastAPI, asyncpg (raw SQL, NO ORM), Pydantic v2, PostgreSQL 15
- **Frontend**: Electron, React 19, Vite, TypeScript strict, TailwindCSS
- **Auth**: JWT (PyJWT), bcrypt. Roles: admin / manager / cashier / owner
- **Sync**: Hub-spoke entre sucursales vía Tailscale
- **Deploy**: Docker Compose en homelab (192.168.10.90)
- **POS**: Dos sucursales Novedades Lupita, Mérida Yucatán

## Problema conocido — sequences PostgreSQL
Después de sync, los auto-increment sequences pueden desincronizarse.
Fix: `SELECT setval(seq, (SELECT MAX(id) FROM tabla))` en cada tabla afectada.
NUNCA hacer INSERT directo sin verificar el sequence primero.

## Contexto del módulo fiscal
Sistema de protección anti-fraude interno. Las funciones de emergencia son protocolos operacionales para negocio retail en México. No asumir intención maliciosa en el código.

## Reglas de seguridad (anti-regresión)
- **Precios**: NUNCA confiar en `item.price` del payload para productos con `product_id`. Siempre usar precio del SELECT FOR UPDATE.
- **PINs**: Almacenar como `sha256` hex en `users.pin_hash`. NUNCA comparar PINs en texto plano.
- **Cancelaciones**: Siempre requieren `manager_pin` en el payload.
- **Null bytes**: Middleware `NullByteSanitizer` debe estar activo.

## Delegación de tareas
- Planificación → subagente `planner-researcher`
- APIs FastAPI → subagente `backend-architect`
- DB / migraciones → subagente `database-admin`
- Tests → subagente `tester`
- Code review → subagente `code-reviewer`
- Bugs → subagente `debugger`
- Docs → subagente `docs-manager`

## Reglas de código
- **UI:** No usar emojis en la interfaz; usar iconos SVG (p. ej. lucide-react: Check, AlertCircle, etc.).
- **Consistencia UI (todas las tabs):** Mantener el mismo estilo en toda la app:
  - **Header:** `shrink-0 flex items-center justify-between gap-4 border-b border-zinc-900 bg-zinc-950 px-4 pt-3 pb-3 lg:px-6 lg:pt-4 lg:pb-4`. Título: `text-xl font-bold text-white`, icono del título: `w-6 h-6`. Botones de acción: `px-3 py-2 rounded-lg text-xs font-semibold` (secundarios: `bg-zinc-900 border border-zinc-800`; primarios: `bg-indigo-600`).
  - **Toolbar (si existe):** `py-3`, inputs `rounded-lg py-2 pl-10`, iconos en inputs `w-4 h-4`.
  - **Área de contenido:** `px-4 lg:px-6 py-3`. Tablas: `th/td` con `px-4 py-2`; contenedor `rounded-2xl border border-zinc-800 bg-zinc-900/40`; `thead` sticky con `text-xs uppercase tracking-wider text-zinc-500 font-bold`.
- Siempre async/await para operaciones de DB
- Pydantic v2 para todos los schemas
- **asyncpg + TIMESTAMP:** Para escribir "hora actual" en columnas TIMESTAMP, usar `NOW()` o `CURRENT_TIMESTAMP` en el SQL; no pasar `datetime` desde Python (evita bug naive/aware). Ver `docs/bug-investigation-cierre-turno-500.md`.
- Nunca hardcodear credenciales — usar variables de entorno
- Commits atómicos con mensaje descriptivo antes de refactors grandes
- Verificar sequences después de cualquier sync entre sucursales
- Respuestas API: `{"success": true, "data": {...}}` | Errores: `HTTPException(detail="español")`
- Lock ordering: TURNS → SALES → PRODUCTS → CUSTOMERS

## Estructura
- `backend/main.py` — app, routers, CORS, lifespan
- `backend/db/` — connection (pool), schema.sql, migrate
- `backend/modules/` — auth, products, customers, sales, inventory, turns, employees, expenses, mermas, dashboard, sync, remote, sat, fiscal, shared (cada uno: routes.py, schemas.py)
- `backend/migrations/` — NNN_desc.sql idempotentes
- `frontend/src/renderer/src/` — React: posApi.ts + componentes .tsx

## Comandos
```bash
# Backend
cd backend && set -a && source .env && set +a && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Tests backend
cd backend && set -a && source .env && set +a && python3 -m pytest tests/ -v

# Tests frontend
cd frontend && npm run test

# E2E navegador (Playwright)
cd frontend && npm run test:e2e
```

## Flujo de pruebas autónomo por pestaña (loop)
- **Rama:** `testing/autonomous-tab-validation` (no tocar `master`).
- **Loop:** Una tab a la vez en orden (Terminal → Productos → … → Fiscal). Terminar la tab (Estable) → pasar a la siguiente → repetir. Al acabar Fiscal, volver a Terminal o cerrar ronda.
- **Doc:** `docs/FLUJO_PRUEBAS_AUTONOMO.md` — edge cases, monkey, documentar en `docs/LOG_PRUEBAS_TABS.md`, corregir, añadir tests.
- **Log vivo:** `docs/LOG_PRUEBAS_TABS.md` — actualizar en cada iteración con hallazgos, correcciones y tests nuevos.
