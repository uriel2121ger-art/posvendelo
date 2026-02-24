# Documentacion completa de debugging y fixes

## Contexto de la intervencion

Esta documentacion resume todo el trabajo de debugging realizado en modo evidenciado por runtime para el proyecto TITAN POS en arquitectura server-only.

- Sesion de debug: `5e74cc`
- Log NDJSON usado: `/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log`
- Alcance principal:
  - Compatibilidad entre `titan_gateway` (clasico) y `titan_gateway_modular`.
  - Consistencia de contratos cliente-servidor en `NetworkClient` y `MultiCajaClient`.
  - Politicas server-only (autorizacion, idempotencia, terminal_id, read-only offline).

## Archivos modificados

- `backend/app/utils/network_client.py`
- `backend/server/titan_gateway_modular.py`
- `backend/server/titan_gateway.py`
- `backend/server/routers/branches.py`
- (instrumentacion existente verificada) `backend/server/request_policies.py`

## Metodologia aplicada

1. Formular hipotesis especificas (H1...H29).
2. Instrumentar con logs NDJSON por hipotesis.
3. Reproducir con pruebas runtime (gateway clasico/modular, tokens validos e invalidos).
4. Confirmar/descartar con evidencia en log.
5. Aplicar fix minimo por hipotesis confirmada.
6. Re-verificar con evidencia post-fix.
7. Mantener instrumentacion activa para siguientes rondas.

## Resumen de hipotesis y estado

### Confirmadas y corregidas

- `H5_client_backup_attempt`
  - Se bloqueo flujo de backup iniciado por cliente (server-only backup).

- `H6_ping_route_mismatch`
  - Causa: cliente usaba `/api/health` y varios servidores exponen `/health`.
  - Fix: fallback de `ping()` a `/health` cuando `/api/health` devuelve `404`.

- `H7_branch_register_role_gap`
  - Causa: token de sucursal podia registrar sucursales.
  - Fix: solo rol `admin` puede registrar sucursales (clasico y modular).

- `H8_inventory_sync_route_mismatch`
  - Causa: falta de endpoints `v1` en modular para sync de cliente.
  - Fix: endpoints de compatibilidad `POST /api/v1/sync/sales` y `POST /api/v1/sync/{table_name}`.

- `H11_measure_latency_route_mismatch`
  - Causa: `measure_latency()` solo usaba `/api/health`.
  - Fix: fallback a `/health`.

- `H12_modular_v1_sync_missing`
  - Confirmo que el gap de rutas `v1` en modular quedo cubierto.

- `H13_inventory_movements_contract`
  - Causa: payload de `sync_inventory_movements` no coincidia con contrato (`data`, `timestamp`, `terminal_id`, `request_id`).
  - Fix: payload corregido.

- `H14_sync_status_route_missing`
  - Causa: `get_last_sync_status()` no compatible entre clasico/modular.
  - Fix:
    - endpoint modular `GET /api/v1/sync/status`,
    - fallback en cliente a `/api/status`,
    - correccion de mapeo de errores para fallback no-200.

- `H15_pull_table_get_not_supported`
  - Causa: `pull_table()` fallaba por `405` en rutas `v1` segun servidor.
  - Fix:
    - fallback para `products`,
    - extension posterior para `customers` y `sales`.

- `H16_movements_missing_connectivity_gate`
  - Causa: `sync_inventory_movements` no aplicaba politica read-only offline.
  - Fix: aplica `_ensure_connected_for_write()` como otras escrituras.

- `H19_pull_inventory_contract`
  - Causa: `pull_inventory()` en clasico caia en `405`.
  - Fix: fallback a `/api/sync/products`.

- `H20_pull_sales_contract`
  - Causa: `pull_sales()` en clasico caia en `405`.
  - Fix: fallback a `/api/reports/sales`.

- `H21_auth_test_route_missing`
  - Causa: `/api/auth/test` faltante en clasico.
  - Fix:
    - endpoint compat en modular,
    - fallback en cliente a `/api/status`,
    - correccion de mapping para token invalido (`401`) evitando `null`.

- `H22_sales_pull_source_mismatch`
  - Causa: ventas se guardaban en JSONL y pull no leia correctamente esa fuente.
  - Fix: lectura directa de JSONL en modular para `sales`.

- `H23_sync_status_not_updated`
  - Causa: sync `v1` no actualizaba `last_sync`.
  - Fix: helper `_update_last_sync()` llamado tras sync exitoso.

- `H24_get_server_info_status_missing`
  - Causa: `get_server_info()` usaba `/api/info` no disponible en clasico.
  - Fix:
    - endpoint compat `/api/info` en modular,
    - fallback cliente a `/api/status`,
    - mapeo correcto de error fallback (`401`, etc.).

- `H25_router_import_strategy`
  - Causa: import strategy en modular provocaba errores de contexto de paquete.
  - Fix: priorizar import por paquete `server.routers` con fallback controlado.

- `H26_products_pull_source_split`
  - Causa: productos de dos fuentes sin deduplicacion semantica.
  - Fix: merge con deduplicacion por `sku`/`id` (preferencia por registro mas reciente en orden de merge).

