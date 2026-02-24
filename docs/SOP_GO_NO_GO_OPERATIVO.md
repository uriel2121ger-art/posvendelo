# SOP — Comité Go/No-Go Operativo

## Objetivo
Tomar decisión formal de salida a producción con criterios técnicos y operativos verificables.

## Participantes mínimos
- Líder técnico
- QA
- Operaciones/Soporte sucursal
- Seguridad TI
- Responsable de producto/negocio

## Criterios GO
- [ ] Pruebas críticas en verde (venta, inventario, clientes, facturación, historial por terminal).
- [ ] Compatibilidad cliente-servidor validada.
- [ ] Backup/restore verificados.
- [ ] Alertas P1 configuradas y monitoreo activo.
- [ ] Plan de rollback confirmado por sucursal objetivo.

## Criterios NO-GO
- [ ] Hallazgo de seguridad alta/crítica sin mitigación.
- [ ] Fallos de timbrado repetidos en staging/piloto.
- [ ] Riesgo de duplicidad de ventas no resuelto.
- [ ] Operaciones sin cobertura on-call en ventana de cambio.

## Formato de decisión
- Estado final: `GO` o `NO-GO`.
- Motivo resumido (3 líneas máximo).
- Riesgos residuales aceptados.
- Responsable de seguimiento.

## Acciones posteriores
- Si `GO`: ejecutar despliegue por ola y monitoreo reforzado 24-72h.
- Si `NO-GO`: abrir plan de remediación, nueva fecha propuesta y criterios de re-evaluación.

