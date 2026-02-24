# Anexo — Refactor por archivo (priorizado)

Lista accionable basada en riesgo, tamaño, criticidad operativa y probabilidad de regresión.

## Criterios usados

- Criticidad de negocio: venta, timbrado, sync, servidor.
- Complejidad (LOC) y acoplamiento.
- Superficie de falla en producción.
- Duplicación `frontend`/`backend` (trabajar en una fuente canónica).

## Bloque P1 (arranque inmediato)

| Prioridad | Archivo | Problema principal | Refactor recomendado | Riesgo | Esfuerzo estimado |
|---|---|---|---|---|---|
| P1 | `backend/src/services/pos_engine.py` | Núcleo de negocio muy grande y acoplado | Extraer servicios por dominio (ventas, descuentos, pagos, validaciones), reducir funciones largas, contratos claros | Alto | 24-40 h |
| P1 | `backend/app/services/http_server.py` | Endpoint layer extensa y mezcla de responsabilidades | Separar routers por contexto (ventas, inventario, clientes, fiscal), middlewares comunes, manejo uniforme de errores | Alto | 20-32 h |
| P1 | `backend/app/core.py` | Fachada monolítica (orquesta demasiado) | Convertir en orquestador delgado; mover lógica a servicios/coordinadores | Alto | 24-36 h |
| P1 | `backend/src/services/fiscal/cfdi_service.py` | Flujo fiscal crítico y sensible | Pipeline explícito (validar->construir->timbrar->persistir), errores tipados, reintentos controlados | Alto | 16-28 h |
| P1 | `backend/src/services/fiscal/facturapi_connector.py` | Integración externa extensa | Cliente HTTP aislado + DTOs + normalización de errores + timeout/retry/backoff | Alto | 16-28 h |
| P1 | `backend/app/services/sync_engine.py` | Consistencia intersucursal | Particionar por etapas (extract/apply/conflict), trazabilidad por `sync_batch_id` | Alto | 12-20 h |

## Bloque P2 (después de estabilizar P1)

| Prioridad | Archivo | Problema principal | Refactor recomendado | Riesgo | Esfuerzo estimado |
|---|---|---|---|---|---|
| P2 | `backend/app/wizards/import_wizard.py` | Wizard muy largo y difícil de mantener | Separar páginas, validadores y adaptadores de importación por tipo de dato | Medio-Alto | 18-30 h |
| P2 | `backend/app/ui/sales_tab.py` | UI enorme con lógica embebida | MVP/MVVM ligero: presenters/controllers + widgets pequeños | Medio-Alto | 28-44 h |
| P2 | `backend/app/ui/settings_tab.py` | Configuración compleja y acoplada | Módulos por sección de settings y esquema de validación central | Medio | 18-30 h |
| P2 | `backend/app/utils/sync_config.py` | Configuración extensa con deuda técnica | Separar carga, validación, defaults y persistencia | Medio | 10-16 h |
| P2 | `backend/app/services/http_server_MERGED.py` | Duplicidad con `http_server.py` | Definir archivo canónico y retirar el alterno de forma controlada | Medio | 6-12 h |

## Bloque P3 (optimización continua)

| Prioridad | Archivo/Área | Mejora | Esfuerzo |
|---|---|---|---|
| P3 | `backend/src/services/fiscal/global_invoicing.py` | Reducir complejidad ciclomática, utilidades compartidas | 8-14 h |
| P3 | `backend/src/services/fiscal/rfc_validator.py` | Normalizar reglas y mensajes de validación | 6-10 h |
| P3 | `backend/server/titan_gateway.py` | Revisar límites de responsabilidad gateway vs servicios | 12-20 h |
| P3 | scripts de despliegue/backup | Quitar secretos hardcodeados y unificar parámetros | 6-12 h |

## Orden sugerido de ejecución (semanal)

1. Semana 1-2: `pos_engine`, `http_server`, `core` (solo estructura y contratos).
2. Semana 3: `cfdi_service`, `facturapi_connector`, `sync_engine`.
3. Semana 4-5: `import_wizard`, `sales_tab`, `settings_tab`.
4. Semana 6: consolidación (`http_server_MERGED`, `sync_config`, limpieza técnica).

## Nota importante por duplicación frontend/backend

- Ejecutar refactor primero en **fuente canónica** (recomendado: `backend/`).
- Replicar a `frontend/` solo cuando el cambio esté validado.
- Ideal: converger a un solo árbol fuente para evitar doble mantenimiento.
