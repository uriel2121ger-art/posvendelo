"""
Query Converter - Convierte queries a sintaxis PostgreSQL
(Nota: Sistema usa solo PostgreSQL, pero mantiene conversión para compatibilidad)
"""

import re

# SECURITY: Whitelist of valid table names for INSERT OR IGNORE/REPLACE conversions
VALID_TABLE_NAMES_FOR_CONVERSION = frozenset([
    'secuencias', 'branches', 'loyalty_rules', 'role_permissions',
    'config', 'app_config', 'emitters', 'categories', 'products',
    'customers', 'users', 'employees', 'suppliers', 'promotions',
    'gift_cards', 'bin_locations', 'branch_ticket_config',
])


def _validate_table_name_format(table_name: str) -> bool:
    """Validate that table name has safe format (alphanumeric + underscore)."""
    if not table_name:
        return False
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name))

def convert_sqlite_to_postgresql(query: str) -> str:
    """
    Convierte sintaxis SQLite a PostgreSQL.
    
    Args:
        query: Query SQL con sintaxis SQLite
        
    Returns:
        Query SQL con sintaxis PostgreSQL
    """
    converted = query
    
    # 0. Convertir INSERT OR IGNORE primero (antes de otros reemplazos)
    if "INSERT OR IGNORE" in converted.upper():
        converted = convert_insert_or_ignore(converted)
    
    # 0.5. Convertir INSERT OR REPLACE
    if "INSERT OR REPLACE" in converted.upper():
        converted = convert_insert_or_replace(converted)
    
    # 1. Reemplazar ? por %s (parámetros)
    converted = converted.replace("%s", "%s")
    
    # 2. Reemplazar funciones SQLite por PostgreSQL
    conversions = [
        # Funciones de fecha/hora
        (r"datetime\('now',\s*'localtime'\)", "NOW()"),
        (r"datetime\('now'\)", "NOW()"),
        (r"strftime\('%Y-%m-%d',\s*'now'\)", "CURRENT_DATE::TEXT"),
        (r"strftime\('%Y-%m-%d\s+%H:%M:%S',\s*'now'\)", "NOW()::TEXT"),
        
        # Funciones de NULL
        (r"IFNULL\(", "COALESCE("),
        
        # Tipos de datos (solo en CREATE TABLE, no en queries)
        # Estos se manejan en conversión de schema, no aquí
        
        # Sintaxis de transacciones
        (r"BEGIN\s+IMMEDIATE", "BEGIN"),
        (r"BEGIN\s+EXCLUSIVE", "BEGIN"),
        
        # Funciones específicas
        (r"last_insert_rowid\(\)", "lastval()"),
        
        # PRAGMA statements (remover o convertir)
        # Estos se manejan en métodos específicos, no en queries normales
    ]
    
    for pattern, replacement in conversions:
        converted = re.sub(pattern, replacement, converted, flags=re.IGNORECASE)
    
    return converted

def convert_pragma_table_info(table_name: str) -> str:
    """
    Convierte PRAGMA table_info a query de information_schema.
    
    Args:
        table_name: Nombre de la tabla
        
    Returns:
        Query PostgreSQL equivalente
    """
    return f"""
        SELECT 
            column_name as name,
            data_type as type,
            is_nullable as notnull,
            column_default as dflt_value,
            CASE WHEN is_nullable = 'NO' THEN 0 ELSE 1 END as notnull
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = %s
        ORDER BY ordinal_position
    """

def convert_sqlite_master() -> str:
    """
    Convierte query de sqlite_master a information_schema.
    
    Returns:
        Query PostgreSQL equivalente
    """
    return """
        SELECT table_name as name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """

def convert_insert_returning(query: str, table_name: str = None, exclude_tables: list = None) -> str:
    """
    Agrega RETURNING id a INSERT si no lo tiene.
    
    Args:
        query: Query INSERT
        table_name: Nombre de tabla (si no se puede extraer de query)
        exclude_tables: Lista de nombres de tablas para excluir (no agregar RETURNING)
        
    Returns:
        Query con RETURNING agregado
    """
    if "RETURNING" in query.upper():
        return query
    
    # No agregar RETURNING si tiene ON CONFLICT (puede causar problemas)
    if "ON CONFLICT" in query.upper():
        return query
    
    # Intentar extraer nombre de tabla
    if not table_name:
        match = re.search(r"INSERT\s+INTO\s+(\w+)", query, re.IGNORECASE)
        if match:
            table_name = match.group(1)
    
    # CRITICAL FIX: No agregar RETURNING id para tablas que no tienen columna id
    # (ej: branch_ticket_config usa branch_id como PRIMARY KEY)
    exclude_tables = exclude_tables or []
    if table_name and table_name.lower() in [t.lower() for t in exclude_tables]:
        return query
    
    if table_name:
        # Agregar RETURNING antes del punto y coma o al final
        if query.rstrip().endswith(';'):
            return query.rstrip()[:-1] + f" RETURNING id;"
        else:
            return query + f" RETURNING id"
    
    return query

