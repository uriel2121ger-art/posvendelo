"""
Generic client sync methods for all configured tables.

Provides automatic push/pull sync for all tables defined in sync_config.
"""

from typing import Any, Dict, List
import logging
import time

from app.utils.sync_config import BIDIRECTIONAL_SYNC_TABLES, PUSH_ONLY_TABLES, is_bidirectional
from app.utils.sql_validators import (
    validate_table_name,
    is_valid_sql_identifier,
    VALID_TABLE_NAMES,
)

logger = logging.getLogger(__name__)


def sync_all_tables_push(sync_client, pos_core) -> Dict[str, Any]:
    """
    Push all configured tables to server.

    Args:
        sync_client: MultiCajaClient instance
        pos_core: POSCore instance for database access

    Returns:
        Dictionary with sync results for each table
    """
    results = {}

    # Sync bidirectional tables
    for table_name, config in sorted(BIDIRECTIONAL_SYNC_TABLES.items(), key=lambda x: x[1].get("priority", 99)):
        try:
            data = get_table_data(pos_core, table_name, config)
            if data:
                success, msg, response = sync_client.sync_table(table_name, data)
                results[table_name] = {
                    "success": success,
                    "message": msg,
                    "count": len(data)
                }
                if success:
                    logger.info(f"📤 PUSH {table_name}: {len(data)} records")
        except Exception as e:
            logger.error(f"Error pushing {table_name}: {e}")
            results[table_name] = {"success": False, "error": str(e)}

    # Sync push-only tables
    for table_name, config in PUSH_ONLY_TABLES.items():
        try:
            data = get_table_data(pos_core, table_name, config)
            if data:
                success, msg, response = sync_client.sync_table(table_name, data)
                results[table_name] = {
                    "success": success,
                    "message": msg,
                    "count": len(data)
                }
                if success:
                    logger.info(f"📤 PUSH {table_name}: {len(data)} records")
        except Exception as e:
            logger.error(f"Error pushing {table_name}: {e}")
            results[table_name] = {"success": False, "error": str(e)}

    return results


def sync_all_tables_pull(sync_client, pos_core) -> Dict[str, Any]:
    """
    Pull all bidirectional tables from server and apply to local DB.

    Args:
        sync_client: MultiCajaClient instance
        pos_core: POSCore instance for database access

    Returns:
        Dictionary with sync results for each table
    """
    results = {}

    # Only pull bidirectional tables
    for table_name, config in sorted(BIDIRECTIONAL_SYNC_TABLES.items(), key=lambda x: x[1].get("priority", 99)):
        logger.debug(f"Starting pull for table: {table_name}")
        try:
            success, msg, data = sync_client.pull_table(table_name)
            logger.debug(f"pull_table result: table={table_name}, success={success}, count={len(data) if data else 0}")

            if success:
                # Success means the request was successful, even if data is empty
                # FIX 2026-01-31: Validar tipo de data antes de aplicar
                if data:
                    if not isinstance(data, list):
                        logger.error(f"PULL {table_name}: data is not a list! type={type(data).__name__}, value={str(data)[:100]}")
                        results[table_name] = {"success": False, "error": f"Invalid data type: {type(data).__name__}"}
                        continue
                    apply_table_data(pos_core, table_name, config, data)
                    results[table_name] = {
                        "success": True,
                        "count": len(data)
                    }
                    logger.info(f"📥 PULL {table_name}: {len(data)} records applied")
                else:
                    # Empty data is still a success - just means no records to sync
                    results[table_name] = {
                        "success": True,
                        "count": 0,
                        "message": "No records to sync"
                    }
                    logger.info(f"📥 PULL {table_name}: 0 records (no data to sync)")
            else:
                logger.debug(f"pull_table failed: table={table_name}, message={msg}")
                results[table_name] = {"success": False, "message": msg}
        except Exception as e:
            import traceback
            logger.error(f"Error pulling {table_name}: {e}")
            logger.error(f"Exception type: {type(e).__name__}, Traceback: {traceback.format_exc()[:500]}")
            results[table_name] = {"success": False, "error": str(e)}

    return results


def _is_valid_sql_identifier(name: str) -> bool:
    """Validate that a string is a safe SQL identifier (alphanumeric and underscores only)."""
    # Use centralized validator
    return is_valid_sql_identifier(name)


