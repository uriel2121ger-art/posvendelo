# Changelog - TITAN POS

All notable changes to this workspace are documented in this file.

## 2026-03-10

### Added

- Turnos por terminal: `shiftTypes` con claves de localStorage por `terminalId` (`getCurrentShiftStorageKey`, `getShiftHistoryStorageKey`, `isShiftStorageKey`).
- Tests unitarios: `shiftTypes.test.ts` (aislamiento por terminal), `expenses-tab.test.tsx` (gastos, turno).
- ESLint: ignore de `scripts/**/*.mjs` para runners E2E/chaos; corrección `no-useless-escape` en `localAgent.shellQuote` (comillas para shell).

### Changed

- `ShiftStartupModal`, `ShiftsTab`, `Terminal`, `ExpensesTab`: uso consistente de `terminalId` en `readCurrentShift`/`saveCurrentShift`/`readShiftHistory`/`saveShiftHistory`.
- `posApi.getCurrentTurn`: envío de `terminal_id` en query y cabecera `X-Terminal-Id`.
- React hooks: dependencias exhaustivas para evitar avisos y comportamientos obsoletos:
  - `CompanionDevicesTab`: `loadDevices` en `useCallback` con `[canManage]`, y en deps del `useEffect`.
  - `ShiftsTab`: `runtimeConfig.terminalId` en deps del `useEffect` (focus/storage).
  - `Terminal`: `config.terminalId` en deps del `useEffect` (refresh shift y poll); `applyTicketSnapshot` con `[activeTicketId, config.terminalId]`; `createNewActiveTicket` con `config.terminalId` y `query`.

### Fixed

- Posible uso de turno/contexto de otra terminal al cambiar de terminal o en multi-caja.
- Avisos de lint `react-hooks/exhaustive-deps` en CompanionDevicesTab, ShiftsTab y Terminal.
- Formato Prettier en archivos tocados (main, preload, Login, tests, TopNavbar, tabs).

## 2026-03-05

### Testing

- Inicio de ejecución del Plan de Pruebas Manuales V10 (`docs/testing/PLAN_PRUEBAS_MANUALES_V10.md`).
- Log de sesión: `docs/testing/LOG_PRUEBAS_MANUALES_V10_2026-03-05.md`.
- Pruebas ejecutadas en navegador (Cursor IDE Browser) con frontend en `http://localhost:5173` y backend en `localhost:8090`.
- Cache del navegador reiniciada antes de comenzar (navegación forzada).
- Fases previstas: 0 (regresión V8), 1–12 y monkey testing; documentación continua en el log.
- Primera ejecución: login OK, Fase 0.3 (carrito vacío — COBRAR deshabilitado) OK; Fase 0.1 (Empleados) parcial: botón se habilita con nombre+código; crear empleado no completado (revisar URL backend en Ajustes, ej. `http://localhost:8090`).
- Segunda ejecución (mismo día): BaseUrl configurada a `http://127.0.0.1:8090` en Ajustes; re-login; Fase 1 muestreo: búsqueda de productos OK, agregar al carrito OK, modal de cobro (Efectivo, Recibido $100) y confirmación OK; pestaña Fiscal verificada (formulario CFDI, botón Generar CFDI). Fases 2–12 no ejecutadas caso por caso; documentado en `docs/testing/LOG_PRUEBAS_MANUALES_V10_2026-03-05.md` con recomendaciones para completar el plan.
- Tercera ejecución (continuación sin saltar ítems): Fase 0 completada: 0.1 Empleados (FALLO crear empleado — botón no clickeable; OK botón habilita con nombre+código; OK código vacío bloqueado), 0.2 Fiscal (OK CFDI folio inexistente + OK EDGE CP 0123), 0.3 Carrito vacío (OK + OK EDGE vaciar 1 item), 0.4 Precisión (OK 16×$100), 0.5 Remoto (OK EDGE cero ventas), 0.6 OMITIDO (localStorage). Fase 1.2 Búsqueda: OK inexistente, OK un carácter, OK caracteres especiales %. LOG exhaustivo actualizado con todos los ítems del plan (Fases 0–12) listados; resumen 14 OK, 1 FALLO, resto OMITIDO para ejecución en sesiones dedicadas.
- Cuarta ejecución (continuación): Login, Continuar turno. 1.2: OK búsqueda vacía (espacios), OK solo números, OK "agua". 1.3: OK mismo producto varias veces (cantidad 2, una línea). 1.1: OK venta efectivo + cambio (2× Papas $100, Recibido $150); OK VARIANTE monto insuficiente (Total $100, Recibido $80 → no venta, mensaje). Resumen LOG: 20 OK, 1 FALLO.

