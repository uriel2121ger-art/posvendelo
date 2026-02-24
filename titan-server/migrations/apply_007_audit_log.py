#!/usr/bin/env python3
"""
Migration script to create audit_log table
Run this once to set up audit logging
"""

import sqlite3
import sys
from pathlib import Path

# Whitelist de índices permitidos para audit_log (prevención SQL injection)
ALLOWED_AUDIT_INDEX_NAMES = {
    'idx_audit_timestamp',
    'idx_audit_user',
    'idx_audit_action',
    'idx_audit_entity',
    'idx_audit_turn',
    'idx_audit_success',
    'idx_audit_composite',
}

ALLOWED_AUDIT_INDEX_COLUMNS = {
    'timestamp DESC',
    'user_id',
    'action',
    'entity_type, entity_id',
    'turn_id',
    'success',
    'timestamp DESC, user_id, action',
}


def validate_index_definition(idx_name: str, idx_cols: str) -> tuple[str, str]:
    """Valida que el índice esté en la whitelist permitida."""
    if idx_name not in ALLOWED_AUDIT_INDEX_NAMES:
        raise ValueError(f"Nombre de índice no permitido: {idx_name}")
    if idx_cols not in ALLOWED_AUDIT_INDEX_COLUMNS:
        raise ValueError(f"Columnas de índice no permitidas: {idx_cols}")
    return idx_name, idx_cols


# Get database path
db_path = Path(__file__).parent.parent / "databases" / "pos.db"

if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    sys.exit(1)

print(f"Creating audit_log table in {db_path}...")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # Create audit_log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id BIGSERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
        user_id INTEGER,
        username TEXT,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        entity_name TEXT,
        old_value TEXT,
        new_value TEXT,
        ip_address TEXT,
        turn_id INTEGER,
        branch_id INTEGER,
        success BOOLEAN DEFAULT TRUE,  -- FIX 2026-02-01: PostgreSQL
        error_message TEXT,
        details TEXT
    )
    """)
    
    # Create indexes
    indexes = [
        ("idx_audit_timestamp", "timestamp DESC"),
        ("idx_audit_user", "user_id"),
        ("idx_audit_action", "action"),
        ("idx_audit_entity", "entity_type, entity_id"),
        ("idx_audit_turn", "turn_id"),
        ("idx_audit_success", "success"),
        ("idx_audit_composite", "timestamp DESC, user_id, action")
    ]
    
    for idx_name, idx_cols in indexes:
        # Validar contra whitelist antes de ejecutar
        validated_name, validated_cols = validate_index_definition(idx_name, idx_cols)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {validated_name} ON audit_log({validated_cols})")
    
    conn.commit()
    
    # Verify
    # PostgreSQL: Usar information_schema en lugar de sqlite_master
    # Nota: Este script es legacy para SQLite, para PostgreSQL usar migrations/007_audit_log.sql
    try:
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='audit_log'")
        table_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_audit%'")
        index_count = cursor.fetchone()[0]
    # FIX 2026-02-01: Cambiar bare except a except Exception
    except Exception:
        # PostgreSQL fallback
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='audit_log'")
        table_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM information_schema.indexes WHERE index_name LIKE 'idx_audit%'")
        index_count = cursor.fetchone()[0]
    
    print(f"✅ Migration successful!")
    print(f"   - audit_log table: {'created' if table_count else 'already exists'}")
    print(f"   - Indexes: {index_count} created/verified")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    conn.rollback()
    sys.exit(1)
finally:
    conn.close()
