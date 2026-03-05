# TITAN POS

Sistema punto de venta retail para Mexico. Backend FastAPI + Frontend Electron/React.

## Variables de entorno

**Dónde están:** el archivo `.env` va en la **raíz del proyecto** (junto a `backend/` y `frontend/`). No se sube a git (está en `.gitignore`).

```bash
cp .env.example .env
# Editar .env con valores reales (DATABASE_URL, JWT_SECRET, etc.)
```

**Variables que usa el backend:**

| Variable | Obligatoria | Uso |
|----------|-------------|-----|
| `DATABASE_URL` | Sí | Conexión PostgreSQL (ej. `postgresql+asyncpg://user:pass@host:5432/titan_pos`) |
| `JWT_SECRET` o `SECRET_KEY` | Sí (recomendado) | Firma de tokens JWT; si falta, se genera uno aleatorio (tokens no persisten al reiniciar) |
| `CORS_ALLOWED_ORIGINS` | No | Orígenes permitidos separados por coma; si está vacío, se usan localhost/127.0.0.1 por defecto |
| `DEBUG` | No | `true` = Swagger en `/docs` y rate-limit relajado |
| `ADMIN_API_USER` / `ADMIN_API_PASSWORD` | Según bootstrap | Usuario inicial si se crea desde seed |
| `FACTURAPI_KEY`, `CSD_MASTER_KEY`, etc. | No | Solo si usas el módulo fiscal |

Para levantar el backend con el `.env` de la raíz:  
`cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m uvicorn main:app --host 0.0.0.0 --port 8090`

## Quick Start

```bash
# 1. Copiar variables de entorno
cp .env.example .env
# Editar .env con valores reales

# 2. Levantar con Docker
make up

# 3. Verificar
make health
```

## Desarrollo Local

```bash
# Backend (requiere PostgreSQL corriendo)
make dev-backend

# Frontend
make dev-frontend

# Tests
make test
```

## Estructura

```
backend/          # FastAPI + asyncpg
  main.py         # Entry point (app factory + routers + lifespan)
  db/             # asyncpg pool + DB wrapper
  modules/        # 14 modulos de negocio (110 endpoints)
  tests/          # 164 tests de integracion (pytest + asyncio)
frontend/         # Electron + React + TypeScript
docs/             # Documentacion del proyecto
_archive/         # Codigo legacy (rollback)
```

## Stack

- **Backend:** Python 3.12, FastAPI, asyncpg, PostgreSQL 15
- **Frontend:** React 19, TypeScript, Zustand, TailwindCSS, Electron
- **Fiscal:** CFDI 4.0 (lxml + signxml), IVA 16%
- **Deploy:** Docker Compose (postgres + api)
