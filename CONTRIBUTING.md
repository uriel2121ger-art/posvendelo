# Contribuir a POSVENDELO

## Rama principal

- Se trabaja en **`master`**. No se usan ramas de larga duración; los cambios se integran en `master` tras revisión.

## Antes de enviar cambios

1. **Tests**: Ejecuta las suites críticas (ver [README.md](README.md) y [AGENTS.md](AGENTS.md)).
2. **Documentación**: Si añades flujos o configs, actualiza `docs/` y el índice en [docs/README.md](docs/README.md).
3. **Convenciones**: Backend (FastAPI, asyncpg, Pydantic v2), frontend (React, TypeScript), mensajes de error en español.

## Estructura del repo

- `backend/` — API y lógica de negocio
- `frontend/` — App POS (Electron/React)
- `control-plane/` — API central (bootstrap, licencias, cloud)
- `owner-app/` — App dueños (PWA/Electron)
- `installers/` — Scripts de instalación del nodo
- `scripts/` — Scripts de utilidad (edge cases, test FastAPI)
- `docs/` — Toda la documentación (índice en docs/README.md)
