"""
Add fiscal_config table to database schema
"""

FISCAL_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS fiscal_config (
    id BIGSERIAL PRIMARY KEY,
    branch_id INTEGER DEFAULT 1,
    
    -- Emisor info
    rfc_emisor TEXT,
    razon_social_emisor TEXT,
    regimen_fiscal TEXT,
    lugar_expedicion TEXT,
    
    -- CSD Certificates  
    csd_cert_path TEXT,
    csd_key_path TEXT,
    csd_key_password_encrypted TEXT,
    csd_cert_serial TEXT,
    csd_cert_valid_from TEXT,
    csd_cert_valid_to TEXT,
    
    -- PAC Provider
    pac_provider TEXT DEFAULT 'custom',
    pac_base_url TEXT,
    pac_user TEXT,
    pac_password_encrypted TEXT,
    pac_mode TEXT DEFAULT 'test',
    
    -- Invoice Series
    serie_factura TEXT DEFAULT 'F',
    folio_actual INTEGER DEFAULT 1,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(branch_id)
);
"""

def add_fiscal_config_table(conn):
    """Add fiscal_config table to existing database."""
    cursor = conn.cursor()
    try:
        cursor.execute(FISCAL_CONFIG_TABLE)
        conn.commit()
        print("✅ fiscal_config table created")
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
            add_fiscal_config_table(conn)
        finally:
            conn.close()
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        sys.exit(1)
