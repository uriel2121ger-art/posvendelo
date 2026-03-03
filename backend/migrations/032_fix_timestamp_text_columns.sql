-- 032_fix_timestamp_text_columns.sql
-- Corrige columnas que fueron creadas como TEXT en migraciones tempranas.
-- schema.sql v6.3.2 ya las declara como TIMESTAMP — esta migración alinea la BD real.
-- Idempotente: solo altera si la columna actual es TEXT.

-- cash_movements.timestamp: TEXT → TIMESTAMP
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'cash_movements'
        AND column_name = 'timestamp'
        AND data_type = 'text'
    ) THEN
        ALTER TABLE cash_movements
            ALTER COLUMN "timestamp" TYPE TIMESTAMP USING "timestamp"::timestamp;
        ALTER TABLE cash_movements
            ALTER COLUMN "timestamp" SET DEFAULT NOW();
        RAISE NOTICE 'cash_movements.timestamp: TEXT → TIMESTAMP ✓';
    END IF;
END $$;

-- turns.start_timestamp: TEXT → TIMESTAMP
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'turns'
        AND column_name = 'start_timestamp'
        AND data_type = 'text'
    ) THEN
        ALTER TABLE turns
            ALTER COLUMN start_timestamp TYPE TIMESTAMP USING start_timestamp::timestamp;
        ALTER TABLE turns
            ALTER COLUMN start_timestamp SET DEFAULT NOW();
        RAISE NOTICE 'turns.start_timestamp: TEXT → TIMESTAMP ✓';
    END IF;
END $$;

-- turns.end_timestamp: TEXT → TIMESTAMP
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'turns'
        AND column_name = 'end_timestamp'
        AND data_type = 'text'
    ) THEN
        ALTER TABLE turns
            ALTER COLUMN end_timestamp TYPE TIMESTAMP USING end_timestamp::timestamp;
        RAISE NOTICE 'turns.end_timestamp: TEXT → TIMESTAMP ✓';
    END IF;
END $$;

-- returns.processed_at: TEXT → TIMESTAMP
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'returns'
        AND column_name = 'processed_at'
        AND data_type = 'text'
    ) THEN
        ALTER TABLE returns
            ALTER COLUMN processed_at TYPE TIMESTAMP USING processed_at::timestamp;
        RAISE NOTICE 'returns.processed_at: TEXT → TIMESTAMP ✓';
    END IF;
END $$;

-- Registrar versión (faltaba — causaba re-ejecución en cada migrate)
INSERT INTO schema_version (version, description)
VALUES (32, 'fix_timestamp_text_columns_cash_movements_turns_returns')
ON CONFLICT (version) DO NOTHING;
