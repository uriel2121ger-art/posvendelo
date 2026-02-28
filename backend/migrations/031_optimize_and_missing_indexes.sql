-- Migration 031: Optimize redundant indexes + add missing FK/query indexes
-- Audit date: 2026-02-27

BEGIN;

-- ============================================================
-- 1. DROP REDUNDANT INDEXES (same column, different names)
-- ============================================================

-- sales(turn_id): idx_sales_turn (schema) vs idx_sales_turn_id (mig 006)
DROP INDEX IF EXISTS idx_sales_turn_id;

-- sale_items(sale_id): idx_sale_items_sale (schema) vs idx_sale_items_sale_id (mig 006)
DROP INDEX IF EXISTS idx_sale_items_sale_id;

-- sale_items(product_id): idx_sale_items_product (schema) vs idx_sale_items_product_id (mig 006)
DROP INDEX IF EXISTS idx_sale_items_product_id;

-- cash_movements(turn_id): idx_cash_movements_turn (schema) vs idx_cash_movements_turn_id (mig 020)
DROP INDEX IF EXISTS idx_cash_movements_turn_id;

-- products(category_id): column no longer used in queries; idx_products_category_text (mig 020) covers category TEXT
DROP INDEX IF EXISTS idx_products_category;

-- ============================================================
-- 2. HIGH PRIORITY — queries frecuentes sin soporte de indice
-- ============================================================

-- kit_components: consultado en cada venta con kits (sales/routes.py)
CREATE INDEX IF NOT EXISTS idx_kit_components_kit_id ON kit_components(kit_product_id);
CREATE INDEX IF NOT EXISTS idx_kit_components_component_id ON kit_components(component_product_id);

-- returns: busqueda por folio, por venta, y por fecha
CREATE INDEX IF NOT EXISTS idx_returns_sale_id ON returns(sale_id);
CREATE INDEX IF NOT EXISTS idx_returns_folio ON returns(return_folio) WHERE return_folio IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_returns_created_at ON returns(created_at);

-- payments: DELETE/SELECT WHERE sale_id (data_privacy_layer, fiscal)
CREATE INDEX IF NOT EXISTS idx_payments_sale_id ON payments(sale_id);

-- fiscal_config: lookup por branch_id en cada operacion de facturacion
CREATE INDEX IF NOT EXISTS idx_fiscal_config_branch ON fiscal_config(branch_id);

-- ============================================================
-- 3. MEDIUM PRIORITY — FK indexes en tablas hijo
-- ============================================================

-- return_items
CREATE INDEX IF NOT EXISTS idx_return_items_return_id ON return_items(return_id);
CREATE INDEX IF NOT EXISTS idx_return_items_product_id ON return_items(product_id);

-- layaway_items / layaway_payments
CREATE INDEX IF NOT EXISTS idx_layaway_items_layaway_id ON layaway_items(layaway_id);
CREATE INDEX IF NOT EXISTS idx_layaway_payments_layaway_id ON layaway_payments(layaway_id);

-- transfer_items
CREATE INDEX IF NOT EXISTS idx_transfer_items_transfer_id ON transfer_items(transfer_id);

-- turn_movements
CREATE INDEX IF NOT EXISTS idx_turn_movements_turn_id ON turn_movements(turn_id);

-- card_transactions
CREATE INDEX IF NOT EXISTS idx_card_transactions_card_id ON card_transactions(gift_card_id);
CREATE INDEX IF NOT EXISTS idx_card_transactions_sale_id ON card_transactions(sale_id) WHERE sale_id IS NOT NULL;

-- sale_cfdi_relation
CREATE INDEX IF NOT EXISTS idx_sale_cfdi_sale_id ON sale_cfdi_relation(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_cfdi_cfdi_id ON sale_cfdi_relation(cfdi_id);

-- cfdi_relations
CREATE INDEX IF NOT EXISTS idx_cfdi_relations_parent ON cfdi_relations(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_cfdi_relations_related ON cfdi_relations(related_uuid);

-- shipping_addresses
CREATE INDEX IF NOT EXISTS idx_shipping_addresses_customer ON shipping_addresses(customer_id);

-- loyalty_transactions
CREATE INDEX IF NOT EXISTS idx_loyalty_tx_account_id ON loyalty_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_tx_sale_id ON loyalty_transactions(sale_id) WHERE sale_id IS NOT NULL;

-- loyalty_fraud_log
CREATE INDEX IF NOT EXISTS idx_loyalty_fraud_account ON loyalty_fraud_log(account_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_fraud_customer ON loyalty_fraud_log(customer_id);

-- loyalty_tier_history
CREATE INDEX IF NOT EXISTS idx_loyalty_tier_customer ON loyalty_tier_history(customer_id);

-- sale_voids
CREATE INDEX IF NOT EXISTS idx_sale_voids_sale_id ON sale_voids(sale_id);

-- loan_payments
CREATE INDEX IF NOT EXISTS idx_loan_payments_loan_id ON loan_payments(loan_id);

-- attendance / attendance_summary
CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_summary_employee ON attendance_summary(employee_id);

-- breaks
CREATE INDEX IF NOT EXISTS idx_breaks_entry_id ON breaks(entry_id);

-- purchase_order_items / order_items / cart_items
CREATE INDEX IF NOT EXISTS idx_po_items_order_id ON purchase_order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id ON cart_items(cart_id);

-- sync_conflicts
CREATE INDEX IF NOT EXISTS idx_sync_conflicts_table_record ON sync_conflicts(table_name, record_id);

-- ============================================================
-- 4. LOWER PRIORITY — columnas filtradas en reportes fiscales
-- ============================================================

-- personal_expenses: reportes por fecha y categoria
CREATE INDEX IF NOT EXISTS idx_personal_expenses_date ON personal_expenses(expense_date);

-- purchase_costs: forecast fiscal por producto y fecha
CREATE INDEX IF NOT EXISTS idx_purchase_costs_product ON purchase_costs(product_id);
CREATE INDEX IF NOT EXISTS idx_purchase_costs_date ON purchase_costs(purchase_date);

-- shadow_movements: inventario dual fiscal
CREATE INDEX IF NOT EXISTS idx_shadow_movements_product ON shadow_movements(product_id);

-- self_consumption: reportes por producto y fecha
CREATE INDEX IF NOT EXISTS idx_self_consumption_product ON self_consumption(product_id);
CREATE INDEX IF NOT EXISTS idx_self_consumption_date ON self_consumption(consumed_date);

-- related_persons: filtrado por is_active
CREATE INDEX IF NOT EXISTS idx_related_persons_active ON related_persons(is_active) WHERE is_active = 1;

-- ============================================================

INSERT INTO schema_version (version, description, applied_at)
VALUES (31, 'Optimize redundant indexes + add missing FK/query indexes', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