## 2026-02-22

### Fixed

- Added missing routing dependency: `react-router-dom`.
- Added missing icon dependency used by renderer mock screen: `lucide-react`.
- Added Tailwind PostCSS plugin for Tailwind v4: `@tailwindcss/postcss`.
- Fixed renderer type error by removing explicit `JSX.Element` return type from `App`.
- Updated `postcss.config.js` to use `@tailwindcss/postcss` plugin.
- Updated `src/renderer/src/assets/main.css` for Tailwind v4 compatibility (`@import "tailwindcss"` and plain base `body` styles).
- Replaced terminal mock UI with a functional Phase 1 POS flow:
  - Product pull from gateway (`/api/v1/sync/products` with classic fallback)
  - Search and add-to-cart
  - Real-time subtotal/IVA/total calculation
  - Sale sync (`/api/v1/sync/sales`)
  - Runtime terminal config persisted in local storage (`baseUrl`, `token`, `terminalId`)
- Upgraded terminal to Phase 2 parity features:
  - Line-level discount per item
  - Global discount percentage on current ticket
  - Customer name assignment at ticket level
  - Payment method selection (`cash`, `card`, `transfer`)
  - Pending tickets save/load with local persistence
- Implemented keyboard shortcuts requested:
  - Global navigation: `F1` ventas, `F2` clientes, `F3` productos, `F4` inventario
  - In sales: `Ctrl+P` producto comun, `Ctrl+D` descuento de producto seleccionado, `Ctrl+G` descuento global
- Added additional sales hotkeys for caja operation:
  - `F10` focus/seleccion de campo de busqueda
  - `F12` cobrar y sincronizar
  - `+` / `-` ajustar cantidad del item seleccionado
  - `Del` / `Backspace` eliminar item seleccionado del carrito
- Enhanced "producto comun" flow:
  - Optional note captured at creation time
  - Note shown in cart line item
  - `common_note` included in sale sync payload for sale history traceability
- Advanced caja continuity in `Terminal`:
  - Multiple active tickets in parallel (`crear`, `cambiar`, `cerrar`)
  - Active ticket keyboard shortcut: `Ctrl+N` to create new active ticket
  - Cash charge validation with `monto recibido`, `faltante`, and `cambio`
  - Sale sync payload extended with `amount_received` and `change_due`
- Added missing functional tabs and sections:
  - `Reportes (F5)`: operational KPIs, payment breakdown, and top products by range
  - `Historial (F6)`: sales search by folio/date and per-sale detail view
  - `Configuraciones (F7)`: runtime config save + backend connection/sync status test
- Strengthened "production-ready" workflow in new tabs:
  - `Reportes (F5)`: CSV exports (`resumen` and `top productos`)
  - `Historial (F6)`: advanced filters (payment method + total min/max) and CSV export
  - `Configuraciones (F7)`: named terminal profiles (save/load/delete)
- Added missing `Turnos` module and corrected keyboard mapping:
  - `Turnos (F5)`: open/close shift flow with opening/closing cash and cash difference
  - Shift records persisted locally and synchronized through `sync/shifts`
  - Function-key remap applied: `F5 turnos`, `F6 reportes`, `F7 historial`, `F8 configuraciones`
- Enforced shift-to-sales continuity:
  - Sales charge in `Terminal` is blocked when no open shift exists
  - Every successful sale updates open-shift accumulators (`salesCount`, totals, payment split)
  - Turno dashboard now reflects live progress for shift cut (`arqueo`) preparation
