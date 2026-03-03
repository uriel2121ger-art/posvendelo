-- 040_numeric_secondary.sql
-- Convierte columnas FLOAT/DOUBLE PRECISION a NUMERIC en tablas secundarias
-- Tablas excluidas: ghost_*, shadow_*, anonymous_*, crypto_* (módulo fiscal)
-- Idempotente: el helper verifica data_type antes de alterar

BEGIN;

-- Helper para conversión idempotente
CREATE OR REPLACE FUNCTION _migrate_to_numeric(
    p_table TEXT, p_column TEXT, p_precision INT, p_scale INT
) RETURNS void AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = p_table AND column_name = p_column
          AND data_type = 'double precision'
    ) THEN
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE NUMERIC(%s,%s) USING %I::numeric(%s,%s)',
            p_table, p_column, p_precision, p_scale, p_column, p_precision, p_scale
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- employees
-- =====================================================================
SELECT _migrate_to_numeric('employees', 'base_salary',          12, 2);
SELECT _migrate_to_numeric('employees', 'commission_rate',       5, 4);
SELECT _migrate_to_numeric('employees', 'current_loan_balance', 12, 2);
SELECT _migrate_to_numeric('employees', 'loan_limit',           12, 2);

-- =====================================================================
-- employee_loans
-- =====================================================================
SELECT _migrate_to_numeric('employee_loans', 'amount',        12, 2);
SELECT _migrate_to_numeric('employee_loans', 'balance',       12, 2);
SELECT _migrate_to_numeric('employee_loans', 'interest_rate',  5, 4);

-- =====================================================================
-- loan_payments
-- =====================================================================
SELECT _migrate_to_numeric('loan_payments', 'amount',        12, 2);
SELECT _migrate_to_numeric('loan_payments', 'balance_after', 12, 2);

-- =====================================================================
-- returns
-- =====================================================================
SELECT _migrate_to_numeric('returns', 'quantity',   12, 4);
SELECT _migrate_to_numeric('returns', 'unit_price', 12, 2);
SELECT _migrate_to_numeric('returns', 'subtotal',   12, 2);
SELECT _migrate_to_numeric('returns', 'tax',        12, 2);
SELECT _migrate_to_numeric('returns', 'total',      12, 2);

-- =====================================================================
-- return_items
-- =====================================================================
SELECT _migrate_to_numeric('return_items', 'quantity',   12, 4);
SELECT _migrate_to_numeric('return_items', 'unit_price', 12, 2);

-- =====================================================================
-- invoices
-- =====================================================================
SELECT _migrate_to_numeric('invoices', 'subtotal', 12, 2);
SELECT _migrate_to_numeric('invoices', 'tax',      12, 2);
SELECT _migrate_to_numeric('invoices', 'total',    12, 2);

-- =====================================================================
-- cfdis
-- =====================================================================
SELECT _migrate_to_numeric('cfdis', 'subtotal',   12, 2);
SELECT _migrate_to_numeric('cfdis', 'impuestos',  12, 2);
SELECT _migrate_to_numeric('cfdis', 'total',      12, 2);

-- =====================================================================
-- layaways
-- =====================================================================
SELECT _migrate_to_numeric('layaways', 'total_amount', 12, 2);
SELECT _migrate_to_numeric('layaways', 'amount_paid',  12, 2);
SELECT _migrate_to_numeric('layaways', 'balance_due',  12, 2);

-- =====================================================================
-- layaway_items
-- =====================================================================
SELECT _migrate_to_numeric('layaway_items', 'price', 12, 2);
SELECT _migrate_to_numeric('layaway_items', 'qty',   12, 4);
SELECT _migrate_to_numeric('layaway_items', 'total', 12, 2);

-- =====================================================================
-- layaway_payments
-- =====================================================================
SELECT _migrate_to_numeric('layaway_payments', 'amount', 12, 2);

-- =====================================================================
-- purchases
-- =====================================================================
SELECT _migrate_to_numeric('purchases', 'subtotal', 12, 2);
SELECT _migrate_to_numeric('purchases', 'tax',      12, 2);
SELECT _migrate_to_numeric('purchases', 'total',    12, 2);

-- =====================================================================
-- purchase_orders
-- =====================================================================
SELECT _migrate_to_numeric('purchase_orders', 'subtotal', 12, 2);
SELECT _migrate_to_numeric('purchase_orders', 'tax',      12, 2);
SELECT _migrate_to_numeric('purchase_orders', 'total',    12, 2);