def get_table_data(pos_core, table_name: str, config: Dict) -> List[Dict[str, Any]]:
    """
    Get data from local database for a specific table.
    Filtra por synced = 0 si la tabla tiene ese campo.

    Args:
        pos_core: POSCore instance
        table_name: Name of table
        config: Table configuration

    Returns:
        List of records as dictionaries (solo no sincronizados si tiene campo synced)
    """
    try:
        columns = config["columns"]
        id_column = config["id_column"]
        # FIX 2026-01-31: Aumentar límite default y permitir 0 = sin límite
        limit = config.get("limit", 50000)  # Default 50k, antes era 5k

        # SECURITY: Validate table_name against whitelist (strictest validation)
        validated_table = validate_table_name(table_name)

        # Validate SQL identifiers to prevent injection
        if not _is_valid_sql_identifier(id_column):
            raise ValueError(f"Invalid id_column: {id_column}")
        for col in columns:
            if not _is_valid_sql_identifier(col):
                raise ValueError(f"Invalid column name: {col}")

        # Verificar si la tabla tiene columna 'synced'
        try:
            table_info = pos_core.db.get_table_info(table_name)
            has_synced = any(col[1] == "synced" for col in table_info)
        except Exception as e:
            logger.debug("Checking synced column existence: %s", e)
            has_synced = False

        # Construir query con filtro de synced si existe
        # SECURITY: table_name validated against whitelist, columns validated above
        # FIX 2026-01-31: Si limit es 0, no aplicar límite (sincronizar todo)
        if has_synced and "synced" in columns:
            base_query = f"SELECT {', '.join(columns)} FROM {validated_table} WHERE (synced = 0 OR synced IS NULL) ORDER BY {id_column} DESC"
        else:
            base_query = f"SELECT {', '.join(columns)} FROM {validated_table} ORDER BY {id_column} DESC"

        if limit and limit > 0:
            query = f"{base_query} LIMIT %s"
            rows = pos_core.db.execute_query(query, (limit,))
        else:
            # Sin límite - sincronizar todos los registros
            rows = pos_core.db.execute_query(base_query)

        data = []
        for row in rows:
            record = dict(row)
            data.append(record)

        return data
    except Exception as e:
        logger.error(f"Error getting {table_name} data: {e}")
        return []


