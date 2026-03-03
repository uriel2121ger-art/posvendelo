-- 035_timestamp_text_to_timestamp.sql
-- Convierte columnas de fecha TEXT → TIMESTAMP en tablas core.
-- Idempotente: verifica el tipo actual antes de alterar.
-- Maneja NULLs y strings vacíos/inválidos poniéndolos en NULL.
--
-- Tablas cubiertas (prioridad por impacto en queries):
--   1. sales.timestamp                 — filtros de dashboard, reportes RESICO, búsquedas
--   2. employees.created_at            — listado de empleados
--   3. employees.hire_date             — DATE (no TIMESTAMP)
--   4. card_transactions.timestamp     — reportes de pagos
--   5. credit_history.timestamp        — historial de crédito
--   6. time_clock_entries.timestamp    — entradas de reloj
--   7. time_clock_entries.entry_date   — fecha de entrada
--   8. attendance.date                 — asistencia
-- NOTE: cash_expenses.timestamp — la tabla en prod es cash_movements (ya migrada en 032)
-- NOTE: schema.sql ya refleja TIMESTAMP en instalaciones limpias

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 0. Drop vistas dependientes de sales.timestamp (se recrean al final)
-- ─────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_sales_with_origin;
DROP MATERIALIZED VIEW IF EXISTS mv_daily_sales_summary;
DROP MATERIALIZED VIEW IF EXISTS mv_hourly_sales_heatmap;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. sales.timestamp — TEXT → TIMESTAMPTZ
--    Los valores actuales tienen offset +00 (e.g. "2026-02-28 21:54:25.041194+00")
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sales'
          AND column_name = 'timestamp'
          AND data_type = 'text'
    ) THEN
        -- Vaciar strings vacíos → NULL antes de castear
        UPDATE sales SET "timestamp" = NULL
        WHERE "timestamp" IS NOT NULL AND TRIM("timestamp") = '';

        -- Convertir a TIMESTAMPTZ (WITH TIME ZONE) preservando el +00 offset
        ALTER TABLE sales
            ALTER COLUMN "timestamp" TYPE TIMESTAMPTZ
            USING CASE
                WHEN "timestamp" IS NULL THEN NULL
                ELSE "timestamp"::timestamptz
            END;

        ALTER TABLE sales
            ALTER COLUMN "timestamp" SET DEFAULT NOW();

        RAISE NOTICE 'sales.timestamp: TEXT → TIMESTAMPTZ ✓';
    ELSE
        RAISE NOTICE 'sales.timestamp: ya es TIMESTAMP — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. employees.created_at — TEXT → TIMESTAMP
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'employees'
          AND column_name = 'created_at'
          AND data_type = 'text'
    ) THEN
        UPDATE employees SET created_at = NULL
        WHERE created_at IS NOT NULL AND TRIM(created_at) = '';

        ALTER TABLE employees
            ALTER COLUMN created_at TYPE TIMESTAMP
            USING CASE
                WHEN created_at IS NULL THEN NULL
                ELSE created_at::timestamp
            END;

        ALTER TABLE employees
            ALTER COLUMN created_at SET DEFAULT NOW();

        RAISE NOTICE 'employees.created_at: TEXT → TIMESTAMP ✓';
    ELSE
        RAISE NOTICE 'employees.created_at: ya es TIMESTAMP — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. employees.hire_date — TEXT → DATE
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'employees'
          AND column_name = 'hire_date'
          AND data_type = 'text'
    ) THEN
        UPDATE employees SET hire_date = NULL
        WHERE hire_date IS NOT NULL AND TRIM(hire_date) = '';

        ALTER TABLE employees
            ALTER COLUMN hire_date TYPE DATE
            USING CASE
                WHEN hire_date IS NULL THEN NULL
                ELSE hire_date::date
            END;

        RAISE NOTICE 'employees.hire_date: TEXT → DATE ✓';
    ELSE
        RAISE NOTICE 'employees.hire_date: ya es DATE — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. card_transactions.timestamp — TEXT → TIMESTAMP
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'card_transactions'
          AND column_name = 'timestamp'
          AND data_type = 'text'
    ) THEN
        UPDATE card_transactions SET "timestamp" = NULL
        WHERE "timestamp" IS NOT NULL AND TRIM("timestamp") = '';

        ALTER TABLE card_transactions
            ALTER COLUMN "timestamp" TYPE TIMESTAMP
            USING CASE
                WHEN "timestamp" IS NULL THEN NULL
                ELSE "timestamp"::timestamp
            END;

        ALTER TABLE card_transactions
            ALTER COLUMN "timestamp" SET DEFAULT NOW();

        RAISE NOTICE 'card_transactions.timestamp: TEXT → TIMESTAMP ✓';
    ELSE
        RAISE NOTICE 'card_transactions.timestamp: ya es TIMESTAMP — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. credit_history.timestamp — TEXT → TIMESTAMP
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'credit_history'
          AND column_name = 'timestamp'
          AND data_type = 'text'
    ) THEN
        UPDATE credit_history SET "timestamp" = NULL
        WHERE "timestamp" IS NOT NULL AND TRIM("timestamp") = '';

        ALTER TABLE credit_history
            ALTER COLUMN "timestamp" TYPE TIMESTAMP
            USING CASE
                WHEN "timestamp" IS NULL THEN NULL
                ELSE "timestamp"::timestamp
            END;

        ALTER TABLE credit_history
            ALTER COLUMN "timestamp" SET DEFAULT NOW();

        RAISE NOTICE 'credit_history.timestamp: TEXT → TIMESTAMP ✓';
    ELSE
        RAISE NOTICE 'credit_history.timestamp: ya es TIMESTAMP — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. time_clock_entries.timestamp — TEXT → TIMESTAMP
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'time_clock_entries'
          AND column_name = 'timestamp'
          AND data_type = 'text'
    ) THEN
        UPDATE time_clock_entries SET "timestamp" = NULL
        WHERE "timestamp" IS NOT NULL AND TRIM("timestamp") = '';

        ALTER TABLE time_clock_entries
            ALTER COLUMN "timestamp" TYPE TIMESTAMP
            USING CASE
                WHEN "timestamp" IS NULL THEN NULL
                ELSE "timestamp"::timestamp
            END;

        ALTER TABLE time_clock_entries
            ALTER COLUMN "timestamp" SET DEFAULT NOW();

        RAISE NOTICE 'time_clock_entries.timestamp: TEXT → TIMESTAMP ✓';
    ELSE
        RAISE NOTICE 'time_clock_entries.timestamp: ya es TIMESTAMP — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. time_clock_entries.entry_date — TEXT → DATE
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'time_clock_entries'
          AND column_name = 'entry_date'
          AND data_type = 'text'
    ) THEN
        UPDATE time_clock_entries SET entry_date = NULL
        WHERE entry_date IS NOT NULL AND TRIM(entry_date) = '';

        ALTER TABLE time_clock_entries
            ALTER COLUMN entry_date TYPE DATE
            USING CASE
                WHEN entry_date IS NULL THEN NULL
                ELSE entry_date::date
            END;

        RAISE NOTICE 'time_clock_entries.entry_date: TEXT → DATE ✓';
    ELSE
        RAISE NOTICE 'time_clock_entries.entry_date: ya es DATE — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. attendance.date — TEXT → DATE
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'attendance'
          AND column_name = 'date'
          AND data_type = 'text'
    ) THEN
        UPDATE attendance SET "date" = NULL
        WHERE "date" IS NOT NULL AND TRIM("date") = '';

        ALTER TABLE attendance
            ALTER COLUMN "date" TYPE DATE
            USING CASE
                WHEN "date" IS NULL THEN NULL
                ELSE "date"::date
            END;

        RAISE NOTICE 'attendance.date: TEXT → DATE ✓';
    ELSE
        RAISE NOTICE 'attendance.date: ya es DATE — sin cambios';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Recrear índice en sales.timestamp si no existe (puede haberse dropado en ALTER)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales ("timestamp");