-- =====================================================================
-- purchase_order_items
-- =====================================================================
SELECT _migrate_to_numeric('purchase_order_items', 'quantity',     12, 4);
SELECT _migrate_to_numeric('purchase_order_items', 'received_qty', 12, 4);
SELECT _migrate_to_numeric('purchase_order_items', 'unit_cost',    12, 2);

-- =====================================================================
-- purchase_costs
-- =====================================================================
SELECT _migrate_to_numeric('purchase_costs', 'unit_cost', 12, 2);

-- =====================================================================
-- price_change_history
-- =====================================================================
SELECT _migrate_to_numeric('price_change_history', 'old_price',        12, 2);
SELECT _migrate_to_numeric('price_change_history', 'new_price',        12, 2);
SELECT _migrate_to_numeric('price_change_history', 'old_cost',         12, 2);
SELECT _migrate_to_numeric('price_change_history', 'new_cost',         12, 2);
SELECT _migrate_to_numeric('price_change_history', 'margin_pct',        5, 4);
SELECT _migrate_to_numeric('price_change_history', 'cost_change_pct',   5, 4);

-- =====================================================================
-- inventory_log
-- =====================================================================
SELECT _migrate_to_numeric('inventory_log', 'qty_change', 12, 4);
SELECT _migrate_to_numeric('inventory_log', 'quantity',   12, 4);

-- =====================================================================
-- inventory_movements
-- =====================================================================
SELECT _migrate_to_numeric('inventory_movements', 'quantity', 12, 4);

-- =====================================================================
-- inventory_transfers
-- =====================================================================
SELECT _migrate_to_numeric('inventory_transfers', 'total_qty',   12, 4);
SELECT _migrate_to_numeric('inventory_transfers', 'total_value', 12, 2);

-- =====================================================================
-- transfer_items
-- =====================================================================
SELECT _migrate_to_numeric('transfer_items', 'qty_sent',     12, 4);
SELECT _migrate_to_numeric('transfer_items', 'qty_received', 12, 4);
SELECT _migrate_to_numeric('transfer_items', 'unit_cost',    12, 2);

-- =====================================================================
-- loss_records
-- =====================================================================
SELECT _migrate_to_numeric('loss_records', 'quantity',    12, 4);
SELECT _migrate_to_numeric('loss_records', 'unit_cost',   12, 2);
SELECT _migrate_to_numeric('loss_records', 'total_value', 12, 2);

-- =====================================================================
-- kit_components
-- =====================================================================
SELECT _migrate_to_numeric('kit_components', 'quantity', 12, 4);

-- =====================================================================
-- kit_items
-- =====================================================================
SELECT _migrate_to_numeric('kit_items', 'qty', 12, 4);

-- =====================================================================
-- online_orders
-- =====================================================================
SELECT _migrate_to_numeric('online_orders', 'subtotal', 12, 2);
SELECT _migrate_to_numeric('online_orders', 'tax',      12, 2);
SELECT _migrate_to_numeric('online_orders', 'total',    12, 2);
SELECT _migrate_to_numeric('online_orders', 'shipping', 12, 2);

-- =====================================================================
-- order_items
-- =====================================================================
SELECT _migrate_to_numeric('order_items', 'quantity',   12, 4);
SELECT _migrate_to_numeric('order_items', 'unit_price', 12, 2);
SELECT _migrate_to_numeric('order_items', 'total',      12, 2);

-- =====================================================================
-- payments
-- =====================================================================
SELECT _migrate_to_numeric('payments', 'amount', 12, 2);

-- =====================================================================
-- gift_cards
-- =====================================================================
SELECT _migrate_to_numeric('gift_cards', 'initial_balance', 12, 2);
SELECT _migrate_to_numeric('gift_cards', 'balance',         12, 2);

-- =====================================================================
-- wallet_transactions
-- =====================================================================
SELECT _migrate_to_numeric('wallet_transactions', 'amount', 12, 2);

-- =====================================================================
-- card_transactions
-- =====================================================================
SELECT _migrate_to_numeric('card_transactions', 'amount',       12, 2);
SELECT _migrate_to_numeric('card_transactions', 'balance_after', 12, 2);

-- =====================================================================
-- promotions
-- =====================================================================
SELECT _migrate_to_numeric('promotions', 'value',        12, 2);
SELECT _migrate_to_numeric('promotions', 'min_purchase', 12, 2);
SELECT _migrate_to_numeric('promotions', 'max_discount', 12, 2);