def apply_table_data(pos_core, table_name: str, config: Dict, data: List[Dict[str, Any]]) -> None:
    """
    Apply data from server to local database.

    Args:
        pos_core: POSCore instance
        table_name: Name of table
        config: Table configuration
        data: List of records to apply
    """
    start_time = time.time()

    try:
        # FIX 2026-01-31: Validar que data sea una lista
        if not data:
            return

        if not isinstance(data, list):
            logger.error(f"apply_table_data: data is not a list! type={type(data).__name__}, value={str(data)[:100]}")
            raise TypeError(f"Expected list for {table_name} data, got {type(data).__name__}: {str(data)[:50]}")

        # SECURITY: Validate table_name against whitelist (strictest validation)
        validated_table = validate_table_name(table_name)

        logger.debug(f"apply_table_data started: table={validated_table}, records={len(data)}")

        updated = 0
        created = 0
        skipped = 0
        operations = []
        id_column = config["id_column"]
        columns = config["columns"]
        unique_columns = config.get("unique_columns", [])  # Columnas con restricción UNIQUE además de id

        # Validate column names
        if not _is_valid_sql_identifier(id_column):
            raise ValueError(f"Invalid id_column: {id_column}")
        for col in columns:
            if not _is_valid_sql_identifier(col):
                raise ValueError(f"Invalid column name: {col}")
        for col in unique_columns:
            if not _is_valid_sql_identifier(col):
                raise ValueError(f"Invalid unique column name: {col}")

        # B.6: Secuencias se identifican por (serie, terminal_id); aplicar MAX (GREATEST) para ultimo_numero
        if table_name == "secuencias":
            existing_sec = set()
            try:
                rows = pos_core.db.execute_query("SELECT serie, terminal_id FROM secuencias", ())
                if rows:
                    for row in rows:
                        r = dict(row) if hasattr(row, 'keys') else row
                        s = r.get('serie') if hasattr(r, 'get') else (r[0] if len(r) > 0 else None)
                        t = r.get('terminal_id') if hasattr(r, 'get') else (r[1] if len(r) > 1 else None)
                        if s is not None and t is not None:
                            existing_sec.add((s, t))
            except Exception as e:
                logger.debug(f"Could not load existing secuencias: {e}")
            for record in data:
                serie = record.get('serie')
                terminal_id = record.get('terminal_id')
                if serie is None or terminal_id is None:
                    continue
                key = (serie, terminal_id)
                if key in existing_sec:
                    operations.append((
                        "UPDATE secuencias SET ultimo_numero = GREATEST(ultimo_numero, %s), descripcion = COALESCE(%s, descripcion), synced = %s WHERE serie = %s AND terminal_id = %s",
                        (record.get('ultimo_numero'), record.get('descripcion'), record.get('synced'), serie, terminal_id)
                    ))
                    updated += 1
                else:
                    operations.append((
                        "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) VALUES (%s, %s, %s, %s, %s)",
                        (serie, terminal_id, record.get('ultimo_numero', 0), record.get('descripcion') or '', record.get('synced', 0))
                    ))
                    created += 1
                    existing_sec.add(key)
            if operations:
                batch_size = 1000
                for i in range(0, len(operations), batch_size):
                    batch = operations[i:i + batch_size]
                    result = pos_core.db.execute_transaction(batch)
                    if result is None or not (result.get('success') if isinstance(result, dict) else result):
                        raise Exception("Transaction failed for secuencias batch")
                logger.info(f"✅ secuencias applied: {updated} updated, {created} created (GREATEST for ultimo_numero)")
            return

        # OPTIMIZACIÓN: Obtener todos los IDs existentes en UNA consulta
        id_values = [record.get(id_column) for record in data if record.get(id_column)]
        if not id_values:
            return

        # Crear placeholders para la consulta IN
        placeholders = ','.join(['%s'] * len(id_values))
        existing_ids_query = f"SELECT {id_column} FROM {validated_table} WHERE {id_column} IN ({placeholders})"
        existing_ids_result = pos_core.db.execute_query(existing_ids_query, tuple(id_values))

        # Si hay columnas UNIQUE, también obtener registros existentes por esas columnas
        existing_by_unique = {}
        if unique_columns:
            for unique_col in unique_columns:
                unique_values = [record.get(unique_col) for record in data if record.get(unique_col) and record.get(unique_col) != '']
                if unique_values:
                    # Remove duplicates and None values
                    unique_values = list(set([v for v in unique_values if v is not None]))
                    if unique_values:
                        unique_placeholders = ','.join(['%s'] * len(unique_values))
                        unique_query = f"SELECT {id_column}, {unique_col} FROM {validated_table} WHERE {unique_col} IN ({unique_placeholders})"
                        unique_result = pos_core.db.execute_query(unique_query, tuple(unique_values))
                        if unique_result:
                            for row in unique_result:
                                unique_value = row[1]  # El valor de la columna única
                                # Only add if value is not None/empty to avoid key errors
                                if unique_value is not None and str(unique_value).strip() != '':
                                    existing_by_unique[(unique_col, unique_value)] = row[0]  # El id existente

        # Convertir a set para búsqueda O(1)
        existing_ids = {row[0] for row in existing_ids_result} if existing_ids_result else set()

        # Preparar operaciones
        for record_idx, record in enumerate(data):
            id_value = record.get(id_column)
            if not id_value:
                logger.debug(f"Record missing id_column: table={validated_table}, index={record_idx}")
                continue

            # Validate that all columns exist in record (use None for missing)
            values = [record.get(col) for col in columns]

            # Verificar si el registro existe por id O por columnas únicas
            record_exists_by_id = id_value in existing_ids
            record_exists_by_unique = False
            existing_id_by_unique = None

            # CRITICAL: Si hay columnas UNIQUE, verificar SIEMPRE
            if unique_columns:
                for unique_col in unique_columns:
                    unique_value = record.get(unique_col)
                    if unique_value is not None and unique_value != '':
                        key = (unique_col, unique_value)
                        if key in existing_by_unique:
                            existing_id_by_unique = existing_by_unique[key]
                            if existing_id_by_unique != id_value:
                                record_exists_by_unique = True
                                logger.debug(f"Found existing record by unique column: table={table_name}, unique_col={unique_col}, existing_id={existing_id_by_unique}, server_id={id_value}")
                                break
                            elif existing_id_by_unique == id_value:
                                record_exists_by_id = True
                                break

            # Validate column count matches value count before any operations
            if len(values) != len(columns):
                logger.error(f"Column/value mismatch for {table_name} id={id_value}: {len(columns)} columns, {len(values)} values")
                skipped += 1
                continue

            if record_exists_by_id or record_exists_by_unique:
                # Update existing - usar el id existente si se encontró por columna única
                update_id = existing_id_by_unique if record_exists_by_unique else id_value

                # Verificar conflictos con columnas únicas
                if record_exists_by_id and not record_exists_by_unique and unique_columns:
                    for unique_col in unique_columns:
                        unique_value = record.get(unique_col)
                        if unique_value is not None and unique_value != '':
                            check_query = f"SELECT {id_column} FROM {validated_table} WHERE {unique_col} = %s AND {id_column} != %s"
                            existing_with_unique = pos_core.db.execute_query(check_query, (unique_value, id_value))

                            if existing_with_unique and len(existing_with_unique) > 0 and len(existing_with_unique[0]) > 0:
                                update_id = existing_with_unique[0][0]
                                logger.warning(f"⚠️ CONFLICT: {table_name} - Record id={id_value} has {unique_col}={unique_value} that exists in id={update_id}. Using id={update_id} for UPDATE.")
                                record_exists_by_unique = True
                                break

                # Obtener registro existente para comparar timestamp
                # NOTA: sync_version puede no existir en todas las tablas, usar solo updated_at
                existing_timestamp = None
                existing_sync_version = None
                try:
                    existing_query = f"SELECT updated_at FROM {validated_table} WHERE {id_column} = %s"
                    existing_rows = pos_core.db.execute_query(existing_query, (update_id,))
                    # E11: Acceso por nombre de columna (backend puede devolver dict-like)
                    if existing_rows and len(existing_rows) > 0:
                        r0 = existing_rows[0]
                        existing_timestamp = (r0.get("updated_at") if hasattr(r0, "get") else (r0[0] if len(r0) >= 1 else None)) if r0 else None
                except Exception as e:
                    # Si updated_at no existe, continuar sin verificación de timestamp
                    logger.debug(f"Could not get updated_at for {table_name} id={update_id}: {e}")

                new_timestamp = record.get("updated_at")
                new_sync_version = record.get("sync_version", 0)

                should_skip = False
                conflict_reason = None

                # Prioridad 1: Comparar sync_version
                sync_version_equal = False
                if existing_sync_version is not None and new_sync_version is not None:
                    if new_sync_version < existing_sync_version:
                        should_skip = True
                        conflict_reason = f"sync_version (existing={existing_sync_version}, new={new_sync_version})"
                    elif new_sync_version == existing_sync_version:
                        sync_version_equal = True

                # Prioridad 2: Comparar timestamps
                timestamp_equal = False
                if not should_skip and existing_timestamp and new_timestamp:
                    from datetime import datetime
                    try:
                        existing_dt = datetime.fromisoformat(existing_timestamp.replace('Z', '+00:00'))
                        new_dt = datetime.fromisoformat(new_timestamp.replace('Z', '+00:00'))

                        if new_dt < existing_dt:
                            should_skip = True
                            conflict_reason = f"timestamp (existing={existing_timestamp}, new={new_timestamp})"
                        elif new_dt == existing_dt:
                            timestamp_equal = True
                            if sync_version_equal:
                                should_skip = True
                                conflict_reason = f"identical (sync_version={existing_sync_version}, timestamp={existing_timestamp})"
                            else:
                                should_skip = True
                                conflict_reason = f"equal timestamp (existing={existing_timestamp}, new={new_timestamp})"
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"⚠️ Error comparing timestamps for {table_name} id={update_id}: {e}. Proceeding with update.")

                # Fallback: Si no hay metadata, actualizar con advertencia
                if not should_skip and not existing_timestamp and not new_timestamp and existing_sync_version is None and new_sync_version is None:
                    logger.warning(f"⚠️ NO_METADATA: {table_name} id={update_id} - updating without conflict check!")
                    try:
                        record_identifier = record.get("sku") or record.get("wallet_id") or str(update_id)
                        pos_core.db.execute_write("""
                            INSERT INTO sync_conflicts
                            (table_name, record_id, record_identifier, conflict_type,
                             existing_timestamp, new_timestamp, existing_sync_version, new_sync_version,
                             conflict_reason, resolved_action, terminal_id, branch_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            table_name,
                            update_id,
                            record_identifier,
                            "no_metadata",
                            None,
                            None,
                            None,
                            None,
                            "forced_update - no metadata available",
                            "forced_update",
                            record.get("terminal_id"),
                            record.get("branch_id")
                        ))
                    except Exception as e:
                        logger.debug(f"Could not log no_metadata conflict: {e}")

                # Si debe saltarse, registrar conflicto y continuar
                if should_skip:
                    if conflict_reason and "identical" in conflict_reason:
                        conflict_type = "identical"
                        action = "skipped_identical"
                        logger.debug(f"⚠️ IDENTICAL: {table_name} id={update_id} - same version and timestamp, skipping")
                    elif conflict_reason and conflict_reason.startswith("sync_version"):
                        conflict_type = "sync_version"
                        action = "skipped"
                    else:
                        conflict_type = "timestamp"
                        action = "skipped"

                    try:
                        record_identifier = record.get("sku") or record.get("wallet_id") or str(update_id)
                        pos_core.db.execute_write("""
                            INSERT INTO sync_conflicts
                            (table_name, record_id, record_identifier, conflict_type,
                             existing_timestamp, new_timestamp, existing_sync_version, new_sync_version,
                             conflict_reason, resolved_action, terminal_id, branch_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            table_name,
                            update_id,
                            record_identifier,
                            conflict_type,
                            existing_timestamp,
                            new_timestamp,
                            existing_sync_version,
                            new_sync_version,
                            conflict_reason,
                            action,
                            record.get("terminal_id"),
                            record.get("branch_id")
                        ))
                    except Exception as e:
                        logger.debug(f"Could not log conflict to sync_conflicts table: {e}")

                    logger.info(f"⏭️ CONFLICT: {table_name} id={update_id} skipped - local is newer ({conflict_reason})")
                    skipped += 1
                    continue

                # CRITICAL FIX 2026-02-03: Check if local record has synced=0 (pending local changes)
                # If synced=0, this means there are LOCAL CHANGES that haven't been pushed to server yet
                # We MUST NOT overwrite these with server data, or local changes will be LOST
                if 'synced' in config.get('columns', []):
                    try:
                        synced_check = pos_core.db.execute_query(
                            f"SELECT synced FROM {validated_table} WHERE {id_column} = %s",
                            (update_id,)
                        )
                        if synced_check and len(synced_check) > 0:
                            local_synced = synced_check[0].get('synced') if hasattr(synced_check[0], 'get') else synced_check[0][0]
                            if local_synced == 0 or local_synced == False:
                                logger.warning(
                                    f"⚠️ PROTECTED: {table_name} id={update_id} has synced=0 (pending local changes). "
                                    f"SKIPPING server update to preserve local data. Push first!"
                                )
                                skipped += 1
                                continue
                    except Exception as e:
                        logger.debug(f"Could not check synced flag for {table_name} id={update_id}: {e}")

                # Proceder con UPDATE
                columns_to_update = [col for col in columns if col != id_column]

                # CRITICAL FIX 2026-02-03: NEVER let server overwrite the local 'synced' flag
                # The synced flag is managed locally to track pending changes
                # If server sends synced=1 but we have synced=0, we'd lose track of pending changes
                if 'synced' in columns_to_update:
                    columns_to_update.remove('synced')
                    logger.debug(f"Excluded 'synced' column from UPDATE for {table_name} id={update_id}")

                # Excluir columnas únicas del UPDATE si causarían conflictos
                if unique_columns:
                    for unique_col in unique_columns:
                        unique_value = record.get(unique_col)
                        if unique_value is not None and unique_value != '':
                            check_query = f"SELECT {id_column} FROM {validated_table} WHERE {unique_col} = %s AND {id_column} != %s"
                            existing_with_unique = pos_core.db.execute_query(check_query, (unique_value, update_id))

                            if existing_with_unique:
                                if unique_col in columns_to_update:
                                    columns_to_update.remove(unique_col)
                                    logger.warning(f"⚠️ UPDATE {table_name} id={update_id}: Excluding {unique_col}={unique_value} from UPDATE (exists in another record)")

                            if record_exists_by_unique:
                                if unique_col in columns_to_update:
                                    columns_to_update.remove(unique_col)

                            current_unique_query = f"SELECT {unique_col} FROM {validated_table} WHERE {id_column} = %s"
                            current_unique_result = pos_core.db.execute_query(current_unique_query, (update_id,))
                            if current_unique_result and len(current_unique_result) > 0 and len(current_unique_result[0]) > 0:
                                current_unique_value = current_unique_result[0][0]
                                if current_unique_value is not None and current_unique_value != unique_value:
                                    if unique_col in columns_to_update:
                                        columns_to_update.remove(unique_col)
                                        logger.warning(f"⚠️ UPDATE {table_name} id={update_id}: Excluding {unique_col} from UPDATE (current={current_unique_value} != new={unique_value})")

                if not columns_to_update:
                    logger.debug(f"⚠️ UPDATE {table_name} id={update_id}: No columns to update (all are unique), skipping")
                    continue

                # FIX 2026-02-01: Para secuencias, usar GREATEST para no retroceder ultimo_numero
                if table_name == "secuencias":
                    set_parts = []
                    update_values = []
                    for col in columns_to_update:
                        if col == "ultimo_numero":
                            # GREATEST garantiza que solo aumenta, nunca disminuye
                            set_parts.append(f"{col} = GREATEST({col}, %s)")
                        else:
                            set_parts.append(f"{col} = %s")
                        update_values.append(record.get(col))
                    set_clause = ", ".join(set_parts)
                    logger.info(f"🔢 SECUENCIAS: Using GREATEST for ultimo_numero (new value: {record.get('ultimo_numero')})")
                else:
                    set_clause = ", ".join([f"{col} = %s" for col in columns_to_update])
                    update_values = [record.get(col) for col in columns_to_update]
                update_values.append(update_id)

                operations.append((
                    f"UPDATE {validated_table} SET {set_clause} WHERE {id_column} = %s",
                    tuple(update_values)
                ))
                updated += 1
                logger.debug(f"✅ Updated {table_name} id={update_id}")
            else:
                # Insert new - validate placeholder count matches values
                if len(values) != len(columns):
                    logger.error(f"INSERT column/value mismatch for {table_name}: {len(columns)} columns, {len(values)} values")
                    skipped += 1
                    continue
                placeholders = ", ".join(["%s" for _ in columns])
                operations.append((
                    f"INSERT INTO {validated_table} ({', '.join(columns)}) VALUES ({placeholders})",
                    tuple(values)
                ))
                created += 1

        # Execute all operations in batches
        if operations:
            batch_size = 1000
            batch_count = 0
            for i in range(0, len(operations), batch_size):
                batch = operations[i:i + batch_size]
                batch_count += 1

                try:
                    result = pos_core.db.execute_transaction(batch)
                    if result is None:
                        raise Exception(f"Transaction returned None for {table_name} batch {batch_count}")
                    success = result.get('success') if isinstance(result, dict) else result
                    if not success:
                        raise Exception(f"Transaction failed for {table_name} batch {batch_count} (returned False)")
                except Exception as batch_error:
                    error_msg = str(batch_error)
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + "..."
                    raise Exception(f"Transaction failed for {table_name} batch {batch_count}: {error_msg}")

            total_time = time.time() - start_time
            logger.info(f"✅ {table_name} applied: {updated} updated, {created} created, {skipped} skipped (took {total_time:.2f}s)")
        else:
            logger.warning(f"⚠️ No operations for {table_name}")

    except Exception as e:
        import traceback
        logger.error(f"Error applying {table_name} data: {e}")
        logger.error(f"Exception type: {type(e).__name__}, Traceback: {traceback.format_exc()[:500]}")
        raise  # Re-raise para que sync_all_tables_pull capture el error
