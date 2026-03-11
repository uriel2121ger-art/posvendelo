-- =============================================================================
-- Migration 048: Fix REAL/DOUBLE PRECISION → NUMERIC in fiscal tables
-- =============================================================================
-- Columns storing monetary values must use NUMERIC(12,2) to prevent
-- floating-point precision errors.  Exchange rates use NUMERIC(12,4).
-- Each ALTER is idempotent (safe to re-run).
-- =============================================================================

-- crypto_conversions (liquidity_bridge)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='crypto_conversions' AND column_name='amount_mxn') THEN
        ALTER TABLE crypto_conversions ALTER COLUMN amount_mxn TYPE NUMERIC(12,2);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='crypto_conversions' AND column_name='amount_usd') THEN
        ALTER TABLE crypto_conversions ALTER COLUMN amount_usd TYPE NUMERIC(12,2);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='crypto_conversions' AND column_name='exchange_rate') THEN
        ALTER TABLE crypto_conversions ALTER COLUMN exchange_rate TYPE NUMERIC(12,4);
    END IF;
END $$;

-- cold_wallets (liquidity_bridge)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cold_wallets' AND column_name='balance_usd') THEN
        ALTER TABLE cold_wallets ALTER COLUMN balance_usd TYPE NUMERIC(12,2);
    END IF;
END $$;

-- cash_expenses (liquidity_bridge)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cash_expenses' AND column_name='amount') THEN
        ALTER TABLE cash_expenses ALTER COLUMN amount TYPE NUMERIC(12,2);
    END IF;
END $$;

-- ghost_wallets (reserve_wallet)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ghost_wallets' AND column_name='balance') THEN
        ALTER TABLE ghost_wallets ALTER COLUMN balance TYPE NUMERIC(12,2);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ghost_wallets' AND column_name='total_earned') THEN
        ALTER TABLE ghost_wallets ALTER COLUMN total_earned TYPE NUMERIC(12,2);
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ghost_wallets' AND column_name='total_spent') THEN
        ALTER TABLE ghost_wallets ALTER COLUMN total_spent TYPE NUMERIC(12,2);
    END IF;
END $$;

-- ghost_transactions (reserve_wallet)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ghost_transactions' AND column_name='amount') THEN
        ALTER TABLE ghost_transactions ALTER COLUMN amount TYPE NUMERIC(12,2);
    END IF;
END $$;

-- cross_invoices (intercompany_billing)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='cross_invoices' AND column_name='amount') THEN
        ALTER TABLE cross_invoices ALTER COLUMN amount TYPE NUMERIC(12,2);
    END IF;
END $$;

INSERT INTO schema_version(version, description)
VALUES (48, 'fiscal_numeric_columns')
ON CONFLICT DO NOTHING;
