-- Migration 041: Drop duplicate customer columns
-- Keep: points, tier, city, state, postal_code
-- Drop: loyalty_points, loyalty_level, ciudad, estado, codigo_postal

BEGIN;

-- Safety copy: preserve data from old columns into new ones where new ones are NULL
UPDATE customers SET city = ciudad WHERE city IS NULL AND ciudad IS NOT NULL;
UPDATE customers SET state = estado WHERE state IS NULL AND estado IS NOT NULL;
UPDATE customers SET postal_code = codigo_postal WHERE postal_code IS NULL AND codigo_postal IS NOT NULL;

-- Drop duplicate columns
ALTER TABLE customers DROP COLUMN IF EXISTS loyalty_points;
ALTER TABLE customers DROP COLUMN IF EXISTS loyalty_level;
ALTER TABLE customers DROP COLUMN IF EXISTS ciudad;
ALTER TABLE customers DROP COLUMN IF EXISTS estado;
ALTER TABLE customers DROP COLUMN IF EXISTS codigo_postal;

-- Register migration
INSERT INTO schema_version(version) VALUES (41) ON CONFLICT DO NOTHING;

COMMIT;
