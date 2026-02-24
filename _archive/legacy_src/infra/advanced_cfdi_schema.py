"""
Additional database tables for advanced CFDI features
"""

CFDI_RELATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS cfdi_relations (
    id BIGSERIAL PRIMARY KEY,
    parent_uuid TEXT NOT NULL,
    related_uuid TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (parent_uuid) REFERENCES cfdis(uuid),
    FOREIGN KEY (related_uuid) REFERENCES cfdis(uuid)
);

CREATE INDEX IF NOT EXISTS idx_cfdi_relations_parent ON cfdi_relations(parent_uuid);
CREATE INDEX IF NOT EXISTS idx_cfdi_relations_related ON cfdi_relations(related_uuid);
"""

SALE_CFDI_RELATION_TABLE = """
CREATE TABLE IF NOT EXISTS sale_cfdi_relation (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL,
    cfdi_id INTEGER NOT NULL,
    is_global INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (sale_id) REFERENCES sales(id),
    FOREIGN KEY (cfdi_id) REFERENCES cfdis(id)
);

CREATE INDEX IF NOT EXISTS idx_sale_cfdi_sale ON sale_cfdi_relation(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_cfdi_cfdi ON sale_cfdi_relation(cfdi_id);
"""

def add_advanced_cfdi_tables(conn):
    """Add advanced CFDI tables to database."""
    cursor = conn.cursor()
    try:
        # CFDIrelations
        for statement in CFDI_RELATIONS_TABLE.strip().split(';'):
            if statement.strip():
                cursor.execute(statement)

        # Sale-CFDI relations
        for statement in SALE_CFDI_RELATION_TABLE.strip().split(';'):
            if statement.strip():
                cursor.execute(statement)

        conn.commit()
        print("✅ Advanced CFDI tables created")
    finally:
        cursor.close()  # CRITICAL FIX: Always close cursor

if __name__ == "__main__":
    from pathlib import Path
    import json
    import sys

    # PostgreSQL - Cargar configuracion
    config_path = Path(__file__).parent.parent.parent / "data" / "local_config.json"
    if not config_path.exists():
        print(f"❌ Config not found at: {config_path}")
        sys.exit(1)

    try:
        import psycopg2
        with open(config_path, 'r') as f:
            config = json.load(f)

        pg_config = config.get('postgresql', {})
        conn = psycopg2.connect(
            host=pg_config.get('host', 'localhost'),
            port=pg_config.get('port', 5432),
            database=pg_config.get('database', 'titan_pos'),
            user=pg_config.get('user', 'titan'),
            password=pg_config.get('password', '')
        )
        try:
            add_advanced_cfdi_tables(conn)
        finally:
            conn.close()
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        sys.exit(1)
