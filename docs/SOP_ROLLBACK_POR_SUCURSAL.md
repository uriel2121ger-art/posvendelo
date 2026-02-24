# SOP — Rollback por Sucursal

## Objetivo
Restaurar operación estable en una sucursal ante fallas post-despliegue.

## Disparadores de rollback
- Error crítico en ventas.
- Error fiscal/timbrado persistente.
- Incompatibilidad cliente-servidor.
- Degradación severa de rendimiento en caja.

## Tiempo objetivo
- Detección a decisión: <= 10 min.
- Ejecución rollback técnico: <= 20 min.
- Validación post-rollback: <= 15 min.

## Procedimiento
1. Declarar incidente y congelar nuevos despliegues.
2. Identificar sucursal y versión afectada.
3. Activar rollback de servidor a versión estable previa.
4. Revertir clientes de la sucursal a versión compatible previa.
5. Verificar conectividad cliente-servidor.
6. Ejecutar pruebas rápidas:
   - venta de prueba
   - actualización inventario
   - consulta historial por terminal
   - facturación de prueba (si aplica)
7. Confirmar normalización con encargado de sucursal.

## Datos y seguridad
- No borrar evidencia del incidente.
- Conservar logs antes y después del rollback.
- Registrar causa preliminar y acciones inmediatas.

## Criterios de cierre
- Operación estable por 30 minutos sin alertas P1.
- Pruebas funcionales mínimas en verde.
- Ticket de incidente actualizado con versión final operativa.

