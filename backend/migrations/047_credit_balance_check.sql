-- Prevent negative credit balances at DB level
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_credit_balance_non_negative'
    ) THEN
        ALTER TABLE customers
            ADD CONSTRAINT chk_credit_balance_non_negative
            CHECK (credit_balance >= 0);
    END IF;
END $$;

INSERT INTO schema_version(version, description)
VALUES (47, 'credit_balance non-negative CHECK constraint')
ON CONFLICT DO NOTHING;
