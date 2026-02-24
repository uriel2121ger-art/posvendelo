-- Migración 001: Tabla de control de versiones de schema
-- Esta tabla trackea qué migraciones se han aplicado

CREATE TABLE IF NOT EXISTS schema_version (
    id BIGSERIAL PRIMARY KEY,
    version INTEGER NOT NULL UNIQUE,
    description TEXT,
    applied_at TIMESTAMP DEFAULT NOW()
);

-- Insertar versión inicial
INSERT INTO schema_version (version, description) 
VALUES (1, 'Schema inicial v2.0.0')
ON CONFLICT (version) DO NOTHING;
