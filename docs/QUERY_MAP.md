# TITAN POS — Mapeo Completo de Queries SQL y Cadenas de Llamado

**Generado:** 2026-02-26
**Stack:** FastAPI + asyncpg (sin ORM) + PostgreSQL
**DB Wrapper:** `db/connection.py` — convierte `:name` a `$N` posicional

---

## Índice

1. [Módulos de Ruta (API Endpoints)](#1-módulos-de-ruta)
2. [Módulo Fiscal (34 clases)](#2-módulo-fiscal)
3. [Referencia de Tablas](#3-referencia-de-tablas)
4. [Seguridad de Transacciones](#4-seguridad-de-transacciones)

---

## 1. Módulos de Ruta

### 1.1 AUTH — `modules/auth/routes.py`
**Prefix:** `/api/v1/auth`

| Endpoint | Función | SQL | Tablas | Tx |
|----------|---------|-----|--------|-----|
| `POST /login` | `_do_login` | `SELECT id,username,password_hash,role,is_active FROM users WHERE username=:username AND is_active=1` | users | No |
| `GET /verify` | `verify_auth` | — (JWT decode) | — | — |

---

### 1.2 DASHBOARD — `modules/dashboard/routes.py`
**Prefix:** `/api/v1/dashboard`

| Endpoint | Función | Tablas | Tx |
|----------|---------|--------|-----|
| `GET /resico` | `get_resico_dashboard` | sales | No |
| `GET /quick` | `get_quick_status` | sales, loss_records | No |
| `GET /expenses` | `get_expenses_dashboard` | cash_movements | No |
| `GET /wealth` | `get_wealth_dashboard` | sales, cash_movements | No |
| `GET /ai` | `get_ai_dashboard` | products, sale_items, sales | No |
| `GET /executive` | `get_executive_dashboard` | sales, sale_items, products | No |

---

### 1.3 SALES — `modules/sales/routes.py`
**Prefix:** `/api/v1/sales`

#### `POST /` — create_sale (Transaction: FULL ACID)
Cadena: route → `get_connection()` → `conn.transaction()` → 12 pasos

| Paso | SQL | Tabla | Lock |
|------|-----|-------|------|
| 1 | `SELECT kit_product_id,component_product_id,quantity FROM kit_components WHERE kit_product_id = ANY($1)` | kit_components | — |
| 2 | `SELECT id,name,stock,sku,sale_type,is_kit FROM products WHERE id = ANY($1) AND is_active=1 FOR UPDATE NOWAIT` | products | **FOR UPDATE NOWAIT** |
| 3 | `SELECT id,terminal_id FROM turns WHERE user_id=:uid AND status='open' ORDER BY id DESC LIMIT 1 FOR UPDATE` | turns | **FOR UPDATE** |
| 4 | `INSERT INTO secuencias ... ON CONFLICT DO NOTHING` | secuencias | — |
| 5 | CTE: `UPDATE secuencias SET ultimo_numero=ultimo_numero+1 ... RETURNING` + `INSERT INTO sales ... RETURNING id,folio_visible` | secuencias, sales | Atómico |
| 6 | `INSERT INTO sale_items ...` (executemany batch) | sale_items | — |
| 7 | `UPDATE products SET stock=stock-d.qty FROM unnest($1::int[],$2::numeric[]) AS d(pid,qty)` | products | Batch |
| 8 | `INSERT INTO inventory_movements ...` (executemany batch) | inventory_movements | — |
| 9 | `SELECT credit_balance,credit_limit FROM customers WHERE id=:id FOR UPDATE` | customers | **FOR UPDATE** |
| 10 | `UPDATE customers SET credit_balance=credit_balance+:amount` | customers | — |
| 11 | `INSERT INTO credit_history ...` | credit_history | — |
| 12 | wallet: `SELECT wallet_balance FROM customers WHERE id=:cid FOR UPDATE` + `UPDATE wallet_balance` | customers | **FOR UPDATE** |

#### `POST /{id}/cancel` — cancel_sale (Transaction: FULL)
| Paso | SQL | Tabla | Lock |
|------|-----|-------|------|
| 1 | `SELECT * FROM sales WHERE id=:id FOR UPDATE` | sales | **FOR UPDATE** |
| 2 | `SELECT * FROM sale_items WHERE sale_id=:id` | sale_items | — |
| 3-5 | kit_components lookup + `SELECT id,sku FROM products WHERE id=ANY($1) FOR UPDATE` | kit_components, products | **FOR UPDATE** |
| 6 | `UPDATE products SET stock=stock+d.qty FROM unnest(...)` | products | Batch |
| 7 | `INSERT INTO inventory_movements` (cancellation) | inventory_movements | — |
| 8 | Credit reversal: `SELECT credit_balance FROM customers FOR UPDATE` + UPDATE + INSERT credit_history | customers, credit_history | **FOR UPDATE** |
| 9 | Wallet reversal | customers | **FOR UPDATE** |
| 10 | `UPDATE sales SET status='cancelled'` | sales | — |

#### Otros endpoints de ventas

| Endpoint | SQL principal | Tablas |
|----------|--------------|--------|
| `GET /` | `SELECT s.*,c.name FROM sales s LEFT JOIN customers c ... ORDER BY s.id DESC LIMIT :limit OFFSET :offset` | sales, customers |
| `GET /{id}` | `SELECT * FROM sales WHERE id=:id` + `SELECT * FROM sale_items WHERE sale_id=:id` | sales, sale_items |
| `GET /search` | `SELECT ... FROM sales WHERE folio_visible ILIKE :folio ...` | sales |
| `GET /{id}/events` | `SELECT * FROM sale_events WHERE sale_id=:sale_id ORDER BY sequence` | sale_events |
| `GET /reports/daily-summary` | `SELECT * FROM mv_daily_sales_summary` | mv_daily_sales_summary (CQRS) |
| `GET /reports/product-ranking` | `SELECT * FROM mv_product_sales_ranking` | mv_product_sales_ranking (CQRS) |
| `GET /reports/hourly-heatmap` | `SELECT * FROM mv_hourly_sales_heatmap` | mv_hourly_sales_heatmap (CQRS) |

---

### 1.4 PRODUCTS — `modules/products/routes.py`
**Prefix:** `/api/v1/products`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `GET /` | No | — | products |
| `GET /low-stock` | No | — | products |
| `GET /sku/{sku}` | No | — | products |
| `GET /{id}` | No | — | products |
| `POST /` | No | — | products |
| `PUT /{id}` | **SÍ** | **FOR UPDATE** | products, price_history |
| `DELETE /{id}` | **SÍ** | **FOR UPDATE** | products (soft delete) |
| `GET /scan/{sku}` | No | — | products |
| `POST /stock` | **SÍ** | **FOR UPDATE** | products, inventory_movements |
| `POST /price` | **SÍ** | **FOR UPDATE** | products, price_history |
| `GET /categories/list` | No | — | products |

---

### 1.5 CUSTOMERS — `modules/customers/routes.py`
**Prefix:** `/api/v1/customers`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `GET /` | No | — | customers |
| `GET /{id}` | No | — | customers |
| `GET /{id}/sales` | No | — | sales |
| `POST /` | No | — | customers |
| `PUT /{id}` | **SÍ** | **FOR UPDATE** | customers |
| `DELETE /{id}` | **SÍ** | **FOR UPDATE** | customers (soft delete) |
| `GET /{id}/credit` | No | — | customers, sales |

---

### 1.6 INVENTORY — `modules/inventory/routes.py`
**Prefix:** `/api/v1/inventory`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `GET /movements` | No | — | inventory_movements |
| `GET /alerts` | No | — | products |
| `POST /adjust` | **SÍ** | **FOR UPDATE** | products, inventory_movements |

---

### 1.7 TURNS — `modules/turns/routes.py`
**Prefix:** `/api/v1/turns`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `POST /open` | **SÍ** | **FOR UPDATE** (prevent double) | turns |
| `POST /{id}/close` | **SÍ** | **FOR UPDATE** | turns, sales, cash_movements |
| `GET /current` | No | — | turns |
| `GET /{id}` | No | — | turns |
| `GET /{id}/summary` | No | — | turns, sales, cash_movements |
| `POST /{id}/movements` | **SÍ** | **FOR UPDATE** (turn + PIN) | employees, turns, cash_movements |

---

### 1.8 EMPLOYEES — `modules/employees/routes.py`
**Prefix:** `/api/v1/employees`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `GET /` | No | — | employees |
| `GET /{id}` | No | — | employees |
| `POST /` | No | — | employees |
| `PUT /{id}` | **SÍ** | **FOR UPDATE** | employees |
| `DELETE /{id}` | **SÍ** | **FOR UPDATE** | employees (soft delete) |

---

### 1.9 EXPENSES — `modules/expenses/routes.py`
**Prefix:** `/api/v1/expenses`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `GET /summary` | No | — | cash_movements |
| `POST /` | **SÍ** | **FOR UPDATE** (turn) | turns, cash_movements |

---

### 1.10 MERMAS — `modules/mermas/routes.py`
**Prefix:** `/api/v1/mermas`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `GET /pending` | No | — | loss_records |
| `POST /approve` | **SÍ** | **FOR UPDATE** (merma + product) | loss_records, products, inventory_movements |

---

### 1.11 SYNC — `modules/sync/routes.py`
**Prefix:** `/api/v1/sync`

| Endpoint | Tx | Tablas | Notas |
|----------|-----|--------|-------|
| `GET /products` | No | products | cursor-based pagination |
| `GET /customers` | No | customers | cursor-based |
| `GET /sales` | No | sales | `timestamp >= :since` (string ISO) |
| `GET /shifts` | No | turns | solo open |
| `GET /status` | No | — | `SELECT 1` |
| `POST /{table}` | **SÍ** | products, customers | UPSERT + FOR UPDATE |

---

### 1.12 REMOTE — `modules/remote/routes.py`
**Prefix:** `/api/v1/remote`

| Endpoint | Tx | Lock | Tablas |
|----------|-----|------|--------|
| `POST /open-drawer` | No | — | app_config, audit_log |
| `GET /turn-status` | No | — | turns, users, sales |
| `GET /live-sales` | No | — | sales, customers |
| `POST /notification` | No | — | remote_notifications |
| `GET /notifications/pending` | **SÍ** | **FOR UPDATE** | remote_notifications |
| `POST /change-price` | **SÍ** | **FOR UPDATE** | products, price_history, audit_log |
| `GET /system-status` | No | — | turns, sales, products |

---

### 1.13 SAT — `modules/sat/routes.py`
**Prefix:** `/api/v1/sat`

| Endpoint | Tablas |
|----------|--------|
| `GET /search` | sat_clave_prod_serv |
| `GET /{code}` | sat_clave_prod_serv |

---

### 1.14 Event Sourcing — `modules/sales/event_sourcing.py`

| Método | SQL | Lock |
|--------|-----|------|
| `append()` | `SELECT COUNT(*) FROM sale_events WHERE sale_id=$1 FOR UPDATE` + INSERT | **FOR UPDATE** + Tx |
| `get_events()` | `SELECT * FROM sale_events WHERE sale_id=:sale_id AND sequence > :after_seq` | — |

---

### 1.15 Saga — `modules/sales/saga.py`

| Step | SQL | Lock | Tabla |
|------|-----|------|-------|
| `_persist_saga` | INSERT saga_instances | — | saga_instances |
| `_persist_step` | INSERT saga_steps ON CONFLICT DO NOTHING | — | saga_steps |
| `_update_saga_state` | UPDATE saga_instances SET state=:state | — | saga_instances |
| `_reserve_source_stock` | `SELECT stock,shadow_stock FROM products WHERE id=:pid FOR UPDATE` + UPDATE shadow_stock | **FOR UPDATE + Tx** | products |
| `_create_transfer_record` | INSERT inventory_movements (OUT, transfer) | — | inventory_movements |
| `_receive_at_destination` | INSERT inventory_movements (IN, transfer) | — | inventory_movements |
| `_confirm_source_deduction` | UPDATE products SET stock=stock-:qty, shadow_stock=shadow_stock-:qty | **Tx** | products |
| Compensaciones | DELETE FROM inventory_movements + UPDATE products SET shadow_stock-=:qty | — | products, inventory_movements |

---

## 2. Módulo Fiscal

### 2.1 CFDIService — `fiscal/cfdi_service.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `_get_fiscal_config` | `SELECT * FROM fiscal_config WHERE branch_id=:bid LIMIT 1` | fiscal_config | No |
| `_get_sale_details` | `SELECT * FROM sales WHERE id=:sid` + `SELECT si.*,p.name,p.sat_* FROM sale_items si LEFT JOIN products p ...` | sales, sale_items, products | No |
| `_save_cfdi` | `INSERT INTO cfdis ({cols}) VALUES ({:cols}) RETURNING id` | cfdis | No |
| `_promote_sale_to_serie_a` | `UPDATE sales SET serie='A',cfdi_uuid=:uuid` + `UPDATE products SET shadow_stock+=:qty` + INSERT shadow_movements | sales, products, shadow_movements | No |
| `cancel_cfdi` | `UPDATE cfdis SET estado='cancelado'` | cfdis | No |
| `cancel_cfdi_via_facturapi` | SELECT cfdis + UPDATE cfdis | cfdis | No |
| `generate_credit_note` | SELECT cfdis + INSERT cfdis + UPDATE fiscal_config | cfdis, fiscal_config | No |

---

### 2.2 GlobalInvoicingService — `fiscal/global_invoicing.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `get_pending_sales_summary` | `SELECT COUNT(*),SUM(subtotal),SUM(tax),SUM(total) FROM sales WHERE serie='B' AND NOT EXISTS (SELECT 1 FROM cfdis WHERE sale_id=s.id)` | sales, cfdis | No |
| `_get_uninvoiced_serie_b_sales` | `SELECT s.* FROM sales s WHERE serie='B' AND CAST(timestamp AS DATE) BETWEEN :d1 AND :d2 AND NOT EXISTS (SELECT 1 FROM cfdis)` | sales, cfdis | No |
| `_aggregate_sales_detailed` | `SELECT p.name,SUM(si.qty),SUM(si.subtotal) FROM sale_items si LEFT JOIN products p ... GROUP BY p.id` | sale_items, products | No |
| `_generate_cfdi_data` | SELECT fiscal_config + INSERT cfdis RETURNING id | fiscal_config, cfdis | No |
| `generate_global_cfdi` | Llama los anteriores + `UPDATE sales SET serie='A'` + INSERT sale_cfdi_relation | sales, cfdis, sale_cfdi_relation | **Tx (promoción B→A)** |
| `generate_global_cfdi_from_selection` | Igual que el anterior pero con sale_ids específicos | sales, cfdis, sale_cfdi_relation | **Tx (promoción B→A)** |

---

### 2.3 MultiEmitterManager — `fiscal/multi_emitter.py`

| Método | SQL | Tabla |
|--------|-----|-------|
| `register_emitter` | INSERT rfc_emitters ON CONFLICT DO UPDATE | rfc_emitters |
| `get_active_emitter` | `SELECT * FROM rfc_emitters WHERE is_active=true AND current_resico_amount < :limit ORDER BY current_resico_amount ASC LIMIT 1` | rfc_emitters |
| `get_accumulated_amount` | `SELECT current_resico_amount FROM rfc_emitters WHERE rfc=:rfc` | rfc_emitters |
| `select_optimal_rfc` | `SELECT * FROM rfc_emitters WHERE is_active=true AND (current_resico_amount+:amt) <= :limit ORDER BY ASC LIMIT 1` | rfc_emitters |
| `list_emitters` | `SELECT * FROM rfc_emitters ORDER BY rfc` | rfc_emitters |
| `update_accumulated_amount` | `UPDATE rfc_emitters SET current_resico_amount+=:amt WHERE rfc=:rfc` | rfc_emitters |

---

### 2.4 CerebroContable — `fiscal/accounting_engine.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_ingresos` | `SELECT SUM(subtotal),SUM(tax),SUM(total),COUNT(*) FROM sales WHERE serie=:serie AND EXTRACT(YEAR FROM timestamp::timestamp)=:year` | sales |
| `_get_serie_b_pendiente` | `SELECT s.*,(SELECT SUM((si.price-p.cost)*si.qty) FROM sale_items si LEFT JOIN products p ...) FROM sales s LEFT JOIN sale_cfdi_relation scr ON s.id=scr.sale_id WHERE s.serie='B' AND scr.id IS NULL ORDER BY fiscal_margin DESC` | sales, sale_items, products, sale_cfdi_relation |

---

### 2.5 ReturnsEngine — `fiscal/returns_engine.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `process_return` | SELECT sales + SELECT sale_items JOIN products + INSERT returns + UPDATE products stock + INSERT inventory_movements | sales, sale_items, products, returns, inventory_movements | **Tx completa** |
| `_generate_return_folio` | `SELECT pg_advisory_xact_lock(738201)` + `SELECT COUNT(*) FROM returns` | returns | **Advisory lock 738201** |
| `get_return_by_folio` | `SELECT * FROM returns WHERE return_folio=:folio` | returns | No |
| `get_pending_cfdi_egresos` | `SELECT * FROM returns WHERE original_serie='A' AND cfdi_egreso_status='pending'` | returns | No |
| `mark_cfdi_egreso_done` | `UPDATE returns SET cfdi_egreso_uuid=:uuid,cfdi_egreso_status='completed'` | returns | No |
| `get_returns_summary` | `SELECT original_serie,COUNT(*),SUM(total) FROM returns ... GROUP BY original_serie` | returns | No |

---

### 2.6 MaterialityEngine — `fiscal/shrinkage_tracker.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `register_loss` | SELECT products **FOR UPDATE** + INSERT loss_records + UPDATE products stock + INSERT inventory_movements | products, loss_records, inventory_movements | **Tx + FOR UPDATE** |
| `_generate_acta_number` | `SELECT pg_advisory_xact_lock(738202)` + SELECT COUNT(*) FROM loss_records | loss_records | **Advisory lock 738202** |
| `authorize_loss` | UPDATE loss_records SET status='authorized' | loss_records | No |
| `generate_acta_text` | SELECT * FROM loss_records | loss_records | No |
| `get_pending_losses` | SELECT * FROM loss_records WHERE status='pending' | loss_records | No |
| `get_loss_summary` | SELECT category,COUNT(*),SUM(quantity),SUM(total_value) FROM loss_records GROUP BY category | loss_records | No |

---

### 2.7 SelfConsumptionEngine — `fiscal/self_consumption.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `register_consumption` | SELECT products **FOR UPDATE** + INSERT self_consumption + UPDATE products stock + INSERT inventory_movements | products, self_consumption, inventory_movements | **Tx + FOR UPDATE** |
| `register_sample` | Llama a register_consumption con category='muestras' | — | — |
| `get_monthly_summary` | SELECT category,COUNT(*),SUM(quantity),SUM(total_value) FROM self_consumption GROUP BY category | self_consumption | No |
| `generate_monthly_voucher` | SELECT + UPDATE self_consumption SET voucher_folio | self_consumption | No |

---

### 2.8 SmartMerge — `fiscal/cost_reconciliation.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `register_purchase` | SELECT products **FOR UPDATE** + INSERT purchase_costs + UPDATE products (cost_a/cost_b, stock) + INSERT inventory_movements + recalculate blended | products, purchase_costs, inventory_movements | **Tx + FOR UPDATE** |
| `_recalculate_blended_cost` | SELECT cost_a,cost_b,qty_from_a,qty_from_b + UPDATE products SET cost | products | No |
| `get_dual_cost_view` | SELECT name,sku,stock,cost,cost_a,cost_b,qty_from_a,qty_from_b,price FROM products | products | No |
| `calculate_fiscal_vs_real_profit` | SELECT si.*,p.cost,p.cost_a FROM sale_items si JOIN products p | sale_items, products | No |
| `get_global_cost_report` | SELECT * FROM products WHERE qty_from_a > 0 OR qty_from_b > 0 | products | No |

---

### 2.9 ShadowInventory — `fiscal/dual_inventory.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `get_dual_stock` | SELECT id,name,stock,shadow_stock,min_stock FROM products | products | No |
| `add_shadow_stock` | SELECT products **FOR UPDATE** + UPDATE products (stock + shadow_stock) + INSERT inventory_movements + INSERT shadow_movements | products, inventory_movements, shadow_movements | **Tx + FOR UPDATE** |
| `sell_with_attribution` | SELECT products **FOR UPDATE** + UPDATE products stock/shadow + INSERT inventory_movements + INSERT shadow_movements | products, inventory_movements, shadow_movements | **Tx + FOR UPDATE** |
| `get_audit_view` | SELECT id,sku,name,(stock-shadow_stock) as stock_auditable FROM products | products | No |
| `get_real_view` | SELECT id,sku,name,stock,shadow_stock FROM products | products | No |
| `reconcile_fiscal` | SELECT stock,shadow_stock FROM products **FOR UPDATE** + UPDATE products SET shadow_stock | products | **Tx + FOR UPDATE** |
| `get_discrepancy_report` | SELECT * FROM products WHERE shadow_stock > 0 | products | No |

---

### 2.10 GhostWallet — `fiscal/reserve_wallet.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `generate_hash_id` | INSERT ghost_wallets ON CONFLICT DO NOTHING | ghost_wallets | No |
| `add_points` | SELECT balance FROM ghost_wallets **FOR UPDATE** + UPDATE ghost_wallets + INSERT ghost_transactions | ghost_wallets, ghost_transactions | **Tx + FOR UPDATE** |
| `redeem_points` | SELECT balance FROM ghost_wallets **FOR UPDATE** + UPDATE ghost_wallets + INSERT ghost_transactions | ghost_wallets, ghost_transactions | **Tx + FOR UPDATE** |
| `get_wallet_stats` | SELECT COUNT(*),SUM(balance),SUM(total_earned),SUM(total_spent) FROM ghost_wallets | ghost_wallets | No |

---

### 2.11 GhostCarrier — `fiscal/internal_transfer.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `create_transfer` | INSERT ghost_transfers + (por item: SELECT products **FOR UPDATE** + UPDATE stock + INSERT inventory_movements) | ghost_transfers, products, inventory_movements | **Tx + FOR UPDATE por producto** |
| `receive_transfer` | SELECT ghost_transfers **FOR UPDATE** + (por item: SELECT products + UPDATE stock + INSERT inventory_movements) + UPDATE ghost_transfers status | ghost_transfers, products, inventory_movements | **Tx + FOR UPDATE** |
| `generate_warehouse_slip` | SELECT * FROM ghost_transfers | ghost_transfers | No |
| `get_pending_transfers` | SELECT * FROM ghost_transfers WHERE status='pending' | ghost_transfers | No |

---

### 2.12 CrossBranchBilling — `fiscal/intercompany_billing.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `select_optimal_rfc_with_facade` | Delega a MultiEmitterManager.select_optimal_rfc | rfc_emitters (vía multi_emitter) | No |
| `process_cross_invoice` | SELECT sales + INSERT cross_invoices + UPDATE sales SET rfc_used,is_cross_billed | sales, cross_invoices | **Tx** |

---

### 2.13 FiscalNoiseGenerator — `fiscal/transaction_normalizer.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `calculate_optimal_noise` | `SELECT COUNT(*),SUM(total) FROM sales WHERE serie='A' AND is_noise=false` | sales | No |
| `_get_historical_hourly_weights` | `SELECT EXTRACT(HOUR FROM timestamp) as hr,COUNT(*) FROM sales WHERE is_noise=false GROUP BY hr` | sales | No |
| `generate_noise_transaction` | `SELECT id,name,price,barcode FROM products WHERE stock>10 AND price BETWEEN 10 AND 500 ORDER BY RANDOM() LIMIT 5` | products | No |
| `_execute_noise_transaction` | INSERT sales (is_noise=true) + INSERT sale_items | sales, sale_items | No |

---

### 2.14 FederationDashboard — `fiscal/enterprise_dashboard.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `get_operational_dashboard` | SELECT branches + (por branch: SELECT sales WHERE branch_id=:bid + SELECT turns WHERE branch_id=:bid + SELECT products WHERE branch_id=:bid) | branches, sales, turns, products |
| `get_fiscal_intelligence` | SELECT rfc_emitters + (por emitter: SELECT SUM(s.total) FROM sales s JOIN cfdis c ON s.id=c.sale_id WHERE c.emitter_rfc=:rfc) | rfc_emitters, sales, cfdis |
| `get_wealth_dashboard` | SELECT SUM(total) FROM sales WHERE serie='B' + serie='A' + SELECT SUM(amount) FROM cash_extractions + SELECT related_persons | sales, cash_extractions, related_persons |
| `remote_lockdown` | UPDATE branches SET lockdown_active=true | branches |
| `release_lockdown` | UPDATE branches SET lockdown_active=false | branches |

---

### 2.15 NostradamusFiscal — `fiscal/fiscal_forecast.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_ab_balance` | `SELECT SUM(total),COUNT(*) FROM sales WHERE serie=:s AND timestamp>=:ms AND status='completed'` (A y B) | sales |
| `_get_deduction_status` | `SELECT SUM(amount) FROM cash_movements WHERE type='expense'` + `SELECT SUM(total_cost) FROM purchase_costs WHERE serie='A'` + `SELECT SUM(total_value) FROM loss_records WHERE status='authorized'` + `SELECT SUM(total) FROM sales WHERE serie='A'` | cash_movements, purchase_costs, loss_records, sales |
| `_get_resico_status` | Delega a MultiEmitterManager.list_emitters | rfc_emitters (vía multi_emitter) |

---

### 2.16 GeneralDeGuerra — `fiscal/internal_audit.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_analyze_materiality` | `SELECT COUNT(*) FROM loss_records WHERE photo_path IS NULL AND created_at::timestamp >= CURRENT_DATE - 7 days` | loss_records |
| `_analyze_fiscal` | Delega a MultiEmitterManager.list_emitters | rfc_emitters |
| `_analyze_inventory` | `SELECT p.id,p.name,p.stock, (subquery SUM sale_items), (subquery SUM loss_records) FROM products p` | products, sale_items, sales, loss_records |
| `_analyze_cash_extraction` | `SELECT SUM(amount),COUNT(*) FROM cash_movements WHERE type='out' AND timestamp >= DATE_TRUNC('month',CURRENT_DATE)` | cash_movements |

---

### 2.17 StealthLayer — `fiscal/data_privacy_layer.py`

| Método | SQL | Tablas | Tx |
|--------|-----|--------|-----|
| `configure_pins` | INSERT config ON CONFLICT DO UPDATE (3x) | config | No |
| `verify_pin` | SELECT value FROM config WHERE key='normal_pin_hash' (3 queries) | config | No (timing-safe compare_digest) |
| `_trigger_silent_alert` | INSERT config ON CONFLICT DO UPDATE | config | No |
| `surgical_delete` | (validación: SELECT serie FROM sales por cada id) + SELECT sale_items + UPDATE products stock + INSERT inventory_movements + DELETE sale_items + DELETE payments + DELETE sales WHERE serie='B' | sales, sale_items, products, payments, inventory_movements | **Tx (valida todo B antes de borrar)** |

---

### 2.18 FiscalDashboard — `fiscal/fiscal_dashboard.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_serie_stats` | `SELECT COUNT(*),SUM(total),SUM(subtotal),SUM(tax) FROM sales WHERE serie=:serie AND EXTRACT(YEAR FROM timestamp::timestamp)=:year` | sales |
| `_get_pendientes_global` | `SELECT COUNT(*),SUM(total),MIN(timestamp) FROM sales s LEFT JOIN sale_cfdi_relation scr ON s.id=scr.sale_id WHERE s.serie='B' AND scr.id IS NULL` | sales, sale_cfdi_relation |
| `get_smart_global_selection` | `SELECT s.*,STRING_AGG(p.name,', ') FROM sales s LEFT JOIN sale_cfdi_relation scr ... LEFT JOIN sale_items si ... LEFT JOIN products p ... WHERE serie='B' AND scr.id IS NULL GROUP BY s.id` | sales, sale_items, products, sale_cfdi_relation |

---

### 2.19 CashExtractionEngine — `fiscal/cash_flow_manager.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `add_related_person` | INSERT related_persons | related_persons |
| `get_serie_b_balance` | SELECT SUM(total) FROM sales WHERE serie='B' + SELECT SUM(amount) FROM cash_extractions | sales, cash_extractions |
| `create_extraction` | SELECT related_persons + INSERT cash_extractions | related_persons, cash_extractions |
| `generate_contract_text` | SELECT e.*,p.name,p.rfc FROM cash_extractions e LEFT JOIN related_persons p | cash_extractions, related_persons |
| `get_annual_summary` | SELECT document_type,COUNT(*),SUM(amount) FROM cash_extractions GROUP BY document_type | cash_extractions |

---

### 2.20 PaymentReceiptService — `fiscal/payment_complement.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `generate_payment_receipt` | SELECT cfdis (validar) + SELECT cfdis (DoctoRelacionado) + INSERT cfdis + INSERT cfdi_relations | cfdis, cfdi_relations |

---

### 2.21 XMLIngestor — `fiscal/xml_ingestor.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_find_existing_product` | `SELECT * FROM products WHERE barcode=:code OR sku=:code` + fallback ILIKE | products |
| `_create_product` | INSERT products | products |
| `_update_product` | UPDATE products SET stock+=:qty,cost_price=:cost + INSERT inventory_movements | products, inventory_movements |

---

### 2.22 RESICOMonitor — `fiscal/resico_monitor.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_ventas_serie_a` | `SELECT SUM(subtotal) FROM sales WHERE serie='A' AND EXTRACT(YEAR FROM timestamp::timestamp)=:yr AND status='completed'` | sales |
| `get_monthly_breakdown` | `SELECT EXTRACT(MONTH),COUNT(*),SUM(subtotal),SUM(tax),SUM(total) FROM sales WHERE serie='A' GROUP BY month ORDER BY mes` | sales |

---

### 2.23 PredictiveExtraction — `fiscal/smart_withdrawal.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `analyze_available` | SELECT SUM(total) FROM sales WHERE serie='B' + SELECT SUM(amount) FROM cash_expenses + SELECT SUM(amount) FROM cash_extractions | sales, cash_expenses, cash_extractions |
| `_get_related_persons` | SELECT name,parentesco FROM related_persons WHERE is_active=1 | related_persons |
| `get_optimal_daily_amount` | SELECT SUBSTRING(timestamp,1,10) as day,SUM(total) FROM sales WHERE serie='B' GROUP BY day | sales |

---

### 2.24 SupplierMatcher — `fiscal/supplier_matcher.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_cash_flow_status` | SELECT SUM(total) FROM sales WHERE serie='B' AND payment_method IN ('cash') + SELECT SUM(amount) FROM cash_expenses + SELECT SUM(total) FROM sales WHERE serie='A' | sales, cash_expenses |
| `_get_product` | SELECT * FROM products WHERE id=:pid | products |

---

### 2.25 CryptoBridge — `fiscal/liquidity_bridge.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `get_available_for_conversion` | SELECT SUM(total) FROM sales WHERE serie='B' + SELECT SUM(amount_mxn) FROM crypto_conversions + SELECT SUM(amount) FROM cash_expenses | sales, crypto_conversions, cash_expenses |
| `_get_remaining_daily_limit` | SELECT SUM(amount_mxn) FROM crypto_conversions WHERE created_at::date=:today | crypto_conversions |
| `create_conversion` | INSERT crypto_conversions + INSERT cash_expenses | crypto_conversions, cash_expenses |
| `get_crypto_wealth` | SELECT * FROM cold_wallets + SELECT stablecoin,SUM(amount_usd) FROM crypto_conversions GROUP BY stablecoin | cold_wallets, crypto_conversions |

---

### 2.26 DiscrepancyMonitor — `fiscal/reconciliation_monitor.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `register_expense` | INSERT personal_expenses | personal_expenses |
| `get_discrepancy_analysis` | SELECT SUM(total) FROM sales WHERE serie='A' + SELECT SUM(amount) FROM personal_expenses + SELECT SUM(amount) FROM cash_extractions | sales, personal_expenses, cash_extractions |
| `get_expense_breakdown` | SELECT category,payment_method,SUM(amount) FROM personal_expenses GROUP BY category,payment_method | personal_expenses |

---

### 2.27 WealthDashboard — `fiscal/wealth_dashboard.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_total_income` | SELECT serie,SUM(total),COUNT(*) FROM sales ... GROUP BY serie | sales |
| `_get_operating_expenses` | SELECT SUM(total) FROM sales (para estimar costos) | sales |
| `_get_extractions` | SELECT SUM(amount),COUNT(*) FROM cash_extractions | cash_extractions |

---

### 2.28 ClimateShield — `fiscal/risk_mitigation.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `attach_to_merma` | SELECT lr.*,p.name FROM loss_records lr JOIN products p + UPDATE loss_records SET climate_justification | loss_records, products |

---

### 2.29 LegalDocumentGenerator — `fiscal/legal_documents.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `_get_app_config` | SELECT * FROM app_config LIMIT 1 | app_config |
| `_get_fiscal_config` | SELECT * FROM fiscal_config WHERE branch_id=:bid LIMIT 1 | fiscal_config |

---

### 2.30 CFDISyncService — `fiscal/cfdi_sync_service.py`

| Método | SQL | Tablas |
|--------|-----|--------|
| `sync_cfdis` | SELECT * FROM cfdis WHERE sync_status != 1 | cfdis |
| `update_sync_status` | UPDATE cfdis SET sync_status=1 WHERE id=:id | cfdis |

---

## 3. Referencia de Tablas

### Tablas Core (usadas por múltiples módulos)

| Tabla | Módulos que la Tocan | Tipo Timestamp |
|-------|---------------------|----------------|
| `sales` | sales, dashboard, sync, remote, fiscal (15+ clases) | **TEXT** (ISO string) |
| `sale_items` | sales, dashboard, fiscal (accounting, global_invoicing) | — |
| `products` | sales, products, inventory, sync, mermas, fiscal (10+ clases) | — |
| `customers` | sales, customers, sync | — |
| `turns` | sales, turns, expenses, sync, remote | — |
| `cash_movements` | turns, expenses, dashboard, fiscal (forecast, audit) | **TIMESTAMP WITHOUT TZ** |
| `inventory_movements` | sales, products, inventory, mermas, saga, fiscal (6+ clases) | — |
| `users` | auth | — |
| `employees` | turns (PIN check), employees | — |

### Tablas Fiscal

| Tabla | Clase Principal | CREATE en |
|-------|----------------|-----------|
| `cfdis` | CFDIService, GlobalInvoicingService, PaymentReceiptService | migración |
| `sale_cfdi_relation` | GlobalInvoicingService | migración |
| `cfdi_relations` | PaymentReceiptService | migración |
| `rfc_emitters` | MultiEmitterManager | migración |
| `fiscal_config` | CFDIService, LegalDocumentGenerator | migración |
| `loss_records` | MaterialityEngine | setup_table() |
| `self_consumption` | SelfConsumptionEngine | setup_table() |
| `purchase_costs` | SmartMerge | ensure_schema() |
| `shadow_movements` | ShadowInventory | ensure_schema() |
| `ghost_wallets` | GhostWallet | _ensure_tables() |
| `ghost_transactions` | GhostWallet | _ensure_tables() |
| `ghost_transfers` | GhostCarrier | ensure_table() |
| `cross_invoices` | CrossBranchBilling | _ensure_tables() |
| `returns` | ReturnsEngine | ensure_tables() |
| `related_persons` | CashExtractionEngine | setup_tables() |
| `cash_extractions` | CashExtractionEngine | setup_tables() |
| `personal_expenses` | DiscrepancyMonitor | setup_table() |
| `crypto_conversions` | CryptoBridge | _ensure_table() |
| `cold_wallets` | CryptoBridge | _ensure_table() |
| `cash_expenses` | CryptoBridge | _ensure_table() |

### Tablas Auxiliares

| Tabla | Módulo |
|-------|--------|
| `secuencias` | sales (folio generation) |
| `kit_components` | sales (kit explosion) |
| `credit_history` | sales (credit payments) |
| `price_history` | products, remote |
| `branches` | enterprise_dashboard, main |
| `sat_clave_prod_serv` | sat |
| `app_config` | remote, legal_documents |
| `audit_log` | remote |
| `remote_notifications` | remote |
| `config` | data_privacy_layer (PINs) |
| `sale_events` | event_sourcing |
| `saga_instances` | saga |
| `saga_steps` | saga |

### Vistas Materializadas (CQRS)

| Vista | Usado por |
|-------|-----------|
| `mv_daily_sales_summary` | sales reports |
| `mv_product_sales_ranking` | sales reports |
| `mv_hourly_sales_heatmap` | sales reports |

---

## 4. Seguridad de Transacciones

### Patrón: FOR UPDATE + Transaction

```python
conn = self.db.connection
async with conn.transaction():
    row = await self.db.fetchrow("SELECT ... FOR UPDATE", ...)
    # validar
    await self.db.execute("UPDATE ...", ...)
```

### Operaciones con FOR UPDATE

| Operación | Lock | Advisory Lock |
|-----------|------|---------------|
| create_sale (products) | **FOR UPDATE NOWAIT** | — |
| create_sale (turns) | **FOR UPDATE** | — |
| create_sale (customers credit/wallet) | **FOR UPDATE** | — |
| cancel_sale (sale + products + customers) | **FOR UPDATE** | — |
| register_loss | **FOR UPDATE** (products) | **738202** (acta_number) |
| process_return | — | **738201** (folio DEV-) |
| register_consumption | **FOR UPDATE** (products) | — |
| register_purchase | **FOR UPDATE** (products) | — |
| add_shadow_stock | **FOR UPDATE** (products) | — |
| sell_with_attribution | **FOR UPDATE** (products) | — |
| reconcile_fiscal | **FOR UPDATE** (products) | — |
| add_points | **FOR UPDATE** (ghost_wallets) | — |
| redeem_points | **FOR UPDATE** (ghost_wallets) | — |
| create_transfer | **FOR UPDATE** (products por item) | — |
| receive_transfer | **FOR UPDATE** (ghost_transfers) | — |
| adjust_stock | **FOR UPDATE** (products) | — |
| open_turn | **FOR UPDATE** (turns) | — |
| close_turn | **FOR UPDATE** (turns) | — |
| create_cash_movement | **FOR UPDATE** (turns) | — |
| approve_merma | **FOR UPDATE** (loss_records + products) | — |
| pending_notifications | **FOR UPDATE** (remote_notifications) | — |
| change_price | **FOR UPDATE** (products) | — |
| sync_push (customers) | **FOR UPDATE** (customers) | — |
| update/delete product | **FOR UPDATE** (products) | — |
| update/delete customer | **FOR UPDATE** (customers) | — |
| update/delete employee | **FOR UPDATE** (employees) | — |
| event_sourcing.append | **FOR UPDATE** (sale_events count) | — |
| saga._reserve_source_stock | **FOR UPDATE** (products) | — |

### Tipo de Datos Clave

| Columna | Tipo Real | Pasar como |
|---------|-----------|------------|
| `sales.timestamp` | **TEXT** | `str` (ISO format) |
| `cash_movements.timestamp` | **TIMESTAMP WITHOUT TZ** | `datetime` (naive, sin tzinfo) |
| `loss_records.created_at` | **TEXT** | `str` |
| `purchase_costs.purchase_date` | **TEXT** | `str` |
| `self_consumption.created_at` | **TEXT** | `str` |
| `ghost_transfers.created_at` | **TIMESTAMP** | `datetime` o auto (DEFAULT NOW()) |
| `returns.created_at` | **TIMESTAMP** | auto (DEFAULT NOW()) |

---

*Documento generado automáticamente durante auditoría de TITAN POS — Feb 2026*
