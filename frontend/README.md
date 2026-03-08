# TITAN POS Desktop

Aplicacion de escritorio de TITAN POS construida con Electron, React y TypeScript.

## Recommended IDE Setup

- [VSCode](https://code.visualstudio.com/) + [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint) + [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)

## Project Setup

### Install

```bash
npm install
```

### Development

```bash
npm run dev
```

### Build Distribuible

```bash
# Verifica branding, config y build
npm run verify:go-live

# Genera instalador para Windows
npm run build:win

# Genera build para macOS
npm run build:mac

# Genera paquetes Linux
npm run build:linux

# Genera checksums SHA256 de los artefactos en dist/
npm run dist:checksums
```

Los scripts `build:*` generan instaladores locales sin intentar publicar artefactos. Si más adelante habilitas auto-updates, configura el proveedor de publicación en un paso separado de release/CI.

## Production Readiness

Run release verification gate:

```bash
npm run verify:release
```

Run full go-live validation (includes release config placeholder checks):

```bash
npm run verify:go-live
```

## Agente Local Y Companion

- La app desktop ahora busca `titan-agent.json` en `appData`, `~/.titanpos/` o `LOCALAPPDATA/TitanPOS/` para descubrir el nodo local y el manifest de releases del control-plane.
- Ese archivo lo generan `setup.sh` y los instaladores en `installers/`.
- Existe un companion MVP reutilizando la UI remota en la ruta `#/companion/remoto` y `#/companion/estadisticas`.
- El agente local también expone estado de licencia para `Login`, `TopNavbar` y `Ajustes`.
- Para activación offline y soporte comercial, consulta `../docs/RUNBOOK_LICENCIAS_Y_SOPORTE.md`.

## E2E Producción

Para validar contra frontend compilado en vez de Vite dev:

```bash
E2E_BASE_URL=http://127.0.0.1:8080 \
E2E_API_URL=http://127.0.0.1:8000 \
E2E_USER=admin \
E2E_PASS=admin \
npm run test:e2e:prod
```

Notas:

- `GO_NO_GO_PRODUCCION_ELECTRON.md`
- `ESTADO_MIGRACION_PYQT6_ELECTRON.md`
- `../docs/RELEASE_CHECKLIST_WINDOWS_LINUX.md`
- El nombre distribuible esperado ya no debe salir como `electron_pos`, sino como `TITAN POS` / `titan-pos`.
- `verify:go-live` ahora también exige `resources/icon.png` para evitar builds con icono genérico.
