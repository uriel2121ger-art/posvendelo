-- Migration 038: Convert DOUBLE PRECISION → NUMERIC in sales and sale_items
-- Drops dependent views/matviews, alters columns, recreates everything, adds indexes.
-- Idempotent: each ALTER checks current data_type before executing.

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────────
-- 1. DROP dependent views (order matters: views before matviews)
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_sales_with_origin;
DROP MATERIALIZED VIEW IF EXISTS mv_daily_sales_summary;
DROP MATERIALIZED VIEW IF EXISTS mv_hourly_sales_heatmap;
DROP MATERIALIZED VIEW IF EXISTS mv_product_sales_ranking;

-- ──────────────────────────────────────────────────────────────────────────────
-- 2. ALTER sales columns → NUMERIC(12,2)
-- ──────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    col_type TEXT;
BEGIN
    -- total
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'total';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN total TYPE NUMERIC(12,2) USING total::numeric(12,2);
    END IF;

    -- subtotal
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'subtotal';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN subtotal TYPE NUMERIC(12,2) USING subtotal::numeric(12,2);
    END IF;

    -- tax
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'tax';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN tax TYPE NUMERIC(12,2) USING tax::numeric(12,2);
    END IF;

    -- discount
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'discount';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN discount TYPE NUMERIC(12,2) USING discount::numeric(12,2);
    END IF;

    -- cash_received
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'cash_received';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN cash_received TYPE NUMERIC(12,2) USING cash_received::numeric(12,2);
    END IF;

    -- change_given
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'change_given';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN change_given TYPE NUMERIC(12,2) USING change_given::numeric(12,2);
    END IF;

    -- mixed_cash
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'mixed_cash';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN mixed_cash TYPE NUMERIC(12,2) USING mixed_cash::numeric(12,2);
    END IF;

    -- mixed_card
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'mixed_card';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN mixed_card TYPE NUMERIC(12,2) USING mixed_card::numeric(12,2);
    END IF;

    -- mixed_transfer
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'mixed_transfer';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN mixed_transfer TYPE NUMERIC(12,2) USING mixed_transfer::numeric(12,2);
    END IF;

    -- mixed_wallet
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'mixed_wallet';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN mixed_wallet TYPE NUMERIC(12,2) USING mixed_wallet::numeric(12,2);
    END IF;

    -- mixed_gift_card
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sales' AND column_name = 'mixed_gift_card';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sales ALTER COLUMN mixed_gift_card TYPE NUMERIC(12,2) USING mixed_gift_card::numeric(12,2);
    END IF;
END $$;

-- ──────────────────────────────────────────────────────────────────────────────
-- 3. ALTER sale_items columns
-- ──────────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    col_type TEXT;
BEGIN
    -- price → NUMERIC(12,2)
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sale_items' AND column_name = 'price';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sale_items ALTER COLUMN price TYPE NUMERIC(12,2) USING price::numeric(12,2);
    END IF;

    -- qty → NUMERIC(12,4)  (fracciones: 1.5 kg, etc.)
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sale_items' AND column_name = 'qty';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sale_items ALTER COLUMN qty TYPE NUMERIC(12,4) USING qty::numeric(12,4);
    END IF;

    -- subtotal → NUMERIC(12,2)
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sale_items' AND column_name = 'subtotal';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sale_items ALTER COLUMN subtotal TYPE NUMERIC(12,2) USING subtotal::numeric(12,2);
    END IF;

    -- total → NUMERIC(12,2)
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sale_items' AND column_name = 'total';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sale_items ALTER COLUMN total TYPE NUMERIC(12,2) USING total::numeric(12,2);
    END IF;

    -- discount → NUMERIC(12,2)
    SELECT data_type INTO col_type FROM information_schema.columns
    WHERE table_name = 'sale_items' AND column_name = 'discount';
    IF col_type <> 'numeric' THEN
        ALTER TABLE sale_items ALTER COLUMN discount TYPE NUMERIC(12,2) USING discount::numeric(12,2);
    END IF;
END $$;

