-- Migration 018: Cola persistente de sincronización (B.4)
-- Permite que los ítems encolados no se pierdan al reiniciar la aplicación.
-- Idempotente: safe to run multiple times.

-- PostgreSQL
CREATE TABLE IF NOT EXISTS sync_queue (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    record_id BIGINT NOT NULL,
    payload TEXT,
    node_id VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    synced BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    last_error VARCHAR(500)
);

CREATE INDEX IF NOT EXISTS idx_sync_queue_synced_created
ON sync_queue (synced, created_at)
WHERE synced = FALSE;

INSERT INTO schema_version (version, description, applied_at)
VALUES (18, 'Persistent synchronization queue', NOW())
ON CONFLICT (version) DO NOTHING;

-- SQLite (si se aplica en entorno SQLite)
-- CREATE TABLE IF NOT EXISTS sync_queue (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     table_name TEXT NOT NULL,
--     record_id INTEGER NOT NULL,
--     payload TEXT,
--     node_id TEXT,
--     created_at TEXT DEFAULT (datetime('now')),
--     synced INTEGER DEFAULT 0,
--     processed_at TEXT,
--     retry_count INTEGER DEFAULT 0,
--     last_error TEXT
-- );
-- CREATE INDEX IF NOT EXISTS idx_sync_queue_synced_created ON sync_queue (synced, created_at) WHERE synced = 0;
