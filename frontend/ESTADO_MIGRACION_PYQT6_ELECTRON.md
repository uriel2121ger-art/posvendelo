# Estado de migracion PyQt6 -> Electron

Fecha de corte: 2026-02-22

## Estado general

- Base Electron/Vite/React/TS: lista y validada.
- Hardening de seguridad y dependencias: aplicado.
- Auditoria NPM: 0 hallazgos en full y prod.
- Terminal POS (fase 2): funcional con logica real conectada al gateway y paridad parcial de ventas.
- Tabs F1-F8: funcionales en navegacion y operacion base (ventas, clientes, productos, inventario, turnos, reportes, historial, configuraciones).

## Lo que ya funciona (fase 2)

- Configuracion runtime de conexion (URL, token, terminal_id) en UI.
- Carga de productos desde API:
  - Primario: `GET /api/v1/sync/products`
  - Fallback clasico: `GET /api/sync/products`
- Busqueda por SKU/nombre y alta a carrito.
- Calculo de subtotal, IVA (16%) y total.
- Sincronizacion de venta:
  - `POST /api/v1/sync/sales`
  - Payload con `data`, `timestamp`, `terminal_id`, `request_id`.
- Descuento por linea de producto (%).
- Descuento global de ticket (%).
- Cliente asignado al ticket.
- Metodo de pago en ticket (`cash`, `card`, `transfer`).
- Tickets pendientes (guardar/cargar) con persistencia local.
- Tickets activos en paralelo (crear/cambiar/cerrar sin perder contexto de venta).
- Cobro en efectivo con validacion de monto recibido, faltante y cambio.
- Modulo Clientes (F2):
  - Carga de clientes desde API de sincronizacion (con fallback clasico).
  - Alta, edicion y baja logica de clientes con sincronizacion inmediata.
- Modulo Productos (F3):
  - Carga de productos desde API de sincronizacion (con fallback clasico).
  - Alta, edicion y baja logica de productos con sincronizacion inmediata.
- Modulo Inventario (F4):
  - Carga de inventario basada en catalogo de productos.
  - Movimientos de inventario por SKU (entrada/salida por cantidad).
  - Validacion de no permitir stock negativo antes de sincronizar.
- Modulo Turnos (F5):
  - Apertura de turno con operador y efectivo inicial.
  - Cierre de turno con efectivo de cierre, esperado y diferencia.
  - Persistencia local e intento de sincronizacion al backend.
  - Acumulados en vivo de turno (ventas, total, efectivo y desglose por metodo).
  - Conciliacion contra historial backend por terminal y rango del turno.
  - Exportacion CSV de corte con diferencias backend vs local.
  - Accion de esperado sugerido para cierre (prioriza efectivo conciliado backend cuando existe).
  - Reporte imprimible de corte de turno desde UI (flujo operativo de caja).
- Integracion Ventas <-> Turnos:
  - Cobro bloqueado cuando no hay turno abierto.
  - Cada venta sincronizada actualiza el acumulado del turno activo.
- Modulo Reportes (F6):
  - KPIs de ventas por rango de fechas.
  - Desglose por metodo de pago y top productos.
  - Exportacion CSV de resumen y top productos.
- Modulo Historial (F7):
  - Busqueda de ventas por folio y rango de fechas.
  - Consulta de detalle por venta.
  - Filtros avanzados por metodo de pago y rango de total.
  - Exportacion CSV de resultados filtrados.
- Modulo Configuraciones (F8):
  - Guardado de configuracion runtime (URL, token, terminal_id).
  - Prueba de conexion y consulta de estado de sincronizacion.
  - Perfiles de terminal (guardar, cargar, eliminar).

## Pendiente para estar "practicamente listo produccion"

1. Paridad funcional contra PyQt6 en modulo de ventas:
   - medios de pago avanzados (abonos parciales, mixtos, propinas)
   - cierre/corte de caja y arqueo
   - reglas de redondeo/decimal y politicas fiscales segun operacion
2. Modulos de negocio:
   - facturacion/CFDI
   - profundizar paridad funcional de reportes/historial/configuracion frente a PyQt6
   - profundizar paridad funcional de clientes/productos/inventario frente a PyQt6
3. Integraciones operativas de desktop:
   - impresion ticket/corte/cajon
   - manejo offline/read-only y cola de reintento de ventas
4. Go-Live config:
   - completar `appId`, `maintainer`, `publish.url` en `electron-builder.yml`

## Gate actual

Tecnico:

```bash
npm run verify:release
```

Go-live (incluye validacion de placeholders):

```bash
npm run verify:go-live
```
