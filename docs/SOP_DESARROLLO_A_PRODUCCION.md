# SOP — Desarrollo a Producción (Desktop POS)

## Objetivo
Estandarizar cómo promover cambios desde desarrollo hasta producción con riesgo controlado en sucursales.

## Alcance
- Cambios en servidor y clientes de POS.
- Cambios funcionales, técnicos y de seguridad.

## Flujo oficial de ramas
1. `feature/*`: desarrollo de cambio.
2. `develop`: integración.
3. `release/*`: estabilización para salida.
4. `main`: producción.

## Requisitos de entrada por etapa
- `feature/*` -> `develop`
  - Revisión técnica aprobada.
  - Pruebas unitarias/locales en verde.
- `develop` -> `release/*`
  - Pruebas críticas en verde: venta, inventario, clientes, facturación, historial por terminal.
  - Sin hallazgos de seguridad alta/crítica abiertos.
- `release/*` -> `main`
  - Smoke test en staging.
  - Plan de rollback validado por sucursal.
  - Aprobación Go/No-Go.

## Checklist previo a despliegue
- [ ] Versionado de artefacto definido (`server_version`, `client_version`).
- [ ] Matriz de compatibilidad cliente-servidor validada.
- [ ] Backup reciente y restore de prueba exitoso.
- [ ] Ventana de cambio comunicada a operación.
- [ ] Responsable on-call asignado.

## Estrategia de despliegue
1. Ola 0: staging/lab.
2. Ola 1: piloto (1-2 sucursales).
3. Ola 2: parcial (20-30% sucursales).
4. Ola 3: total.

## Evidencia obligatoria de salida
- Resultado de pruebas críticas.
- Registro de versión desplegada por sucursal.
- Estado de alertas P1 después de despliegue.
- Acta de aceptación operativa.

## Criterios de abortar despliegue
- Falla de facturación/timbrado repetida.
- Errores de venta duplicada o pérdida de inventario.
- Inestabilidad de API/BD en servidor.

