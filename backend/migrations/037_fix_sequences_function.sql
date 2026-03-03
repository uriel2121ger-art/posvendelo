-- =============================================================================
-- 037_fix_sequences_function.sql
-- Crea función reutilizable fix_all_sequences() para corregir secuencias
-- desincronizadas después de operaciones de sync hub-spoke.
--
-- BUG CONOCIDO: después de sync, las secuencias PostgreSQL pueden quedar
-- en valores anteriores al MAX(id) real, causando duplicate key violations.
-- Esta función detecta y corrige el drift automáticamente.
-- =============================================================================

BEGIN;

-- Instalar la función (CREATE OR REPLACE es idempotente)
CREATE OR REPLACE FUNCTION fix_all_sequences()
RETURNS TABLE(tabla TEXT, seq_anterior BIGINT, seq_nuevo BIGINT)
LANGUAGE plpgsql
AS $$
DECLARE
    r RECORD;
    v_seq_name TEXT;
    v_max_id   BIGINT;
    v_curr_val BIGINT;
    v_new_val  BIGINT;
BEGIN
    -- Recorrer todas las tablas que tienen columna 'id' con secuencia asociada
    FOR r IN
        SELECT
            t.table_name,
            pg_get_serial_sequence(t.table_name, 'id') AS sequence_name
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON c.table_name = t.table_name
            AND c.table_schema = t.table_schema
            AND c.column_name = 'id'
        WHERE t.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND pg_get_serial_sequence(t.table_name, 'id') IS NOT NULL
        ORDER BY t.table_name
    LOOP
        v_seq_name := r.sequence_name;

        -- Obtener MAX(id) actual de la tabla (NULL si está vacía)
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM %I', r.table_name)
            INTO v_max_id;

        -- Obtener el last_value de la secuencia
        SELECT COALESCE(last_value, 0)
          INTO v_curr_val
          FROM pg_sequences
         WHERE sequencename = split_part(v_seq_name, '.', 2)
           AND schemaname = 'public';

        IF v_curr_val IS NULL THEN
            v_curr_val := 0;
        END IF;

        -- El próximo valor correcto es MAX(id) + 1 (mínimo 1)
        v_new_val := GREATEST(v_max_id + 1, 1);

        -- Solo corregir si hay drift (secuencia retrasada respecto a los datos)
        IF v_curr_val < v_max_id THEN
            -- setval(..., v_new_val - 1, true) → el próximo nextval() devuelve v_new_val
            PERFORM setval(v_seq_name, v_new_val - 1, true);

            -- Reportar la corrección
            tabla       := r.table_name;
            seq_anterior := v_curr_val;
            seq_nuevo    := v_new_val - 1;  -- last_value que quedó en la secuencia
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$;

-- Registrar migración
INSERT INTO schema_version (version, description)
VALUES (37, 'fix_all_sequences function for post-sync sequence repair')
ON CONFLICT (version) DO NOTHING;

COMMIT;