-- ──────────────────────────────────────────────────────────────────────────────
-- 4. Recrear v_sales_with_origin
-- ──────────────────────────────────────────────────────────────────────────────
CREATE VIEW v_sales_with_origin AS
 SELECT s.id AS sale_id,
    s.uuid,
    s."timestamp",
    s.created_at,
    s.updated_at,
    s.total,
    s.subtotal,
    s.tax,
    s.discount,
    s.status,
    COALESCE(s.pos_id, ('T'::text || (t.terminal_id)::text), s.synced_from_terminal, 'DESCONOCIDO'::text) AS terminal_identifier,
    s.pos_id AS pos_id_sale,
    t.terminal_id,
    t.pos_id AS pos_id_turn,
    s.synced_from_terminal,
    s.branch_id,
    b.name AS branch_name,
    b.code AS branch_code,
    s.turn_id,
    t.start_timestamp AS turn_start,
    t.end_timestamp AS turn_end,
    s.user_id,
    u.username,
    u.name AS user_name,
    s.customer_id,
    c.name AS customer_name,
    s.serie,
    s.folio_visible,
    s.payment_method,
    s.synced,
    s.sync_status
   FROM ((((sales s
     LEFT JOIN turns t ON ((s.turn_id = t.id)))
     LEFT JOIN branches b ON ((s.branch_id = b.id)))
     LEFT JOIN users u ON ((s.user_id = u.id)))
     LEFT JOIN customers c ON ((s.customer_id = c.id)))
  WHERE (s.visible = 1);

-- ──────────────────────────────────────────────────────────────────────────────
-- 5. Recrear mv_daily_sales_summary
-- ──────────────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW mv_daily_sales_summary AS
 SELECT date(s."timestamp") AS sale_date,
    s.branch_id,
    count(*) AS total_transactions,
    sum(s.total) AS total_revenue,
    sum(s.subtotal) AS total_subtotal,
    sum(s.tax) AS total_tax,
    sum(s.discount) AS total_discounts,
    avg(s.total) AS avg_ticket,
    count(DISTINCT s.customer_id) AS unique_customers,
    count(DISTINCT s.user_id) AS unique_cashiers
   FROM sales s
  WHERE (s.status = 'completed'::text)
  GROUP BY (date(s."timestamp")), s.branch_id;

CREATE UNIQUE INDEX idx_mv_daily_sales_date_branch
    ON mv_daily_sales_summary USING btree (sale_date, branch_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 6. Recrear mv_hourly_sales_heatmap
-- ──────────────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW mv_hourly_sales_heatmap AS
 SELECT (EXTRACT(dow FROM s."timestamp"))::integer AS day_of_week,
    (EXTRACT(hour FROM s."timestamp"))::integer AS hour_of_day,
    s.branch_id,
    count(*) AS transaction_count,
    sum(s.total) AS revenue
   FROM sales s
  WHERE ((s.status = 'completed'::text) AND (s."timestamp" >= (now() - '90 days'::interval)))
  GROUP BY ((EXTRACT(dow FROM s."timestamp"))::integer), ((EXTRACT(hour FROM s."timestamp"))::integer), s.branch_id;

CREATE UNIQUE INDEX idx_mv_heatmap_dow_hour_branch
    ON mv_hourly_sales_heatmap USING btree (day_of_week, hour_of_day, branch_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 7. Recrear mv_product_sales_ranking
-- ──────────────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW mv_product_sales_ranking AS
 SELECT si.product_id,
    p.name AS product_name,
    p.sku,
    p.category,
    sum(si.qty) AS total_qty_sold,
    sum(si.subtotal) AS total_revenue,
    count(DISTINCT si.sale_id) AS num_transactions,
    avg(si.price) AS avg_price
   FROM ((sale_items si
     JOIN products p ON ((p.id = si.product_id)))
     JOIN sales s ON ((s.id = si.sale_id)))
  WHERE (s.status = 'completed'::text)
  GROUP BY si.product_id, p.name, p.sku, p.category;

CREATE UNIQUE INDEX idx_mv_product_ranking_id
    ON mv_product_sales_ranking USING btree (product_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- 8. Registrar versión
-- ──────────────────────────────────────────────────────────────────────────────
INSERT INTO schema_version(version) VALUES (38) ON CONFLICT DO NOTHING;

COMMIT;
