-- =============================================================================
-- POSVENDELO — Event Sourcing: sale_events table
-- Phase 5: Append-only event store for sale aggregates
--
-- Run: psql -U posvendelo_user -d posvendelo -f migrations/add_sale_events_table.sql
-- =============================================================================

-- Sale events (append-only event stream)
CREATE TABLE IF NOT EXISTS sale_events (
    id              BIGSERIAL PRIMARY KEY,
    event_id        TEXT UNIQUE NOT NULL,
    sale_id         INTEGER NOT NULL,
    sequence        INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    data            JSONB NOT NULL DEFAULT '{}',
    user_id         INTEGER,
    metadata        JSONB DEFAULT '{}',
    timestamp       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Enforce unique sequence per sale
    CONSTRAINT uq_sale_events_sale_seq UNIQUE (sale_id, sequence)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sale_events_sale_id ON sale_events (sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_events_type ON sale_events (event_type);
CREATE INDEX IF NOT EXISTS idx_sale_events_timestamp ON sale_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_sale_events_user ON sale_events (user_id) WHERE user_id IS NOT NULL;

-- Saga tracking (for multi-step distributed operations)
CREATE TABLE IF NOT EXISTS saga_instances (
    id              BIGSERIAL PRIMARY KEY,
    saga_id         TEXT UNIQUE NOT NULL,
    saga_type       TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'started',
    data            JSONB NOT NULL DEFAULT '{}',
    current_step    INTEGER NOT NULL DEFAULT 0,
    total_steps     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_saga_type ON saga_instances (saga_type);
CREATE INDEX IF NOT EXISTS idx_saga_state ON saga_instances (state);

-- Saga step log (compensations)
CREATE TABLE IF NOT EXISTS saga_steps (
    id              BIGSERIAL PRIMARY KEY,
    saga_id         TEXT NOT NULL REFERENCES saga_instances(saga_id),
    step_number     INTEGER NOT NULL,
    step_name       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending, completed, compensating, compensated, failed
    data            JSONB DEFAULT '{}',
    result          JSONB DEFAULT '{}',
    error_message   TEXT,
    executed_at     TIMESTAMP WITH TIME ZONE,
    compensated_at  TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_saga_steps_saga ON saga_steps (saga_id);

-- =============================================================================
-- CQRS: Materialized views for read-heavy queries
-- =============================================================================

-- Daily sales summary (refreshed periodically)
-- Note: sales.timestamp is TEXT (ISO format), cast to TIMESTAMP for date ops
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sales_summary AS
SELECT
    DATE(s.timestamp::TIMESTAMP) AS sale_date,
    s.branch_id,
    COUNT(*) AS total_transactions,
    SUM(s.total) AS total_revenue,
    SUM(s.subtotal) AS total_subtotal,
    SUM(s.tax) AS total_tax,
    SUM(s.discount) AS total_discounts,
    AVG(s.total) AS avg_ticket,
    COUNT(DISTINCT s.customer_id) AS unique_customers,
    COUNT(DISTINCT s.user_id) AS unique_cashiers
FROM sales s
WHERE s.status = 'completed'
GROUP BY DATE(s.timestamp::TIMESTAMP), s.branch_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_sales_date_branch
ON mv_daily_sales_summary (sale_date, branch_id);

-- Product sales ranking (for reports)
-- Note: sale_items uses 'qty' (not 'quantity'), subtotal exists as column
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_sales_ranking AS
SELECT
    si.product_id,
    p.name AS product_name,
    p.sku,
    p.category,
    SUM(si.qty) AS total_qty_sold,
    SUM(si.subtotal) AS total_revenue,
    COUNT(DISTINCT si.sale_id) AS num_transactions,
    AVG(si.price) AS avg_price
FROM sale_items si
JOIN products p ON p.id = si.product_id
JOIN sales s ON s.id = si.sale_id
WHERE s.status = 'completed'
GROUP BY si.product_id, p.name, p.sku, p.category;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_product_ranking_id
ON mv_product_sales_ranking (product_id);

-- Hourly heatmap (for staffing decisions)
-- Note: cast TEXT timestamp to TIMESTAMP for EXTRACT
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_sales_heatmap AS
SELECT
    EXTRACT(DOW FROM s.timestamp::TIMESTAMP)::INTEGER AS day_of_week,
    EXTRACT(HOUR FROM s.timestamp::TIMESTAMP)::INTEGER AS hour_of_day,
    s.branch_id,
    COUNT(*) AS transaction_count,
    SUM(s.total) AS revenue
FROM sales s
WHERE s.status = 'completed'
  AND s.timestamp::TIMESTAMP >= NOW() - INTERVAL '90 days'
GROUP BY day_of_week, hour_of_day, s.branch_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_heatmap_dow_hour_branch
ON mv_hourly_sales_heatmap (day_of_week, hour_of_day, branch_id);

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_sales_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_product_sales_ranking;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_sales_heatmap;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Comments
-- =============================================================================
COMMENT ON TABLE sale_events IS 'Append-only event store for sale aggregates (Event Sourcing)';
COMMENT ON TABLE saga_instances IS 'Saga orchestration tracking (e.g., inventory transfers)';
COMMENT ON TABLE saga_steps IS 'Individual steps within a saga with compensation support';
COMMENT ON MATERIALIZED VIEW mv_daily_sales_summary IS 'CQRS read model: daily sales aggregates';
COMMENT ON MATERIALIZED VIEW mv_product_sales_ranking IS 'CQRS read model: product sales ranking';
COMMENT ON MATERIALIZED VIEW mv_hourly_sales_heatmap IS 'CQRS read model: hourly transaction heatmap';

INSERT INTO schema_version (version, description, applied_at)
VALUES (28, 'add_sale_events_and_saga_tables', NOW())
ON CONFLICT (version) DO NOTHING;
