-- =====================================================
-- FIX: Agregar constraints faltantes para ON CONFLICT
-- Ejecutar en la base de datos PostgreSQL de Lupita
-- =====================================================

-- 1. sale_items: UNIQUE (sale_id, product_id)
-- Necesario para: ON CONFLICT (sale_id, product_id) DO NOTHING
CREATE UNIQUE INDEX IF NOT EXISTS idx_sale_items_unique_sale_product
ON sale_items(sale_id, product_id);

-- 2. Agregar columna synced si no existe (para sincronización)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'sale_items' AND column_name = 'synced'
    ) THEN
        ALTER TABLE sale_items ADD COLUMN synced INTEGER DEFAULT 0;
    END IF;
END $$;

-- 3. sales: UNIQUE en uuid (si no existe)
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_uuid
ON sales(uuid) WHERE uuid IS NOT NULL;

-- 4. Verificación
SELECT
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('sales', 'sale_items')
ORDER BY tablename, indexname;