-- ─────────────────────────────────────────────────────────────────────────────
-- Recrear vista v_sales_with_origin (dropeada al inicio)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_sales_with_origin AS
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
    COALESCE(s.pos_id, ('T' || t.terminal_id::text), s.synced_from_terminal, 'DESCONOCIDO') AS terminal_identifier,
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
FROM sales s
    LEFT JOIN turns t ON s.turn_id = t.id
    LEFT JOIN branches b ON s.branch_id = b.id
    LEFT JOIN users u ON s.user_id = u.id
    LEFT JOIN customers c ON s.customer_id = c.id
WHERE s.visible = 1;

-- ─────────────────────────────────────────────────────────────────────────────
-- Recrear materialized view mv_daily_sales_summary (dropeada al inicio)
-- Ahora sales.timestamp es TIMESTAMPTZ, no necesita cast ::timestamp
-- ─────────────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sales_summary AS
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
WHERE s.status = 'completed'
GROUP BY date(s."timestamp"), s.branch_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_sales_date_branch
    ON mv_daily_sales_summary(sale_date, branch_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Recrear materialized view mv_hourly_sales_heatmap (dropeada al inicio)
-- Con TIMESTAMPTZ ya no necesita cast ::timestamp
-- ─────────────────────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_sales_heatmap AS
SELECT (EXTRACT(dow FROM s."timestamp"))::integer AS day_of_week,
    (EXTRACT(hour FROM s."timestamp"))::integer AS hour_of_day,
    s.branch_id,
    count(*) AS transaction_count,
    sum(s.total) AS revenue
FROM sales s
WHERE s.status = 'completed'
  AND s."timestamp" >= (now() - '90 days'::interval)
GROUP BY (EXTRACT(dow FROM s."timestamp"))::integer,
         (EXTRACT(hour FROM s."timestamp"))::integer,
         s.branch_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_heatmap_dow_hour_branch
    ON mv_hourly_sales_heatmap(day_of_week, hour_of_day, branch_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Registrar versión
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO schema_version (version, description, applied_at)
VALUES (35, 'timestamp_text_to_timestamp_core_tables', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
