# Pipeline de Promoción Dev -> Prod

## Flujo
1. `feature/*` -> `develop`
2. `develop` -> `release/*`
3. `release/*` -> `main`

## Gates obligatorios
- Lint y chequeos estáticos.
- Pruebas críticas: venta, inventario, clientes, facturación, historial por terminal.
- Smoke test en staging.
- Aprobación comité Go/No-Go.

## Despliegue
- Ola 1: piloto 1-2 sucursales.
- Ola 2: parcial 20-30%.
- Ola 3: total.

## Rollback
- Versión anterior pre-validada por sucursal.
- Tiempo objetivo de rollback <= 20 minutos.
- Evidencia post-rollback obligatoria.

