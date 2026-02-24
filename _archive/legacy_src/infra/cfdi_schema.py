"""
Create CFDI invoices table in database
"""

CFDIS_TABLE = """
CREATE TABLE IF NOT EXISTS cfdis (
    id BIGSERIAL PRIMARY KEY,
    sale_id INTEGER UNIQUE,
    uuid TEXT UNIQUE,
    folio INTEGER,
    serie TEXT,
    rfc_receptor TEXT,
    nombre_receptor TEXT,
    regimen_receptor TEXT,
    uso_cfdi TEXT DEFAULT 'G03',
    xml_original TEXT,
    xml_timbrado TEXT,
    pdf_path TEXT,
    fecha_emision TEXT,
    fecha_timbrado TEXT,
    estado TEXT DEFAULT 'vigente',
    motivo_cancelacion TEXT,
    fecha_cancelacion TEXT,
    total DOUBLE PRECISION,
    subtotal DOUBLE PRECISION,
    impuestos DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (sale_id) REFERENCES sales(id)
);

CREATE INDEX IF NOT EXISTS idx_cfdis_sale ON cfdis(sale_id);
CREATE INDEX IF NOT EXISTS idx_cfdis_uuid ON cfdis(uuid);
CREATE INDEX IF NOT EXISTS idx_cfdis_estado ON cfdis(estado);
"""

def add_cfdis_table(conn):
    """Add CFDIs table to database."""
    cursor = conn.cursor()
    try:
        for statement in CFDIS_TABLE.strip().split(';'):
            if statement.strip():
                cursor.execute(statement)
        conn.commit()
        print("✅ cfdis table and indexes created")
    finally:
        cursor.close()

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
            add_cfdis_table(conn)
        finally:
            conn.close()
    except ImportError:
        print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        sys.exit(1)