def convert_insert_or_ignore(query: str) -> str:
    """
    Convierte INSERT OR IGNORE a INSERT ... ON CONFLICT DO NOTHING.

    Args:
        query: Query con INSERT OR IGNORE

    Returns:
        Query convertida a PostgreSQL
    """
    if "INSERT OR IGNORE" not in query.upper():
        return query

    # Remover "OR IGNORE"
    converted = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", query, flags=re.IGNORECASE)

    # Intentar extraer información para ON CONFLICT
    # Buscar tabla y columnas
    pattern = r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)"
    match = re.search(pattern, converted, re.IGNORECASE)

    if match:
        table = match.group(1)
        columns = match.group(2).strip()

        # SECURITY: Validate table name format
        if not _validate_table_name_format(table):
            raise ValueError(f"Invalid table name format in INSERT OR IGNORE: {table}")

        # Intentar determinar columna de conflicto
        # Para tablas comunes, usar la columna UNIQUE o PRIMARY KEY conocida
        conflict_cols = {
            'secuencias': '(serie, terminal_id)',
            'branches': '(id)',
            'loyalty_rules': '(regla_id)',
            'role_permissions': '(role, permission)',
        }

        if table.lower() in conflict_cols:
            conflict = conflict_cols[table.lower()]
        else:
            # Por defecto, usar la primera columna
            first_col = columns.split(',')[0].strip()
            # SECURITY: Validate column name format
            if not _validate_table_name_format(first_col):
                raise ValueError(f"Invalid column name format: {first_col}")
            conflict = f"({first_col})"

        # Agregar ON CONFLICT antes del punto y coma o al final
        if converted.rstrip().endswith(';'):
            converted = converted.rstrip()[:-1] + f" ON CONFLICT {conflict} DO NOTHING;"
        else:
            converted = converted + f" ON CONFLICT {conflict} DO NOTHING"

    return converted

def convert_insert_or_replace(query: str, conflict_column: str = None) -> str:
    """
    Convierte INSERT OR REPLACE a INSERT ... ON CONFLICT DO UPDATE.

    Args:
        query: Query con INSERT OR REPLACE
        conflict_column: Columna de conflicto (si no se puede inferir)

    Returns:
        Query convertida a PostgreSQL
    """
    if "INSERT OR REPLACE" not in query.upper():
        return query

    # Extraer partes de la query
    # INSERT OR REPLACE INTO table (cols) VALUES (...)
    pattern = r"INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)"
    match = re.search(pattern, query, re.IGNORECASE)

    if match:
        table = match.group(1)
        columns = match.group(2).strip().split(',')
        columns = [col.strip() for col in columns]
        values = match.group(3).strip()

        # SECURITY: Validate table name format
        if not _validate_table_name_format(table):
            raise ValueError(f"Invalid table name format in INSERT OR REPLACE: {table}")

        # SECURITY: Validate all column names
        for col in columns:
            if not _validate_table_name_format(col):
                raise ValueError(f"Invalid column name format: {col}")

        # Determinar columna de conflicto
        if not conflict_column:
            # Intentar inferir: generalmente es 'id' o la primera columna
            if 'id' in columns:
                conflict_column = 'id'
            elif 'key' in columns:
                conflict_column = 'key'
            else:
                conflict_column = columns[0]

        # SECURITY: Validate conflict column
        if not _validate_table_name_format(conflict_column):
            raise ValueError(f"Invalid conflict column format: {conflict_column}")

        # Construir SET clause para UPDATE
        set_clauses = [f"{col} = EXCLUDED.{col}" for col in columns if col != conflict_column]
        set_clause = ", ".join(set_clauses) if set_clauses else f"{columns[0]} = EXCLUDED.{columns[0]}"

        # Convertir a ON CONFLICT
        converted = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values}) ON CONFLICT ({conflict_column}) DO UPDATE SET {set_clause}"
        return converted

    return query
