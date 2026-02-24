"""
Sync Helpers - Utilidades para sincronización con metadata automática

Proporciona funciones helper para actualizar registros con metadata de sync
(updated_at, sync_version, last_modified_by) automáticamente.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import logging

from app.utils.sql_validators import (
    validate_table_name,
    validate_column_name,
    is_valid_sql_identifier,
    VALID_TABLE_NAMES,
)

logger = logging.getLogger(__name__)


def prepare_sync_update(
    core,
    table_name: str,
    record_id: int,
    updates: Dict[str, Any],
    skip_sync_version: bool = False) -> Tuple[str, tuple]:
    """
    Prepara UPDATE con metadata de sincronización automática.
    
    Agrega automáticamente:
    - updated_at: timestamp actual
    - last_modified_by: identificador del terminal
    - sync_version: se incrementa automáticamente por trigger (si no se especifica manualmente)
    
    Args:
        core: POSCore instance (debe tener método get_terminal_identifier())
        table_name: Nombre de la tabla
        record_id: ID del registro a actualizar
        updates: Diccionario con campos a actualizar
        skip_sync_version: Si True, no incluye sync_version (ya lo hace el trigger)
    
    Returns:
        (query, values) tuple para ejecutar con db.execute_write()
    
    Example:
        # Antes (manual):
        UPDATE products SET price=%s, name=%s, updated_at=NOW(), 
                           sync_version=sync_version+1, last_modified_by='PC2' WHERE id=%s
        
        # Después (automático):
        query, values = prepare_sync_update(
            core, "products", product_id,
            {"price": 18.00, "name": "Coca Cola"}
        )
        core.db.execute_write(query, values)
    """
    # Crear copia para no modificar el original
    sync_updates = updates.copy()
    
    # Convertir is_favorite de boolean a integer si existe
    if "is_favorite" in sync_updates and isinstance(sync_updates["is_favorite"], bool):
        sync_updates["is_favorite"] = 1 if sync_updates["is_favorite"] else 0
    
    # Agregar metadata automáticamente
    sync_updates["updated_at"] = datetime.now().isoformat()
    sync_updates["last_modified_by"] = core.get_terminal_identifier()
    
    # FIX 2026-02-01: Eliminado bloque if/pass vacío.
    # sync_version se incrementa automáticamente por trigger de BD.
    # Si se especifica manualmente en updates, se respeta (ya está en sync_updates).

    # SECURITY: Validate table_name against whitelist
    validated_table = validate_table_name(table_name)

    # SECURITY: Validate all column names
    for col in sync_updates.keys():
        if not is_valid_sql_identifier(col):
            raise ValueError(f"Invalid column name: {col}")

    # Construir query
    set_clause = ", ".join([f"{col} = %s" for col in sync_updates.keys()])
    values = list(sync_updates.values())
    values.append(record_id)

    query = f"UPDATE {validated_table} SET {set_clause} WHERE id = %s"
    return (query, tuple(values))


def prepare_sync_update_by_sku(
    core,
    table_name: str,
    sku: str,
    updates: Dict[str, Any],
    skip_sync_version: bool = False
) -> Tuple[str, tuple]:
    """
    Prepara UPDATE con metadata de sincronización usando SKU (o columna única).
    
    Similar a prepare_sync_update pero usa SKU en lugar de ID.
    
    Args:
        core: POSCore instance
        table_name: Nombre de la tabla
        sku: SKU del producto (o valor de columna única)
        updates: Diccionario con campos a actualizar
        skip_sync_version: Si True, no incluye sync_version
    
    Returns:
        (query, values) tuple para ejecutar
    """
    sync_updates = updates.copy()
    
    # Convertir is_favorite de boolean a integer si existe
    if "is_favorite" in sync_updates and isinstance(sync_updates["is_favorite"], bool):
        sync_updates["is_favorite"] = 1 if sync_updates["is_favorite"] else 0
    
    # Agregar metadata automáticamente
    sync_updates["updated_at"] = datetime.now().isoformat()
    sync_updates["last_modified_by"] = core.get_terminal_identifier()
    
    # SECURITY: Validate table_name against whitelist
    validated_table = validate_table_name(table_name)

    # SECURITY: Validate all column names
    for col in sync_updates.keys():
        if not is_valid_sql_identifier(col):
            raise ValueError(f"Invalid column name: {col}")

    # Construir query usando SKU
    set_clause = ", ".join([f"{col} = %s" for col in sync_updates.keys()])
    values = list(sync_updates.values())
    values.append(sku)

    query = f"UPDATE {validated_table} SET {set_clause} WHERE sku = %s"
    return (query, tuple(values))


def prepare_sync_insert(
    core,
    table_name: str,
    record: Dict[str, Any],
    include_sync_metadata: bool = True
) -> Tuple[str, tuple]:
    """
    Prepara INSERT con metadata de sincronización automática.
    
    Args:
        core: POSCore instance
        table_name: Nombre de la tabla
        record: Diccionario con campos del registro
        include_sync_metadata: Si True, agrega updated_at y last_modified_by
    
    Returns:
        (query, values) tuple para ejecutar
    """
    sync_record = record.copy()
    
    # Convertir is_favorite de boolean a integer si existe
    if "is_favorite" in sync_record and isinstance(sync_record["is_favorite"], bool):
        sync_record["is_favorite"] = 1 if sync_record["is_favorite"] else 0
    
    if include_sync_metadata:
        sync_record["updated_at"] = datetime.now().isoformat()
        sync_record["last_modified_by"] = core.get_terminal_identifier()
        # sync_version inicia en 0 (default en migración)
        if "sync_version" not in sync_record:
            sync_record["sync_version"] = 0
    
    # SECURITY: Validate table_name against whitelist
    validated_table = validate_table_name(table_name)

    # SECURITY: Validate all column names
    columns = list(sync_record.keys())
    for col in columns:
        if not is_valid_sql_identifier(col):
            raise ValueError(f"Invalid column name: {col}")

    # Construir query (PostgreSQL usa %s)
    placeholders = ", ".join(["%s" for _ in columns])
    values = list(sync_record.values())

    query = f"INSERT INTO {validated_table} ({', '.join(columns)}) VALUES ({placeholders})"
    return (query, tuple(values))


def validate_sync_metadata(record: dict, table_name: str, strict: bool = False) -> Tuple[bool, str]:
    """
    Valida que el registro tenga metadata necesaria para sync.
    
    Args:
        record: Registro a validar
        table_name: Nombre de la tabla
        strict: Si True, rechaza registros sin metadata (para tablas críticas)
    
    Returns:
        (is_valid, error_message)
    """
    # Para tablas críticas, requerir metadata
    critical_tables = ["products", "customers", "employees"]
    
    if table_name in critical_tables or strict:
        if not record.get("updated_at"):
            return (False, f"Missing updated_at for {table_name}")
        
        if record.get("sync_version") is None:
            return (False, f"Missing sync_version for {table_name}")
    
    return (True, "")


# =============================================================================
# SYNC CHECKPOINTS - Para sincronización incremental
# =============================================================================

def get_sync_checkpoint(core, table_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el checkpoint de sincronización para una tabla.
    
    Args:
        core: POSCore instance
        table_name: Nombre de la tabla
    
    Returns:
        Dict con checkpoint o None si no existe
    """
    try:
        rows = core.db.execute_query(
            "SELECT * FROM sync_checkpoints WHERE table_name = %s",
            (table_name,)
        )
        # FIX 2026-02-01: Validar rows con len() antes de acceder a [0]
        if rows and len(rows) > 0:
            return dict(rows[0])
        return None
    except Exception as e:
        logger.warning(f"Error getting sync checkpoint for {table_name}: {e}")
        return None