-- =====================================================================
-- loyalty_accounts
-- =====================================================================
SELECT _migrate_to_numeric('loyalty_accounts', 'saldo_actual',    12, 2);
SELECT _migrate_to_numeric('loyalty_accounts', 'saldo_pendiente', 12, 2);
SELECT _migrate_to_numeric('loyalty_accounts', 'total_spent',     12, 2);

-- =====================================================================
-- loyalty_ledger
-- =====================================================================
SELECT _migrate_to_numeric('loyalty_ledger', 'monto',              12, 2);
SELECT _migrate_to_numeric('loyalty_ledger', 'porcentaje_cashback', 5, 4);
SELECT _migrate_to_numeric('loyalty_ledger', 'saldo_anterior',     12, 2);
SELECT _migrate_to_numeric('loyalty_ledger', 'saldo_nuevo',        12, 2);

-- =====================================================================
-- loyalty_rules
-- =====================================================================
SELECT _migrate_to_numeric('loyalty_rules', 'monto_minimo',         12, 2);
SELECT _migrate_to_numeric('loyalty_rules', 'monto_maximo_puntos',  12, 2);
SELECT _migrate_to_numeric('loyalty_rules', 'multiplicador',         8, 4);

-- =====================================================================
-- loyalty_fraud_log
-- =====================================================================
SELECT _migrate_to_numeric('loyalty_fraud_log', 'monto_involucrado', 12, 2);

-- =====================================================================
-- self_consumption
-- =====================================================================
SELECT _migrate_to_numeric('self_consumption', 'quantity',  12, 4);
SELECT _migrate_to_numeric('self_consumption', 'unit_cost', 12, 2);

-- =====================================================================
-- personal_expenses
-- =====================================================================
SELECT _migrate_to_numeric('personal_expenses', 'amount', 12, 2);

-- =====================================================================
-- product_lots
-- =====================================================================
SELECT _migrate_to_numeric('product_lots', 'stock', 12, 4);

-- =====================================================================
-- bin_locations
-- =====================================================================
SELECT _migrate_to_numeric('bin_locations', 'quantity', 12, 4);

-- =====================================================================
-- branch_inventory
-- =====================================================================
SELECT _migrate_to_numeric('branch_inventory', 'stock',     12, 4);
SELECT _migrate_to_numeric('branch_inventory', 'min_stock', 12, 4);
SELECT _migrate_to_numeric('branch_inventory', 'max_stock', 12, 4);

-- =====================================================================
-- attendance_summary
-- =====================================================================
SELECT _migrate_to_numeric('attendance_summary', 'hours_worked', 6, 2);

-- =====================================================================
-- attendance_rules
-- =====================================================================
SELECT _migrate_to_numeric('attendance_rules', 'overtime_after_hours', 4, 2);

-- =====================================================================
-- analytics_conversions
-- =====================================================================
SELECT _migrate_to_numeric('analytics_conversions', 'value', 12, 2);

-- =====================================================================
-- invoice_ocr_history
-- =====================================================================
SELECT _migrate_to_numeric('invoice_ocr_history', 'confidence_score', 5, 4);

-- =====================================================================
-- transfer_suggestions
-- =====================================================================
SELECT _migrate_to_numeric('transfer_suggestions', 'suggested_qty', 12, 4);

-- =====================================================================
-- shelf_audits
-- =====================================================================
SELECT _migrate_to_numeric('shelf_audits', 'fill_level_pct', 5, 2);

-- =====================================================================
-- warehouse_pickups
-- =====================================================================
SELECT _migrate_to_numeric('warehouse_pickups', 'quantity', 12, 4);

-- =====================================================================
-- cart_items
-- =====================================================================
SELECT _migrate_to_numeric('cart_items', 'quantity',   12, 4);
SELECT _migrate_to_numeric('cart_items', 'unit_price', 12, 2);

-- =====================================================================
-- resurrection_bundles (incluida: es tabla de negocio, no ghost_*)
-- =====================================================================
SELECT _migrate_to_numeric('resurrection_bundles', 'original_value', 12, 2);
SELECT _migrate_to_numeric('resurrection_bundles', 'bundle_price',   12, 2);
SELECT _migrate_to_numeric('resurrection_bundles', 'discount_pct',    5, 4);

-- Limpieza del helper
DROP FUNCTION IF EXISTS _migrate_to_numeric(TEXT, TEXT, INT, INT);

-- Registro de versión
INSERT INTO schema_version(version) VALUES (40)
ON CONFLICT DO NOTHING;

COMMIT;
