-- Migration 020: Performance indexes identified in deep audit (Feb 24, 2026)
-- These indexes address full table scans in dashboard, turns, inventory, and search queries.

BEGIN;

-- Cash movements: used in close_turn, get_turn_summary, expenses
CREATE INDEX IF NOT EXISTS idx_cash_movements_turn_id ON cash_movements(turn_id);
CREATE INDEX IF NOT EXISTS idx_cash_movements_type ON cash_movements(type);

-- Inventory movements: filtered by product_id and movement_type
CREATE INDEX IF NOT EXISTS idx_inv_movements_product_id ON inventory_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_movements_type ON inventory_movements(movement_type);

-- Sales: folio search (trigram), serie filter (RESICO), branch filter
CREATE INDEX IF NOT EXISTS idx_sales_folio_visible_trgm ON sales USING gin(folio_visible gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_sales_serie ON sales(serie);
CREATE INDEX IF NOT EXISTS idx_sales_branch_id ON sales(branch_id);

-- Loss records: filtered by status in mermas endpoints
CREATE INDEX IF NOT EXISTS idx_loss_records_status ON loss_records(status);

-- Credit history: queried by customer_id
CREATE INDEX IF NOT EXISTS idx_credit_history_customer_id ON credit_history(customer_id);

-- Remote notifications: partial index for unsent
CREATE INDEX IF NOT EXISTS idx_notifications_sent ON remote_notifications(sent) WHERE sent = 0;

-- Products: category text (existing idx_products_category is on category_id which is unused)
CREATE INDEX IF NOT EXISTS idx_products_category_text ON products(category) WHERE is_active = 1;

-- Products: barcode trigram for search
CREATE INDEX IF NOT EXISTS idx_products_barcode_trgm ON products USING gin(barcode gin_trgm_ops);

-- Customers: phone trigram for search
CREATE INDEX IF NOT EXISTS idx_customers_phone_trgm ON customers USING gin(phone gin_trgm_ops);

INSERT INTO schema_version (version, description, applied_at)
VALUES (20, 'Performance indexes from deep audit', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
