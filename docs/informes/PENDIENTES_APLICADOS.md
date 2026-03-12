# Pendientes aplicados (schema + instalador)

**Fecha:** 2025-03-08

## 1. Unificación de schema_version

- **backend/db/schema.sql**: La tabla `schema_version` quedó alineada con **backend/migrations/001_schema_version.sql** y **backend/db/migrate.py** (SCHEMA_VERSION_DDL):
  - `id BIGSERIAL PRIMARY KEY`
  - `version INTEGER NOT NULL UNIQUE`
  - `description TEXT`
  - `applied_at TIMESTAMP DEFAULT NOW()`
- Así, instalaciones desde schema.sql y desde migrate usan la misma estructura.

## 2. Instalador Linux: --backend-image y fallback al pull

- **installers/linux/install-titan.sh**:
  - Opción `--backend-image IMAGEN` en usage y en el parser.
  - Variable `BACKEND_IMAGE_OVERRIDE`; se pasa al Python que genera `.env`.
  - En la generación de `.env`, `BACKEND_IMAGE` usa: override > bootstrap `backend_image` > `TITAN_DEFAULT_BACKEND_IMAGE`.
  - Si `docker compose pull` falla: se comprueba si `BACKEND_IMAGE_OVERRIDE` está definida y la imagen existe localmente; si es así se continúa con `up -d`; si no, se muestra mensaje en español y se sale con error (incluyendo la sugerencia de usar `--backend-image posvendelo:local`).

## 3. Corrección de typos en módulos (español)

- **backend/modules/fiscal/timezone_handler.py**: "Maximo permitido" → "Máximo permitido"
- **backend/modules/hardware/printer.py**: "invalido" → "inválido"
- **backend/modules/customers/routes.py**: "credito" → "crédito"
- **backend/modules/sales/routes.py**: "credito" / "limite de credito" → "crédito" / "límite de crédito"
- **backend/modules/turns/schemas.py**: "numero finito" / "denominacion" → "número finito" / "denominación"
- **backend/modules/customers/schemas.py**: "limite de credito" / "numero finito" → "límite de crédito" / "número finito"
- **backend/modules/inventory/schemas.py**: "numero finito" → "número finito"
- **backend/modules/fiscal/cfdi_service.py**: "Nota de credito", "devolucion" → "Nota de crédito", "devolución"
- **backend/modules/fiscal/legal_documents.py**: "Nota de credito" → "Nota de crédito"
