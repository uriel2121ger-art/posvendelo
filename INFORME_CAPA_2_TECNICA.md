# Segunda capa de informe — Análisis técnico profundo

Análisis derivado del inventario total, con enfoque en arquitectura real, riesgos operativos, seguridad y mantenibilidad.

## 1) Arquitectura y duplicación

- Archivos en `frontend`: **16,509**
- Archivos en `backend`: **16,508**
- Rutas relativas comunes: **16,491**
- Comunes idénticas (mismo hash): **11,671**
- Comunes distintas: **4,820**
- Tamaño idéntico duplicado estimado: **618,726,581 bytes** (~0.576 GB)

- Proporción de coincidencia exacta frontend/backend: **70.77%**

## 2) Complejidad de código (LOC)

- Archivos de código analizados (sin `.venv` ni `__pycache__`): **946**
- Archivos Python analizados: **833**

### Top 15 archivos Python por LOC

- `backend/app/ui/sales_tab.py` — 4,480 LOC (3,939 no vacías)
- `frontend/app/ui/sales_tab.py` — 4,480 LOC (3,939 no vacías)
- `backend/app/core.py` — 3,812 LOC (3,360 no vacías)
- `frontend/app/core.py` — 3,812 LOC (3,360 no vacías)
- `backend/app/ui/settings_tab.py` — 3,461 LOC (2,977 no vacías)
- `frontend/app/ui/settings_tab.py` — 3,461 LOC (2,977 no vacías)
- `backend/src/services/pos_engine.py` — 2,490 LOC (2,146 no vacías)
- `frontend/src/services/pos_engine.py` — 2,490 LOC (2,146 no vacías)
- `backend/server/titan_gateway.py` — 2,447 LOC (2,057 no vacías)
- `frontend/server/titan_gateway.py` — 2,447 LOC (2,057 no vacías)
- `backend/app/wizards/import_wizard.py` — 2,390 LOC (2,070 no vacías)
- `frontend/app/wizards/import_wizard.py` — 2,390 LOC (2,070 no vacías)
- `backend/app/services/http_server.py` — 2,157 LOC (1,914 no vacías)
- `frontend/app/services/http_server.py` — 2,157 LOC (1,914 no vacías)
- `backend/app/ui/welcome_wizard.py` — 1,967 LOC (1,730 no vacías)

## 3) Riesgo operativo por artefactos

- `virtualenv`: 31,074 archivos | 1,366,030,842 bytes (~1302.75 MB)
- `cache_pyc`: 10,442 archivos | 183,922,618 bytes (~175.40 MB)
- `logs`: 14 archivos | 172,428,556 bytes (~164.44 MB)
- `exports_csv_xlsx`: 78 archivos | 27,625,827 bytes (~26.35 MB)
- `zip_backups`: 4 archivos | 503,217,506 bytes (~479.91 MB)

## 4) Dependencias

- `frontend/requirements.txt`: 27 entradas no comentadas
- `backend/requirements.txt`: 27 entradas no comentadas

- Diferencias de líneas de dependencias entre `frontend/requirements.txt` y `backend/requirements.txt`: 0

## 5) Hallazgos de seguridad (barrido de patrones)

- Coincidencias totales de patrones sensibles: **6**
- `password_assignment`: 4
- `api_key_assignment`: 2

### Muestras (primeras 20)

- `backend/scripts/backup_postgresql.sh:42` [password_assignment] -> `export PGPASSWORD="$PASSWORD"`
- `backend/scripts/restore_postgresql.sh:52` [password_assignment] -> `export PGPASSWORD="$PASSWORD"`
- `backend/server/instalar_sucursal.sh:31` [api_key_assignment] -> `ADMIN_TOKEN="sOha_F4JGLhkCB7ERzgqrmLAQmJsX4NMISXyNHrjV6Y"`
- `frontend/scripts/backup_postgresql.sh:42` [password_assignment] -> `export PGPASSWORD="$PASSWORD"`
- `frontend/scripts/restore_postgresql.sh:52` [password_assignment] -> `export PGPASSWORD="$PASSWORD"`
- `frontend/server/instalar_sucursal.sh:31` [api_key_assignment] -> `ADMIN_TOKEN="sOha_F4JGLhkCB7ERzgqrmLAQmJsX4NMISXyNHrjV6Y"`

## 6) Hotspots de riesgo técnico (heurístico)

- score 8 | `backend/src/services/pos_engine.py` | 2,490 LOC
- score 8 | `frontend/src/services/pos_engine.py` | 2,490 LOC
- score 8 | `backend/app/services/http_server.py` | 2,157 LOC
- score 8 | `frontend/app/services/http_server.py` | 2,157 LOC
- score 7 | `backend/app/core.py` | 3,812 LOC
- score 7 | `frontend/app/core.py` | 3,812 LOC
- score 7 | `backend/src/services/fiscal/facturapi_connector.py` | 1,017 LOC
- score 7 | `frontend/src/services/fiscal/facturapi_connector.py` | 1,017 LOC
- score 7 | `backend/app/services/http_server_MERGED.py` | 905 LOC
- score 7 | `frontend/app/services/http_server_MERGED.py` | 905 LOC
- score 7 | `backend/src/services/fiscal/cfdi_service.py` | 858 LOC
- score 7 | `frontend/src/services/fiscal/cfdi_service.py` | 858 LOC
- score 6 | `backend/app/utils/sync_config.py` | 1,828 LOC
- score 6 | `frontend/app/utils/sync_config.py` | 1,828 LOC
- score 6 | `backend/src/services/fiscal/global_invoicing.py` | 697 LOC
- score 6 | `frontend/src/services/fiscal/global_invoicing.py` | 697 LOC
- score 6 | `backend/app/services/sync_engine.py` | 598 LOC
- score 6 | `frontend/app/services/sync_engine.py` | 598 LOC
- score 6 | `backend/src/services/fiscal/rfc_validator.py` | 497 LOC
- score 6 | `frontend/src/services/fiscal/rfc_validator.py` | 497 LOC

## Conclusión técnica de capa 2

- El repositorio contiene dos árboles casi espejados (`frontend` y `backend`) con alta duplicación real.
- La mayor parte del peso proviene de `.venv`, binarios y cachés compilados (`.pyc`).
- Hay archivos grandes de logs/exportes en el árbol de app que conviene externalizar o rotar.
- La complejidad se concentra en motores/servicios nucleares (POS, HTTP server, sync, fiscal).
