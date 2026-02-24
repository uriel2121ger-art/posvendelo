# electron_pos

An Electron application with React and TypeScript

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

### Build

```bash
# For windows
npm run build:win

# For macOS
npm run build:mac

# For Linux
npm run build:linux
```

## Production Readiness

Run release verification gate:

```bash
npm run verify:release
```

Run full go-live validation (includes release config placeholder checks):

```bash
npm run verify:go-live
```

See:

- `GO_NO_GO_PRODUCCION_ELECTRON.md`
- `ESTADO_MIGRACION_PYQT6_ELECTRON.md`
