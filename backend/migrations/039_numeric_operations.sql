-- Migration 039: Convert double precision columns to NUMERIC in operational tables
-- Idempotent: each ALTER is wrapped in DO $$ with data_type check
-- Tables: products, customers, turns, cash_movements, cash_expenses,
--         cash_extractions, credit_movements, credit_history, turn_movements

BEGIN;

-- ─── products (13 columns) ───────────────────────────────────────────────────

-- Money columns → NUMERIC(12,2)
DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='price') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN price TYPE NUMERIC(12,2) USING price::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='cost') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN cost TYPE NUMERIC(12,2) USING cost::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='cost_price') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN cost_price TYPE NUMERIC(12,2) USING cost_price::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='cost_a') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN cost_a TYPE NUMERIC(12,2) USING cost_a::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='cost_b') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN cost_b TYPE NUMERIC(12,2) USING cost_b::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='price_wholesale') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN price_wholesale TYPE NUMERIC(12,2) USING price_wholesale::NUMERIC(12,2);
  END IF;
END $$;

-- Quantity/stock columns → NUMERIC(12,4)
DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='stock') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN stock TYPE NUMERIC(12,4) USING stock::NUMERIC(12,4);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='min_stock') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN min_stock TYPE NUMERIC(12,4) USING min_stock::NUMERIC(12,4);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='max_stock') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN max_stock TYPE NUMERIC(12,4) USING max_stock::NUMERIC(12,4);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='shadow_stock') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN shadow_stock TYPE NUMERIC(12,4) USING shadow_stock::NUMERIC(12,4);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='qty_from_a') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN qty_from_a TYPE NUMERIC(12,4) USING qty_from_a::NUMERIC(12,4);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='qty_from_b') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN qty_from_b TYPE NUMERIC(12,4) USING qty_from_b::NUMERIC(12,4);
  END IF;
END $$;

-- Tax rate → NUMERIC(5,4)
DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='products' AND column_name='tax_rate') != 'numeric' THEN
    ALTER TABLE products ALTER COLUMN tax_rate TYPE NUMERIC(5,4) USING tax_rate::NUMERIC(5,4);
  END IF;
END $$;

-- ─── customers (3 columns) ───────────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='customers' AND column_name='credit_balance') != 'numeric' THEN
    ALTER TABLE customers ALTER COLUMN credit_balance TYPE NUMERIC(12,2) USING credit_balance::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='customers' AND column_name='credit_limit') != 'numeric' THEN
    ALTER TABLE customers ALTER COLUMN credit_limit TYPE NUMERIC(12,2) USING credit_limit::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='customers' AND column_name='wallet_balance') != 'numeric' THEN
    ALTER TABLE customers ALTER COLUMN wallet_balance TYPE NUMERIC(12,2) USING wallet_balance::NUMERIC(12,2);
  END IF;
END $$;

-- ─── turns (4 columns) ───────────────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='turns' AND column_name='initial_cash') != 'numeric' THEN
    ALTER TABLE turns ALTER COLUMN initial_cash TYPE NUMERIC(12,2) USING initial_cash::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='turns' AND column_name='final_cash') != 'numeric' THEN
    ALTER TABLE turns ALTER COLUMN final_cash TYPE NUMERIC(12,2) USING final_cash::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='turns' AND column_name='system_sales') != 'numeric' THEN
    ALTER TABLE turns ALTER COLUMN system_sales TYPE NUMERIC(12,2) USING system_sales::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='turns' AND column_name='difference') != 'numeric' THEN
    ALTER TABLE turns ALTER COLUMN difference TYPE NUMERIC(12,2) USING difference::NUMERIC(12,2);
  END IF;
END $$;

-- ─── cash_movements (1 column) ───────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='cash_movements' AND column_name='amount') != 'numeric' THEN
    ALTER TABLE cash_movements ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
  END IF;
END $$;

-- ─── cash_expenses (1 column) ────────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='cash_expenses' AND column_name='amount') != 'numeric' THEN
    ALTER TABLE cash_expenses ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
  END IF;
END $$;

-- ─── cash_extractions (1 column) ─────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='cash_extractions' AND column_name='amount') != 'numeric' THEN
    ALTER TABLE cash_extractions ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
  END IF;
END $$;

-- ─── credit_movements (2 columns) ────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='credit_movements' AND column_name='amount') != 'numeric' THEN
    ALTER TABLE credit_movements ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='credit_movements' AND column_name='balance_after') != 'numeric' THEN
    ALTER TABLE credit_movements ALTER COLUMN balance_after TYPE NUMERIC(12,2) USING balance_after::NUMERIC(12,2);
  END IF;
END $$;

-- ─── credit_history (3 columns) ──────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='credit_history' AND column_name='amount') != 'numeric' THEN
    ALTER TABLE credit_history ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='credit_history' AND column_name='balance_before') != 'numeric' THEN
    ALTER TABLE credit_history ALTER COLUMN balance_before TYPE NUMERIC(12,2) USING balance_before::NUMERIC(12,2);
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='credit_history' AND column_name='balance_after') != 'numeric' THEN
    ALTER TABLE credit_history ALTER COLUMN balance_after TYPE NUMERIC(12,2) USING balance_after::NUMERIC(12,2);
  END IF;
END $$;

-- ─── turn_movements (1 column) ───────────────────────────────────────────────

DO $$ BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema='public' AND table_name='turn_movements' AND column_name='amount') != 'numeric' THEN
    ALTER TABLE turn_movements ALTER COLUMN amount TYPE NUMERIC(12,2) USING amount::NUMERIC(12,2);
  END IF;
END $$;

-- ─── schema_version ──────────────────────────────────────────────────────────

INSERT INTO schema_version (version, description, applied_at)
VALUES (39, 'Convert double precision to NUMERIC in operational tables', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
