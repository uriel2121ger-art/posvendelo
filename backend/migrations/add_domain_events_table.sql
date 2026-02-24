-- TITAN POS - Domain Events Table (Phase 2: Outbox Pattern)
-- Run this migration to enable persistent domain events.

CREATE TABLE IF NOT EXISTS domain_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT,
    data JSONB NOT NULL DEFAULT '{}',
    source_module TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for polling unprocessed events
CREATE INDEX IF NOT EXISTS idx_domain_events_unprocessed
    ON domain_events (processed, created_at)
    WHERE processed = FALSE;

-- Index for aggregate event history (event sourcing)
CREATE INDEX IF NOT EXISTS idx_domain_events_aggregate
    ON domain_events (aggregate_type, aggregate_id, timestamp);

-- Index for event type filtering
CREATE INDEX IF NOT EXISTS idx_domain_events_type
    ON domain_events (event_type, timestamp);

COMMENT ON TABLE domain_events IS 'Outbox pattern: domain events persisted atomically with business data changes';
COMMENT ON COLUMN domain_events.event_id IS 'UUID unique per event';
COMMENT ON COLUMN domain_events.aggregate_type IS 'Type of business entity (sale, product, customer)';
COMMENT ON COLUMN domain_events.aggregate_id IS 'ID of the specific entity instance';
COMMENT ON COLUMN domain_events.data IS 'Event payload as JSONB';
COMMENT ON COLUMN domain_events.source_module IS 'Module that produced the event';
COMMENT ON COLUMN domain_events.processed IS 'Whether all handlers have processed this event';
COMMENT ON COLUMN domain_events.retry_count IS 'Number of failed processing attempts';
