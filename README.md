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
| -------- | ----------- | --- |
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

## Producción Y Distribución

Para dejar el backend productivo actualizado:

```bash
export BACKEND_IMAGE="${BACKEND_IMAGE:-ghcr.io/titan-pos/titan-pos:latest}"
docker build -t "$BACKEND_IMAGE" backend
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate api
curl http://127.0.0.1:8000/health
```

Para validar y generar artefactos de escritorio:

```bash
cd frontend
npm run verify:go-live
npm run build:win
# o npm run build:linux
```

No dejes procesos dev activos en `8090` o `5173` mientras validas el runtime productivo.
Si más adelante habilitas auto-updates del desktop, configura ese proveedor aparte del empaquetado local.
Antes de publicar a clientes, sigue `docs/RELEASE_CHECKLIST_WINDOWS_LINUX.md`.
Para soporte comercial y activación offline, usa `docs/RUNBOOK_LICENCIAS_Y_SOPORTE.md`.
Para rollout de fixes, staging de updates y rollback, usa `docs/ROLLOUT_UPDATES_Y_ROLLBACK.md`.

### Flujo Plug-And-Play

Objetivo operativo:

- instalar en Windows o Linux sin editar archivos manualmente
- dejar el nodo listo para abrir caja y operar
- delegar el acceso remoto del dueño mediante el agente local
- dejar un resumen usable por soporte en `INSTALL_SUMMARY.txt`

Flujo esperado:

1. El `control-plane` entrega `bootstrap-config` y `compose-template`.
2. El instalador genera `.env`, `docker-compose.yml`, `titan-agent.json` e `INSTALL_SUMMARY.txt`.
3. La app desktop detecta el nodo local, licencia, companion y acceso del dueño desde el agente.
4. Soporte valida salud local, branch, manifest y companion sin reconstruir rutas a mano.

Validación rápida antes de salida a cliente:

```bash
cd frontend && npm run verify:go-live
cd backend && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_auth.py tests/test_remote.py tests/test_sales.py tests/test_turns.py tests/test_system.py -q
cd control-plane && export $(grep -v '^#' ../.env | grep -v '^$' | xargs) && python3 -m pytest tests/test_security.py tests/test_owner.py tests/test_licenses.py tests/test_tenants.py -q
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

```text
backend/          # FastAPI + asyncpg
  main.py         # Entry point (app factory + routers + lifespan)
  db/             # asyncpg pool + DB wrapper
  modules/        # Módulos de negocio (auth, sales, turns, remote, etc.)
  migrations/     # SQL idempotentes (incl. 045 pending_remote_changes)
  tests/          # Tests de integración (pytest + asyncio)
frontend/         # Electron + React + TypeScript (app cajeros)
control-plane/    # API central (bootstrap, licencias, tenants, cloud)
  db/migrations/  # Schema y migraciones (002 cloud Nube TITAN)
owner-app/        # PWA/Electron para dueños (monitoreo, sucursales)
installers/       # Scripts instalación nodo (Linux/Windows)
docs/             # Documentación del proyecto
_archive/         # Código legacy (rollback)
```

## Stack

- **Backend:** Python 3.12, FastAPI, asyncpg, PostgreSQL 15
- **Frontend:** React 19, TypeScript, Zustand, TailwindCSS, Electron
- **Fiscal:** CFDI 4.0 (lxml + defusedxml + signxml), IVA 16%
- **Deploy:** Docker Compose (postgres + api)

## Documentación importante

| Doc | Contenido |
| --- | --------- |
| [CHANGELOG.md](CHANGELOG.md) | Changelog del proyecto (releases y cambios notables) |
| [docs/INSTRUCCIONES_DISTRIBUCION.md](docs/INSTRUCCIONES_DISTRIBUCION.md) | Cómo publicar una release y distribuir (cajeros, sucursales) |
| [docs/INSTALACION_EQUIPOS.md](docs/INSTALACION_EQUIPOS.md) | Instalación en equipos nuevos (Release, script, clonado) |
| [docs/PLAN_NUBE_TITAN.md](docs/PLAN_NUBE_TITAN.md) | Plan Nube TITAN: cuenta opcional, app dueño, sync, comandos remotos |
| [installers/README.md](installers/README.md) | Instalación Windows/Linux, contrato bootstrap y soporte plug-and-play |
| [docs/SECURITY_CHECKLIST.md](docs/SECURITY_CHECKLIST.md) | Checklist de seguridad, pip-audit y controles implementados |
| [docs/INGESTORES_CSV_XML.md](docs/INGESTORES_CSV_XML.md) | Ingestores CSV/XML: productos, clientes, inventario, historial |
| [docs/PARSEAR_XML_FISCAL.md](docs/PARSEAR_XML_FISCAL.md) | Parsear XML (CFDI 4.0): defusedxml, instalación, pruebas |
| [docs/BUG_PATTERN_ASYNCPG_FECHAS.md](docs/BUG_PATTERN_ASYNCPG_FECHAS.md) | Patrones de bug asyncpg con fechas (DATE/TIMESTAMP) |
| [docs/DESPUES_DE_DEPLOY.md](docs/DESPUES_DE_DEPLOY.md) | Reinicio de servicios y limpieza de caché tras deploy |
| [docs/RUNBOOK_LICENCIAS_Y_SOPORTE.md](docs/RUNBOOK_LICENCIAS_Y_SOPORTE.md) | Emisión, renovación, activación offline y reinstalación de licencias |
| [docs/ROLLOUT_UPDATES_Y_ROLLBACK.md](docs/ROLLOUT_UPDATES_Y_ROLLBACK.md) | Publicación de fixes, rollout por canal/sucursal y rollback operativo |
| [backend/README.md](backend/README.md) | API, tests, dependencias (incl. defusedxml para Parsear XML) |
