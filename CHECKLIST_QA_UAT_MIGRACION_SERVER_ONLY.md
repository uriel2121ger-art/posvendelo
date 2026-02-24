# Checklist QA/UAT — Migración Server-Only DB

Usa este checklist en orden. Marca cada punto solo si tienes evidencia (captura, log o acta).

## 0) Preparación

- [ ] Confirmar versión de servidor y cliente bajo prueba.
- [ ] Confirmar ambiente: `lab` / `staging` / `piloto sucursal`.
- [ ] Confirmar token admin en entorno (`TITAN_GATEWAY_ADMIN_TOKEN`) y sin hardcodes.
- [ ] Confirmar backup inicial realizado antes de pruebas.
- [ ] Confirmar rollback documentado disponible.

## 1) Conectividad y salud base

- [ ] `GET /health` responde `200` en servidor.
- [ ] Cliente conecta a servidor por LAN/WLAN con token válido.
- [ ] Token inválido es rechazado (`401`).
- [ ] Branch token no puede operar sobre otra sucursal (`403` esperado).

## 2) Flujo de venta (core)

- [ ] Crear venta desde cliente.
- [ ] Confirmar persistencia en servidor (no local business DB).
- [ ] Confirmar historial refleja la venta.
- [ ] Confirmar venta contiene `terminal_id`.
- [ ] Confirmar no hay inconsistencias de inventario tras venta.

## 3) Edición de catálogo y clientes

- [ ] Crear producto desde cliente.
- [ ] Editar producto (precio/stock/nombre) desde cliente.
- [ ] Crear/editar cliente desde cliente.
- [ ] Confirmar todo persiste en servidor y es visible en otra terminal.

## 4) Inventario y concurrencia mínima

- [ ] Ajuste de inventario desde terminal A se refleja en terminal B.
- [ ] Dos ventas simultáneas del mismo SKU no dejan stock negativo indebido.
- [ ] Confirmar respuesta controlada cuando no hay stock suficiente.

## 5) Política offline (solo lectura)

- [ ] Cortar red en cliente (simulación controlada).
- [ ] Verificar que cliente no permite ventas/ediciones/facturación.
- [ ] Verificar que cliente sí permite consultas/historial.
- [ ] Reestablecer red y confirmar recuperación normal.

## 6) Idempotencia (no duplicados)

- [ ] Repetir misma operación crítica con misma `request_id` o `X-Idempotency-Key`.
- [ ] Verificar respuesta deduplicada.
- [ ] Confirmar que no se crea segunda venta/factura/ajuste.

## 7) Facturación centralizada

- [ ] Cliente solicita facturación (flujo cliente -> servidor).
- [ ] Servidor timbra y persiste resultado fiscal.
- [ ] Respuesta incluye vínculo `sale_id` + `terminal_id` + identificador fiscal.
- [ ] Error de timbrado devuelve mensaje controlado (sin romper operación).

## 8) Backup/restore server-only

- [ ] Backup en servidor funciona (`TITAN_NODE_ROLE=server`).
- [ ] Intento de backup desde cliente es bloqueado.
- [ ] Restore de prueba en ambiente controlado completado.
- [ ] Evidencia de restore guardada.

## 9) Seguridad mínima operativa

- [ ] `instalar_sucursal.sh` solicita token/env; no usa token embebido.
- [ ] No hay secretos nuevos hardcodeados en scripts.
- [ ] Puertos expuestos mínimos según política local.
- [ ] Logs no exponen datos sensibles innecesarios.

## 10) Observabilidad y alertas

- [ ] Se generan eventos en `gateway_data/events.jsonl`.
- [ ] Eventos críticos incluyen `branch_id` y `terminal_id`.
- [ ] Simular falla API y validar alerta P1.
- [ ] Simular error fiscal repetido y validar alerta P1.

## 11) Compatibilidad de versiones

- [ ] Cliente compatible conecta y opera normalmente.
- [ ] Cliente incompatible es bloqueado con mensaje operativo.
- [ ] Procedimiento de actualización/rollback por versión probado.

## 12) Go/No-Go piloto sucursal

- [ ] 48–72h piloto sin incidentes severos.
- [ ] KPIs dentro de umbral (disponibilidad, latencia, timbrado, sync).
- [ ] SOP de Go/No-Go firmado.
- [ ] Si falla criterio, ejecutar SOP de rollback y cerrar incidente.

---

## Evidencia mínima por prueba

- [ ] Fecha/hora
- [ ] Sucursal
- [ ] Terminal
- [ ] Responsable
- [ ] Resultado (OK/FAIL)
- [ ] Evidencia (captura/log/folio)
- [ ] Ticket de incidente (si aplica)