def update_sync_checkpoint(
    core,
    table_name: str,
    last_sync_version: int = None,
    last_sync_timestamp: str = None,
    success: bool = True,
    error: str = None
) -> bool:
    """
    Actualiza el checkpoint de sincronización para una tabla.
    
    Args:
        core: POSCore instance
        table_name: Nombre de la tabla
        last_sync_version: Última versión sincronizada
        last_sync_timestamp: Último timestamp sincronizado
        success: Si la sync fue exitosa
        error: Mensaje de error si falló
    
    Returns:
        True si se actualizó correctamente
    """
    try:
        from datetime import datetime
        
        checkpoint = get_sync_checkpoint(core, table_name)
        
        if checkpoint:
            # Actualizar existente
            updates = []
            values = []
            
            if last_sync_version is not None:
                updates.append("last_sync_version = %s")
                values.append(last_sync_version)
            
            if last_sync_timestamp:
                updates.append("last_sync_timestamp = %s")
                values.append(last_sync_timestamp)
            
            updates.append("last_sync_success = %s")
            values.append(1 if success else 0)
            
            if error:
                updates.append("last_error = %s")
                values.append(error)
            else:
                updates.append("last_error = NULL")
            
            updates.append("sync_count = sync_count + 1")
            updates.append("updated_at = %s")
            values.append(datetime.now().isoformat())
            
            values.append(table_name)
            
            query = f"""
                UPDATE sync_checkpoints 
                SET {', '.join(updates)}
                WHERE table_name = %s
            """
            core.db.execute_write(query, tuple(values))
        else:
            # Crear nuevo checkpoint
            query = """
                INSERT INTO sync_checkpoints 
                (table_name, last_sync_version, last_sync_timestamp, 
                 last_sync_success, sync_count, last_error, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            core.db.execute_write(query, (
                table_name,
                last_sync_version or 0,
                last_sync_timestamp or datetime.now().isoformat(),
                1 if success else 0,
                1,
                error,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
        
        return True
    except Exception as e:
        logger.error(f"Error updating sync checkpoint for {table_name}: {e}")
        return False


def get_unsynced_records(
    core,
    table_name: str,
    id_column: str = "id",
    limit: int = 1000
) -> list:
    """
    Obtiene registros no sincronizados usando checkpoint incremental.

    Args:
        core: POSCore instance
        table_name: Nombre de la tabla
        id_column: Columna de ID
        limit: Límite de registros

    Returns:
        Lista de registros no sincronizados
    """
    # SECURITY: Validate table_name against whitelist
    validated_table = validate_table_name(table_name)

    # SECURITY: Validate id_column format
    if not is_valid_sql_identifier(id_column):
        raise ValueError(f"Invalid id_column: {id_column}")

    # SECURITY: Enforce limit bounds
    limit = max(1, min(int(limit), 10000))

    checkpoint = get_sync_checkpoint(core, table_name)

    if not checkpoint:
        # Primera sync: obtener todos los registros recientes
        query = f"""
            SELECT * FROM {validated_table}
            WHERE updated_at > NOW() - INTERVAL '7 days'
            ORDER BY sync_version DESC, updated_at DESC
            LIMIT %s
        """
        return core.db.execute_query(query, (limit,))
    
    # Sync incremental: solo cambios desde último checkpoint
    last_version = checkpoint.get("last_sync_version", 0)
    last_timestamp = checkpoint.get("last_sync_timestamp")
    
    # Usar sync_version primero (más confiable)
    if last_version > 0:
        query = f"""
            SELECT * FROM {validated_table}
            WHERE sync_version > %s
            ORDER BY sync_version ASC, updated_at ASC
            LIMIT %s
        """
        return core.db.execute_query(query, (last_version, limit))
    
    # Fallback a timestamp si no hay sync_version
    if last_timestamp:
        query = f"""
            SELECT * FROM {validated_table}
            WHERE updated_at > %s
            ORDER BY updated_at ASC
            LIMIT %s
        """
        return core.db.execute_query(query, (last_timestamp, limit))

    # Sin checkpoint válido: obtener todos recientes
    query = f"""
        SELECT * FROM {validated_table}
        WHERE updated_at > NOW() - INTERVAL '7 days'
        ORDER BY sync_version DESC, updated_at DESC
        LIMIT %s
    """
    return core.db.execute_query(query, (limit,))


def reset_sync_checkpoint(core, table_name: str) -> bool:
    """
    Resetea el checkpoint de sincronización (fuerza full sync).
    
    Args:
        core: POSCore instance
        table_name: Nombre de la tabla
    
    Returns:
        True si se reseteó correctamente
    """
    try:
        core.db.execute_write(
            "DELETE FROM sync_checkpoints WHERE table_name = %s",
            (table_name,)
        )
        logger.info(f"Reset sync checkpoint for {table_name}")
        return True
    except Exception as e:
        logger.error(f"Error resetting sync checkpoint for {table_name}: {e}")
        return False


# =============================================================================
# COMPRESIÓN Y PAGINACIÓN
# =============================================================================

def compress_payload(data: Any) -> Tuple[bytes, bool]:
    """
    Comprime un payload si es grande.
    
    Args:
        data: Datos a comprimir (dict, list, etc.)
    
    Returns:
        (compressed_data, is_compressed) tuple
    """
    try:
        import json
        import gzip
        from app.config.sync_config import should_compress
        
        payload = json.dumps(data).encode('utf-8')
        
        if should_compress(len(payload)):
            compressed = gzip.compress(payload)
            logger.debug(f"Compressed payload: {len(payload)} → {len(compressed)} bytes ({100 - (len(compressed)/len(payload)*100):.1f}% reduction)")
            return compressed, True
        else:
            return payload, False
    except Exception as e:
        logger.warning(f"Error compressing payload: {e}")
        # Fallback: retornar sin comprimir
        import json
        return json.dumps(data).encode('utf-8'), False


def decompress_payload(compressed_data: bytes, is_compressed: bool) -> Any:
    """
    Descomprime un payload si está comprimido.
    
    Args:
        compressed_data: Datos comprimidos
        is_compressed: Si True, descomprime con gzip
    
    Returns:
        Datos descomprimidos (dict, list, etc.)
    """
    try:
        import json
        import gzip
        
        if is_compressed:
            decompressed = gzip.decompress(compressed_data)
            return json.loads(decompressed.decode('utf-8'))
        else:
            return json.loads(compressed_data.decode('utf-8'))
    except Exception as e:
        logger.error(f"Error decompressing payload: {e}")
        raise RuntimeError(f"Error decompressing payload: {e}") from e


def paginate_records(records: list, batch_size: int) -> list:
    """
    Divide registros en lotes (paginación).
    
    Args:
        records: Lista de registros
        batch_size: Tamaño de cada lote
    
    Returns:
        Lista de lotes
    """
    batches = []
    for i in range(0, len(records), batch_size):
        batches.append(records[i:i + batch_size])
    return batches
