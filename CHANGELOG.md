# Changelog — TITAN POS

Cambios notables del proyecto (backend, frontend, control-plane, owner-app, instaladores).

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [1.0.2] - 2026-03-10

### Documentación

- **CHANGELOG.md** (raíz): changelog unificado del proyecto con entrada 1.0.0.
- **README.md**: estructura actualizada (owner-app, control-plane, migrations); tabla de documentación con enlaces a distribución, instalación y Nube TITAN.
- **docs/README.md**: índice "Distribución e instalación" (INSTRUCCIONES_DISTRIBUCION, INSTALACION_EQUIPOS, PLAN_NUBE_TITAN).
- **docs/INSTRUCCIONES_DISTRIBUCION.md**: guía para publicar release y distribuir a cajeros y sucursales.
- **frontend/CHANGELOG.md**: sección 2026-03-10 (turnos por terminal, React hooks, lint).

---

## [1.0.0] - 2026-03-10

### Añadido

- **Backend**
  - Migración `045_pending_remote_changes`: tabla para comandos remotos con confirmación local (Nube TITAN).
  - Validación en ventas: rechazo 409 si `turn_id` o `branch_id` del cliente no coinciden con el turno abierto de la terminal.
  - Turnos atados a `terminal_id`: cada terminal tiene su propio turno; cierre validado por terminal.
- **Control-plane**
  - Migración `002_cloud_nube_titan`: tablas `cloud_users`, `cloud_user_memberships`, `cloud_sessions`, `cloud_password_resets`.
  - Módulo `/api/v1/cloud`: discover, registro de sucursal; tests `test_cloud_auth`.
- **Frontend (POS)**
  - Turnos por terminal: `shiftTypes` con claves de localStorage por `terminalId`; `ShiftStartupModal`, `ShiftsTab`, `Terminal` y `ExpensesTab` usan `terminalId` consistente.
  - Tests: `shiftTypes.test.ts`, `expenses-tab.test.tsx`; ajustes en `posApi`, login y owner-portfolio.
  - ESLint: ignore de `scripts/**/*.mjs`; corrección `no-useless-escape` en `localAgent.shellQuote`.
  - React hooks: dependencias exhaustivas en `CompanionDevicesTab`, `ShiftsTab` y `Terminal` (useEffect/useCallback).
- **Owner-app**
  - App PWA/Electron para dueños (React + Vite + TypeScript); build y desktop.
- **Instaladores**
  - Checklist de instalación limpia pre-lanzamiento en `installers/README.md`.
- **Documentación**
  - `docs/PLAN_NUBE_TITAN.md`: plan Nube TITAN (cuenta opcional, app dueño, sync, comandos remotos).
  - `docs/INSTALACION_EQUIPOS.md`: instalación en equipos nuevos (Release, script, clonado).
  - `docs/INSTRUCCIONES_DISTRIBUCION.md`: instrucciones para publicar y distribuir (release, cajeros, sucursales).

### Cambiado

- Backend: `open_turn` / `get_current_turn` filtran por `terminal_id`; `close_turn` exige que el turno pertenezca a la terminal del request.
- Frontend: `posApi.getCurrentTurn` envía `terminal_id` en query; persistencia de turno y pendientes por terminal.
- Instaladores: README ampliado con checklist pre-lanzamiento.

### Corregido

- Contaminación de turnos entre terminales (todas las ventas en `terminal_id` null).
- Cierre de turno desde otra terminal (409 si no coincide `X-Terminal-Id`).
- Avisos de lint `react-hooks/exhaustive-deps` en CompanionDevicesTab, ShiftsTab y Terminal.

---

## Historial anterior

Para cambios detallados del frontend (Electron/React), ver [frontend/CHANGELOG.md](frontend/CHANGELOG.md).
