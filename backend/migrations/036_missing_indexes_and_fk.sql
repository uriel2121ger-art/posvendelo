-- Migration 036: Missing indexes in high-activity tables + FK constraint
-- Audit date: 2026-03-03
-- Beneficia: inventory_movements, cash_movements, cash_expenses, customers, users

BEGIN;

-- ============================================================
-- 1. inventory_movements — timestamp faltante
--    Omitido: idx_inv_movements_product_id ya existe (mig 031)
-- ============================================================

-- Usado en: inventory/routes.py LIST con rango de fechas y exportes
CREATE INDEX IF NOT EXISTS idx_inv_movements_timestamp
    ON inventory_movements(timestamp);

-- ============================================================
-- 2. cash_movements — índice compuesto (turn_id, type)
--    Omitidos: idx_cash_movements_turn y idx_cash_movements_type
--    ya existen por separado; el compuesto cubre ambos de una sola vez.
--    Usado en: turns/routes.py close_turn() SUM filtrado por turn y tipo
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_cash_movements_turn_type
    ON cash_movements(turn_id, type);

-- ============================================================
-- 3. cash_expenses — sin ningún índice funcional (solo PK)
--    Usado en: turns/routes.py close_turn() SELECT WHERE turn_id
--              expenses/routes.py LIST con filtro de fecha
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_cash_expenses_turn
    ON cash_expenses(turn_id);

CREATE INDEX IF NOT EXISTS idx_cash_expenses_timestamp
    ON cash_expenses(timestamp);

-- ============================================================
-- 4. customers — índice funcional LOWER(TRIM(name))
--    Usado en: customers/routes.py create_customer() búsqueda duplicado
--    El trgm existente cubre LIKE fuzzy; este cubre igualdad exacta
--    normalizada sin importar mayúsculas ni espacios extremos.
--    WHERE is_active=1 para excluir clientes eliminados del lookup.
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_customers_name_lower
    ON customers(LOWER(TRIM(name)))
    WHERE is_active = 1;

-- ============================================================
-- 5. users — índice compuesto (role, is_active) con filtro PIN
--    Usado en: sales/routes.py verify PIN de cancelación
--              turns/routes.py verify PIN de cierre
--    Cubre: WHERE role IN ('admin','manager','owner') AND is_active=1
--            AND pin_hash IS NOT NULL
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_users_role_active
    ON users(role, is_active)
    WHERE is_active = 1 AND pin_hash IS NOT NULL;

-- ============================================================
-- 6. FK constraint: inventory_movements.product_id → products(id)
--    Verificado: no existe ninguna FK en inventory_movements (solo PK)
--    product_id es NOT NULL → ON DELETE RESTRICT previene borrar productos
--    con movimientos registrados (preserva integridad histórica).
--    NOT VALID + VALIDATE permite evitar lock de escritura en tabla grande.
-- ============================================================

ALTER TABLE inventory_movements
    ADD CONSTRAINT fk_inv_movements_product
    FOREIGN KEY (product_id) REFERENCES products(id)
    ON DELETE RESTRICT
    NOT VALID;

-- Validar la FK sin bloquear escrituras (PostgreSQL 12+)
ALTER TABLE inventory_movements
    VALIDATE CONSTRAINT fk_inv_movements_product;

-- ============================================================

INSERT INTO schema_version (version, description, applied_at)
VALUES (36, 'missing_indexes_and_fk_inventory_movements', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;
