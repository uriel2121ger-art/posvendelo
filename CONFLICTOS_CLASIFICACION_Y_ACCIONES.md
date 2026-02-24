# Conflictos de Clasificación y Acciones

## Conflictos detectados
- Duplicación funcional entre `backend/` y `frontend/`.
- Endpoints duplicados en `backend/server/titan_gateway.py` y routers modulares.
- Scripts con secretos embebidos (`instalar_sucursal.sh` histórico).
- Backups reportados desde terminales (incompatible con política server-only).

## Acciones aplicadas
- Se agregó política server-only para backups en endpoints modulares.
- Se eliminó token hardcodeado en instalador de sucursal (ahora prompt/env).
- Se introdujo `terminal_id` obligatorio e idempotencia en endpoints críticos modulares.
- Se añadió observabilidad estructurada (`gateway_data/events.jsonl`).

## Acciones pendientes recomendadas
- Consolidar un único entrypoint de gateway (preferir modular).
- Deprecar rutas legacy duplicadas en `titan_gateway.py`.
- Unificar despliegue para evitar divergencia `frontend/backend`.

