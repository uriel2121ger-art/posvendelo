-- TITAN POS - Performance Optimization Indexes
-- This migration adds critical indexes to improve query performance

-- Products table indexes (most searched)
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

-- Sales table indexes (frequent queries)
CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_turn_id ON sales(turn_id);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);

-- Turns table indexes (lookup optimization)
CREATE INDEX IF NOT EXISTS idx_turns_user_status ON turns(user_id, status);
CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(start_timestamp);

-- Customers table indexes (search optimization)
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_rfc ON customers(rfc);

-- Sale items (JOIN optimization)
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);

-- Loyalty accounts (MIDAS optimization)
CREATE INDEX IF NOT EXISTS idx_loyalty_customer ON loyalty_accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_level ON loyalty_accounts(nivel_lealtad);

-- Employee loans
CREATE INDEX IF NOT EXISTS idx_loans_employee ON employee_loans(employee_id);
CREATE INDEX IF NOT EXISTS idx_loans_status ON employee_loans(status);

-- Analyze tables for query planner optimization
-- PostgreSQL: ANALYZE es compatible, pero puede requerir privilegios
-- Se ejecuta automáticamente en PostgreSQL, pero puede ejecutarse manualmente
-- ANALYZE products;
-- ANALYZE sales;
-- ANALYZE customers;
-- ANALYZE turns;

INSERT INTO schema_version (version, description, applied_at)
VALUES (6, 'Performance optimization indexes', NOW())
ON CONFLICT (version) DO NOTHING;