- Extended `Turnos (F5)` for operational control:
  - Backend reconciliation for a selected shift using sales history
  - Shift-cut CSV export including local values and backend deltas
  - Terminal-aware reconciliation window (`openedAt`..`closedAt`) against backend sales data
- Extended shift close workflow for cashier execution:
  - Printable shift-cut report (`Imprimir corte`) from `Turnos (F5)`
  - Suggested expected cash action using backend reconciliation when available
  - Reconciliation now records timestamp (`reconciledAt`) and includes it in exported CSV
- Expanded API helper capabilities in `posApi.ts`:
  - `searchSales`, `getSaleDetail`, `getSyncStatus`, `getSystemInfo`
  - GET fallback resolver for endpoint compatibility
- Replaced placeholder tabs with functional modules:
  - `Clientes (F2)`: customer pull + create flow using sync API
  - `Productos (F3)`: product pull + create flow using sync API
  - `Inventario (F4)`: stock load and SKU stock adjustment with sync
- Extended module operations for daily workflow parity:
  - `Clientes (F2)`: row selection, edit/update, logical delete (sync + UI removal)
  - `Productos (F3)`: row selection, edit/update, logical delete (sync + UI removal)
  - `Inventario (F4)`: stock movement mode (`entrada` / `salida`) by quantity
  - `Inventario (F4)`: negative stock guard before syncing movement
- Corrected JSX root structure regressions in functional tabs:
  - `Clientes`, `Productos`, `Inventario`, `Historial`, `Reportes`, `Configuraciones`
  - Removed parse blockers caused by inconsistent root wrappers
- Added shared frontend API helper `src/renderer/src/posApi.ts`:
  - Runtime config reuse (`baseUrl`, `token`, `terminalId`)
  - Primary + fallback data pull strategy
  - Generic sync payload with `request_id` and `terminal_id`

### Verified

- `npm run lint` passes.
- `npm run typecheck` passes.
- `npm run build` passes (`electron-vite` main, preload, and renderer outputs generated).
- Terminal flow compiles and runs in renderer route `/terminal`.

### Security

- Ran NPM audit and classified findings.
- Added `INFORME_VULNERABILIDADES_NPM.md`.
- Confirmed `npm audit --omit=dev` has 0 runtime vulnerabilities in production dependencies.
- Executed `npm audit fix` (without `--force`) and verified no reduction in findings (`26 high` remains).
- Added `PLAN_HARDENING_DEPENDENCIAS.md` for phased remediation with controlled major upgrades.
- Kept ESLint on v9 line due to current `eslint-plugin-react` peer compatibility.
- Upgraded `electron-builder` to `26.8.1` and re-validated quality gates.
- Added dependency overrides to unblock transitive vulnerability chain:
  - `minimatch: ^10.2.2`
  - `tar: ^7.5.8`
- Re-ran audits after remediation: full tree now reports `0` and production dependencies remain `0`.
- Hardened Electron window security defaults in `src/main/index.ts`:
  - `sandbox: true`
  - `contextIsolation: true`
  - `nodeIntegration: false`
  - `webviewTag: false`
  - `devTools` enabled only in development
- Restricted `shell.openExternal` to `http/https` URLs only.

### Notes

- NPM reports engine warnings related to Node version for some transitive packages (`@electron/rebuild`, `node-abi`) in this environment.
- NPM audit reports high vulnerabilities in dependency tree (not resolved in this pass to avoid introducing breaking changes without approval).

### Production

- Added automated release gate scripts in `package.json`:
  - `audit:full`
  - `audit:prod`
  - `audit:all`
  - `verify:release`
- Added `GO_NO_GO_PRODUCCION_ELECTRON.md` with production release criteria and blockers.
- Updated `README.md` with production readiness command and reference doc.
- Added `check:release-config` script to block go-live when `electron-builder.yml` still has placeholders.
- Added `verify:go-live` script to run technical gate plus release config validation.
