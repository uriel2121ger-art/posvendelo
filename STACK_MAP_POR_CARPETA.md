# Mapa de Stack por Carpeta

## Resumen general
- Lenguaje principal: `Python`
- UI desktop: `PyQt6`
- API servidor: `FastAPI` + `Uvicorn`
- DB central: `PostgreSQL`
- Integración fiscal: `Facturapi` / CFDI

## Clasificación por carpeta
- `backend/app/ui/` -> UI desktop (frontend de terminal)
- `backend/app/dialogs/` -> UI/UX de terminal
- `backend/app/wizards/` -> UI de asistentes de operación
- `backend/app/services/` -> servicios de aplicación (backend lógico local)
- `backend/src/services/` -> dominio de negocio (backend core)
- `backend/src/infra/` -> acceso DB y esquemas (backend infraestructura)
- `backend/server/` -> gateway/API central (backend servidor)
- `backend/scripts/` -> operación DevOps/DB (backend operación)
- `backend/data/config/` -> configuración local por rol
- `frontend/` -> árbol espejo histórico; recomendado converger a fuente canónica única

## Decisión de ownership recomendada
- Fuente canónica de desarrollo: `backend/`
- `frontend/` se mantiene temporal como espejo/artefacto hasta convergencia total.