- `H27_pull_customers_contract`
  - Causa: `pull_customers()` en clasico caia en `405`.
  - Fix: fallback a `/api/customers`.

- `H28_pull_sales_since_filter`
  - Causa: fallback de `pull_sales()` ignoraba `since`.
  - Fix: filtro client-side por `timestamp/_received_at/created_at`.

- `H29_pull_table_classic_fallbacks`
  - Causa: `pull_table(customers/sales)` no tenia fallback en clasico.
  - Fix: fallbacks completos por tabla.

### Confirmadas como evidencia de politicas (sin cambio adicional mayor)

- `H1_terminal_id_missing` (validaciones activas)
- `H2_missing_idempotency_key` (instrumentacion de ausencia de key)
- `H3_idempotency_duplicate` (deduplicacion funcional)
- `H4_connectivity_gate` (read-only offline activo)

## Cambios funcionales clave por modulo

### Cliente (`network_client.py`)

- Robustez de health checks (`ping`, `measure_latency`).
- Compatibilidad clasico/modular para:
  - `get_server_info`
  - `test_api_token`
  - `get_last_sync_status`
  - `pull_inventory`, `pull_sales`, `pull_customers`
  - `pull_table(products/customers/sales)`
- Correccion de contrato en `sync_inventory_movements`.
- Aplicacion uniforme de politica read-only offline en escrituras.
- Mejoras de mapeo de errores (evitar `null` y devolver codigo real del fallback).

### Servidor modular (`titan_gateway_modular.py`)

- Endpoints de compatibilidad agregados:
  - `POST /api/v1/sync/sales`
  - `POST /api/v1/sync/{table_name}`
  - `GET /api/v1/sync/status`
  - `GET /api/v1/sync/{table_name}`
  - `GET /api/auth/test`
  - `GET /api/info`
- Soporte de lectura de ventas desde JSONL.
- Actualizacion de `last_sync` despues de sync exitoso.
- Merge de productos de fuentes multiples con deduplicacion semantica.
- Estrategia de imports de routers estabilizada.

### Servidor clasico / routers

- Restriccion de seguridad en registro de sucursales para solo admin.
- Refuerzo de politicas de backup server-only.

## Evidencia y validacion

Se realizaron multiples ciclos de:

- levantado de servidores (`titan_gateway` y `titan_gateway_modular`),
- ejecucion de flujos con token valido/invalido,
- pruebas de rutas de sync/pull/status/auth,
- verificacion de idempotencia con claves repetidas,
- verificacion de modo offline read-only,
- validacion de no regresion entre clasico y modular.

Los resultados se validaron siempre con logs NDJSON por hipotesis y con salidas runtime de cliente.

## Estado actual

- Compatibilidad cliente-servidor entre clasico y modular: **ampliamente mejorada**.
- Politicas server-only clave (rol, terminal_id, idempotencia, offline read-only): **operativas**.
- Contratos `v1` de sync/pull/status/auth/info: **normalizados** con fallbacks.
- Dedupe de productos en merge multi-fuente: **aplicado**.

## Riesgos residuales y siguientes pasos recomendados

1. Consolidar contratos en una sola fuente (idealmente eliminar duplicidad clasico/modular a mediano plazo).
2. Agregar tests automatizados de compatibilidad cruzada (clasico/modular) para:
   - auth/info/status,
   - pull_table por tabla,
   - filtros `since`,
   - idempotencia por ruta.
3. Definir politicas de precedence de campos para merge de productos (si hay conflicto de `sku` con valores distintos).
4. Cuando se cierre el ciclo de debugging, remover o reducir instrumentacion de logs para produccion.

## Nota

Esta documentacion cubre los cambios aplicados durante la sesion de debugging evidenciado por runtime.  
Si se requiere, se puede generar una version ejecutiva (1-2 paginas) y una version tecnica de traspaso para el equipo de desarrollo/soporte.

## Anexo 2026-02-22 - Fixes de scaffold Electron

Se realizo una ronda de correccion sobre `frontend/electron_pos` (Electron + React + Vite + TypeScript + Tailwind), porque el estado inicial no compilaba.

### Hallazgos

- Dependencia faltante: `react-router-dom`.
- Error de TypeScript en `App.tsx` por uso de `JSX.Element`.
- Configuracion Tailwind v4 incompleta para PostCSS.
- Build fallando por `@apply bg-zinc-900` en CSS base.

### Fixes aplicados

- Instaladas dependencias: `react-router-dom` y `@tailwindcss/postcss`.
- Actualizado `postcss.config.js` para usar plugin `@tailwindcss/postcss`.
- Ajustado `App.tsx` para eliminar el tipado de retorno que rompia typecheck.
- Migrado `main.css` a `@import "tailwindcss"` y estilos base explicitos.

### Validacion

- `npm run typecheck` en verde.
- `npm run build` en verde, con salida en `out/main`, `out/preload`, `out/renderer`.

### Documentos generados

- `frontend/electron_pos/CHANGELOG.md`
- `frontend/electron_pos/INFORME_FIXES_INICIAL_ELECTRON.md`
