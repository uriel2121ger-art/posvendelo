ALTER TABLE audit_log
ALTER COLUMN success DROP DEFAULT;

ALTER TABLE audit_log
ALTER COLUMN success TYPE BOOLEAN
USING CASE
    WHEN success IS NULL THEN TRUE
    WHEN success::text IN ('t', 'true', 'TRUE', '1') THEN TRUE
    ELSE FALSE
END;

ALTER TABLE audit_log
ALTER COLUMN success SET DEFAULT TRUE;

INSERT INTO schema_version(version, description)
VALUES (44, 'audit_log success boolean type')
ON CONFLICT DO NOTHING;
