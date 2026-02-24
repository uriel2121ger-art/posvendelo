# Tercera capa de informe — Plan de acción priorizado

Plan propuesto por fases, con impacto/esfuerzo y orden recomendado para un entorno productivo POS.

## Fase 0 — Control y respaldo (1 día)

- Congelar snapshot actual de producción (zip + checksum) antes de cambios estructurales.
- Definir carpeta canónica de desarrollo (`backend` o `frontend`) para evitar divergencia doble.
- Establecer checklist de rollback por sucursal.

## Fase 1 — Higiene operativa y espacio (1-2 días)

- Excluir de control y de despliegue: `.venv`, `__pycache__`, `*.pyc`, logs y exportes CSV/XLSX temporales.
- Implementar rotación de logs (`max size` + `retention`) para `debug.log` y `crash_debug.log`.
- Mover exportes de ventas a carpeta de datos externa a código.
- Resultado esperado: reducción fuerte de tamaño y ruido operativo.

## Fase 2 — Unificación de fuente única (2-4 días)

- Consolidar en **un solo árbol fuente**; generar artefactos cliente/servidor desde build o configuración, no por copia manual.
- Mantener rol por configuración (`server`/`client`) como ya opera en producción.
- Verificar igualdad funcional con pruebas de caja: venta, corte, sync, fiscal.

## Fase 3 — Riesgo técnico en hotspots (3-7 días)

- Refactor incremental de módulos con mayor LOC/riesgo (`pos_engine`, `http_server`, `core`, `sync`, fiscal críticos).
- Dividir funciones largas en servicios pequeños con contratos claros.
- Añadir pruebas dirigidas en rutas críticas (cobro, timbrado, sync, reconexión).

## Fase 4 — Seguridad y cumplimiento (2-5 días)

- Revisar hallazgos de patrones sensibles y clasificar: secreto real vs falso positivo.
- Centralizar secretos en entorno seguro (`.env` fuera de repo / vault local por sitio).
- Política de minimización de datos sensibles en logs.

## Fase 5 — Observabilidad productiva (1-3 días)

- Estandarizar logs JSON por evento crítico (venta, factura, sync, error DB).
- Correlación por `terminal_id`, `turn_id`, `sale_id`, `sync_batch_id`.
- Alertas: errores de timbrado, cola de sync atascada, caída de servidor principal.

## Matriz rápida impacto/esfuerzo

| Acción | Impacto | Esfuerzo | Prioridad |
|---|---:|---:|---:|
| Rotación de logs + limpieza pyc/venv en despliegue | Alto | Bajo | P1 |
| Unificar frontend/backend en fuente única | Muy alto | Medio | P1 |
| Pruebas de regresión en venta/fiscal/sync | Muy alto | Medio | P1 |
| Refactor hotspots (pos_engine/http_server) | Alto | Alto | P2 |
| Hardening de secretos y compliance | Alto | Medio | P1 |
