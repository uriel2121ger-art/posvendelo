# TITAN POS

Sistema punto de venta retail para Mexico. Backend FastAPI + Frontend Electron/React.

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
  modules/        # 16 modulos de negocio
  tests/          # pytest
frontend/         # Electron + React + TypeScript
docs/             # Documentacion del proyecto
_archive/         # Codigo legacy (rollback)
```

## Stack

- **Backend:** Python 3.13, FastAPI, asyncpg, PostgreSQL 15+
- **Frontend:** React 19, TypeScript, Zustand, TailwindCSS, Electron
- **Fiscal:** CFDI 4.0 (lxml + signxml), IVA 16%
- **Deploy:** Docker Compose (postgres + api)
