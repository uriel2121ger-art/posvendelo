# Quinta etapa — Observabilidad operativa (sin tocar código)

Mapeo de señales actuales y diseño objetivo de monitoreo para operación POS multi-sucursal.

## Alcance

- Archivos analizados para puntos de logging/rutas/errores: **951**
- Señales detectadas: **10,605**
- Anexo de puntos detectados: `ANEXO_CAPA_5_PUNTOS_LOGGING.csv`

## Señales actuales detectadas

- `logger_obj`: 4472
- `try_except`: 4445
- `print_call`: 838
- `fastapi_route`: 342
- `http_exception`: 270
- `python_logging`: 238

## Flujos críticos identificados (por naming de módulos)

- Archivos potencialmente críticos: **256**
- `backend/app/config/sync_config.py`
- `backend/app/dialogs/cash_movement_dialog.py`
- `backend/app/dialogs/credit_payment_dialog.py`
- `backend/app/dialogs/global_invoice_dialog.py`
- `backend/app/dialogs/layaway_payment_dialog.py`
- `backend/app/dialogs/midas_payment_dialog.py`
- `backend/app/dialogs/payment_dialog.py`
- `backend/app/dialogs/turn_sales_dialog.py`
- `backend/app/fiscal/__init__.py`
- `backend/app/fiscal/auto_proxy.py`
- `backend/app/fiscal/cash_extraction.py`
- `backend/app/fiscal/cerebro_contable.py`
- `backend/app/fiscal/cfdi_builder.py`
- `backend/app/fiscal/cfdi_service.py`
- `backend/app/fiscal/cfdi_sync_service.py`
- `backend/app/fiscal/climate_shield.py`
- `backend/app/fiscal/constants.py`
- `backend/app/fiscal/cross_branch_billing.py`
- `backend/app/fiscal/crypto_bridge.py`
- `backend/app/fiscal/csd_vault.py`
- `backend/app/fiscal/discrepancy_monitor.py`
- `backend/app/fiscal/email_service.py`
- `backend/app/fiscal/error_translator.py`
- `backend/app/fiscal/facturapi_connector.py`
- `backend/app/fiscal/fiscal_dashboard.py`
- `backend/app/fiscal/global_invoicing.py`
- `backend/app/fiscal/legal_documents.py`
- `backend/app/fiscal/materiality_engine.py`
- `backend/app/fiscal/multi_emitter.py`
- `backend/app/fiscal/noise_generator.py`

## Modelo objetivo de observabilidad

### Eventos mínimos obligatorios

- `sale_created`, `sale_paid`, `sale_cancelled`, `ticket_printed`
- `invoice_requested`, `invoice_stamped`, `invoice_failed`
- `sync_started`, `sync_completed`, `sync_failed`, `sync_queue_backlog`
- `db_connect_ok`, `db_connect_failed`, `db_migration_applied`
- `terminal_online`, `terminal_offline`, `server_role_changed`

### Campos de correlación recomendados

- `timestamp`, `level`, `event`, `message`
- `store_id`, `terminal_id`, `user_id`, `turn_id`
- `sale_id`, `invoice_id`, `sync_batch_id`, `trace_id`

### SLI/SLO operativos sugeridos

- Disponibilidad de servidor POS >= 99.5%
- Tasa de error en timbrado < 1% por día
- Latencia P95 de registro de venta < 800 ms
- Backlog de sync pendiente < umbral definido por sucursal

### Alertas P1 (inmediatas)

- Caída de API/server principal
- Fallo repetido de timbrado CFDI
- Cola de sincronización atascada
- Fallo de conexión a BD en servidor designado

## Plan de implementación posterior (sin ejecutar todavía)

1. Definir contrato de log JSON único para toda la app.
2. Instrumentar primero hotspots: `pos_engine`, `http_server`, `sync_engine`, fiscal.
3. Configurar agregación central de logs por sucursal/terminal.
4. Construir tablero operativo mínimo (ventas, fiscal, sync, disponibilidad).
5. Ensayar incident response con casos reales (caída server, timbrado, red).

## Dictamen etapa 5

- Hay señales de logging, pero falta estandarización transversal orientada a operación y SLO.
- El siguiente salto de madurez es un contrato de eventos y alertas unificado por rol server/client.
