# Changelog — POSVENDELO

Cambios notables del proyecto (backend, frontend, control-plane, owner-app, instaladores).

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

---

## [1.0.3] - 2026-03-12

### Añadido

- **Wizard inicial (PC principal)**
  - Wizard en dos pasos: paso 1 (negocio, impresora, ancho de papel 58/80 mm, abrir cajón al cobrar en efectivo) y paso 2 (registro para monitoreo desde la app del dueño). Opción "Omitir por ahora" con mensaje para completar en Configuración.
  - Backend: `InitialSetupPayload` y `complete_initial_setup` aceptan `receipt_paper_width` y `cash_drawer_auto_open_cash`; se persisten en `app_config` y se muestran en Configuración.
- **Registro para monitoreo**
  - En Configuración → Nube PosVendelo: bloque "Registro para monitoreo" cuando el nodo está conectado al servidor central y aún no está vinculado (formulario email/contraseña y "Vincular cuenta para monitoreo"). API frontend: `getCloudStatus`, `activateCloud` en `posApi.ts`.
- **Instalador: PC principal vs caja secundaria**
  - Linux (.deb): variable de entorno `INSTALL_MODE=client` (o `secundaria`) en el postinst omite Docker/backend y escribe marcador en `~/.config/posvendelo/install-mode`; la app muestra "Conectar al servidor" al abrir.
  - Windows (PowerShell): parámetro `-InstallMode Client` omite backend y escribe marcador en `ProgramData\POSVENDELO\install-mode`.
  - Electron: lectura del marcador y redirección a Configurar servidor cuando modo cliente y no hay URL guardada; en modo principal se mantiene auto-asignación a 127.0.0.1:8000.
- **Documentación**
  - installers/README.md: uso de modo secundaria (Linux `INSTALL_MODE=client`, Windows `-InstallMode Client`); Android siempre cliente.

### Cambiado

- La configuración del wizard (negocio, papel, cajón) persiste y es editable en la pestaña Configuración (misma fuente `app_config`).
- RequireAuth y lógica de redirección consideran modo instalación (principal/client) en Electron para decidir si mostrar Configurar servidor.

---

## [1.0.2] - 2026-03-10

### Documentación

- **CHANGELOG.md** (raíz): changelog unificado del proyecto con entrada 1.0.0.
- **README.md**: estructura actualizada (owner-app, control-plane, migrations); tabla de documentación con enlaces a distribución, instalación y Nube PosVendelo.
- **docs/README.md**: índice "Distribución e instalación" (INSTRUCCIONES_DISTRIBUCION, INSTALACION_EQUIPOS, PLAN_NUBE_POSVENDELO).
- **docs/distribucion/INSTRUCCIONES_DISTRIBUCION.md**: guía para publicar release y distribuir a cajeros y sucursales.
- **frontend/CHANGELOG.md**: sección 2026-03-10 (turnos por terminal, React hooks, lint).

---

## [1.0.0] - 2026-03-10

### Añadido

- **Backend**
  - Migración `045_pending_remote_changes`: tabla para comandos remotos con confirmación local (Nube PosVendelo).
  - Validación en ventas: rechazo 409 si `turn_id` o `branch_id` del cliente no coinciden con el turno abierto de la terminal.
  - Turnos atados a `terminal_id`: cada terminal tiene su propio turno; cierre validado por terminal.
- **Control-plane**
  - Migración `002_cloud_nube_posvendelo`: tablas `cloud_users`, `cloud_user_memberships`, `cloud_sessions`, `cloud_password_resets`.
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
  - `docs/distribucion/PLAN_NUBE_POSVENDELO.md`: plan Nube PosVendelo (cuenta opcional, app dueño, sync, comandos remotos).
  - `docs/distribucion/INSTALACION_EQUIPOS.md`: instalación en equipos nuevos (Release, script, clonado).
  - `docs/distribucion/INSTRUCCIONES_DISTRIBUCION.md`: instrucciones para publicar y distribuir (release, cajeros, sucursales).

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
