# Matriz Frontend / Backend / Shared

## Frontend (terminal/caja)
- `backend/app/ui/`
- `backend/app/dialogs/`
- `backend/app/wizards/`
- `backend/app/window/`
- `backend/assets/`

## Backend (API/servidor/DB)
- `backend/server/`
- `backend/src/infra/`
- `backend/src/api/`
- `backend/scripts/`

## Shared (lógica común)
- `backend/src/services/`
- `backend/src/core/`
- `backend/app/services/`
- `backend/app/repositories/`
- `backend/app/models/`

## Regla operativa
- Escrituras de negocio: solo vía API/gateway en servidor.
- Clientes: UI + consumo API; sin base de datos de negocio autónoma.

