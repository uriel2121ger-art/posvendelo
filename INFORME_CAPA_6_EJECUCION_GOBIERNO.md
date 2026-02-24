# Etapa 6 — Ejecución, gobierno y control de cambio

Esta etapa convierte las capas 1-5 en un plan operativo ejecutable para producción, sin tocar código en esta fase.

## Objetivo de la etapa

- Pasar de diagnóstico a ejecución controlada.
- Reducir riesgo operativo durante despliegues y cambios estructurales.
- Asegurar trazabilidad: responsable, evidencia, criterio de éxito y rollback.

## Entradas usadas

- Inventario total (33,025 archivos).
- Capa 2 técnica (duplicación, hotspots, riesgos).
- Capa 3 plan priorizado (fases P1/P2).
- Capa 4 seguridad/compliance (hallazgos de credenciales/tokens).
- Capa 5 observabilidad (señales actuales + modelo objetivo).

## 1) Modelo de gobierno propuesto

- Cadencia: comité semanal Go/No-Go (PM, TI, QA, Seguridad, Operaciones).
- Regla de cambio: nada pasa a producción sin evidencia de prueba + rollback probado.
- Política de incidentes: evento P1 detiene ola de despliegue automáticamente.
- Trazabilidad: cada cambio con ticket, dueño, riesgo y validación post-cambio.

## 2) KPIs y umbrales ejecutivos

- Disponibilidad servidor POS >= 99.5%.
- Error de timbrado diario < 1%.
- P95 registro de venta < 800 ms.
- Backlog de sync dentro de umbral definido por sucursal.
- MTTR incidentes P1 <= 30 min (objetivo).

## 3) Criterios Go / No-Go

### Go

- Suite crítica (venta/fiscal/sync) en verde.
- Backups/restores verificados en ambiente objetivo.
- Observabilidad activa con alertas P1 operativas.
- Dueños on-call asignados durante ventana de cambio.

### No-Go

- Hallazgo de seguridad alta/crítica sin contención.
- Rollback no probado en la sucursal objetivo.
- Fallos repetidos en timbrado/sync durante piloto.
- Falta de confirmación de operación/soporte local.

## 4) Plan de despliegue por olas

- Ola 0: laboratorio + staging interno.
- Ola 1: 1-2 sucursales piloto (48-72h de observación).
- Ola 2: 20-30% sucursales (despliegue gradual por ventana).
- Ola 3: 100% con seguimiento reforzado 7 días.

## 5) Riesgos de ejecución y mitigación

- Divergencia de código `frontend/backend` -> definir carpeta canónica y bloqueo de cambios paralelos.
- Exposición de tokens/credenciales en scripts -> saneo de secretos previo a rollout masivo.
- Saturación por logs/artefactos -> política de rotación y retención desde día 1.
- Falta de evidencia de pruebas -> gate obligatorio antes de cada ola.

## 6) Entregables de etapa 6

- `ANEXO_CAPA_6_RACI.csv` (responsabilidades).
- `ANEXO_CAPA_6_PLAN_90_DIAS.csv` (cronograma 90 días).
- `ANEXO_CAPA_6_CHECKLIST_GO_LIVE.md` (checklist sucursal).

## Dictamen etapa 6

- El proyecto ya tiene insumos suficientes para entrar en ejecución controlada.
- El mayor beneficio inmediato viene de: (1) fuente única, (2) seguridad de secretos, (3) observabilidad mínima operativa.
- Recomendación: arrancar semana 1 con comité Go/No-Go y piloto controlado.
