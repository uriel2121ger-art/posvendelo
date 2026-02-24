"""
Database Partitioning - Particionado de tablas por año
Optimización para rendimiento y borrado forense rápido
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
from pathlib import Path
import shutil
import sys

logger = logging.getLogger(__name__)

class DatabasePartitioner:
    """
    Gestor de particionado de base de datos por año.
    
    Nota: SQLite no soporta particionado nativo como PostgreSQL.
    Implementamos particionado lógico usando:
    1. Tablas separadas por año (sales_2025, sales_2026)
    2. Vista unificada para queries transparentes
    3. Función de "desprendimiento" para borrado forense rápido
    """
    
    PARTITIONABLE_TABLES = [
        'sales',
        'sale_items', 
        'audit_log',
        'inventory_log',
        'cash_movements',
        'loss_records'
    ]
    
    def __init__(self, core):
        self.core = core
        self.current_year = datetime.now().year

    def _validate_table_name(self, table: str) -> str:
        """
        SECURITY: Validate table name against whitelist.
        Prevents SQL injection if table names ever come from external sources.
        """
        if table not in self.PARTITIONABLE_TABLES:
            raise ValueError(f"Invalid table name: {table}. Must be one of {self.PARTITIONABLE_TABLES}")
        return table

    def _quote_identifier(self, identifier: str) -> str:
        """
        SECURITY: Quote SQL identifier for PostgreSQL.
        Escapes any double quotes in the identifier to prevent SQL injection.
        """
        # PostgreSQL uses double quotes for identifiers
        # Escape any existing double quotes by doubling them
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def setup_partitioning(self, year: int = None) -> Dict[str, Any]:
        """
        Configura particionado para un año.
        Crea tablas de partición y vistas unificadas.
        """
        if year is None:
            year = self.current_year
        
        results = {}
        
        for table in self.PARTITIONABLE_TABLES:
            result = self._create_year_partition(table, year)
            results[table] = result
        
        # SECURITY: No loguear configuración de particionado
        pass
        
        return {
            'year': year,
            'tables': results,
            'status': 'success'
        }
    
    def _create_year_partition(self, table: str, year: int) -> Dict:
        """Crea una partición de tabla para un año específico."""
        # SECURITY: Validate table against whitelist
        table = self._validate_table_name(table)
        partition_name = f"{table}_{year}"
        
        # Verificar si ya existe (PostgreSQL compatible)
        try:
            # Try using DatabaseManager.list_tables() first
            tables = self.core.db.list_tables()
            exists = partition_name in tables
        except Exception:
            # Fallback: use PostgreSQL information_schema
            exists_result = list(self.core.db.execute_query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
                (partition_name,)
            ))
            exists = len(exists_result) > 0
        
        if exists:
            return {'table': partition_name, 'action': 'exists'}
        
        # Obtener estructura de la tabla original desde PostgreSQL
        try:
            # Obtener columnas de la tabla desde information_schema
            columns_result = list(self.core.db.execute_query(
                """SELECT column_name, data_type, is_nullable, column_default,
                          character_maximum_length, numeric_precision, numeric_scale
                   FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=%s
                   ORDER BY ordinal_position""",
                (table,)
            ))

            if not columns_result:
                return {'table': partition_name, 'action': 'error', 'reason': 'Original table not found'}

            # Construir CREATE TABLE desde las columnas
            column_defs = []
            for col in columns_result:
                col_name = self._quote_identifier(col['column_name'])
                col_type = col['data_type'].upper()

                # Ajustar tipos con longitud/precisión
                if col.get('character_maximum_length'):
                    col_type = f"{col_type}({col['character_maximum_length']})"
                elif col.get('numeric_precision') and col['data_type'] == 'numeric':
                    scale = col.get('numeric_scale', 0)
                    col_type = f"NUMERIC({col['numeric_precision']},{scale})"

                col_def = f"{col_name} {col_type}"

                if col['is_nullable'] == 'NO':
                    col_def += " NOT NULL"
                if col.get('column_default'):
                    col_def += f" DEFAULT {col['column_default']}"

                column_defs.append(col_def)

            q_partition = self._quote_identifier(partition_name)
            partition_sql = f"CREATE TABLE IF NOT EXISTS {q_partition} ({', '.join(column_defs)})"

            self.core.db.execute_write(partition_sql)
            
            # Crear índices de la partición
            self._copy_indexes(table, partition_name)
            
            return {'table': partition_name, 'action': 'created'}
            
        except Exception as e:
            logger.error(f"Error creando partición {partition_name}: {e}")
            return {'table': partition_name, 'action': 'error', 'reason': str(e)}
    
    def _copy_indexes(self, source: str, target: str):
        """Copia índices de tabla fuente a destino."""
        # PostgreSQL: obtener índices desde pg_indexes
        try:
            indexes = list(self.core.db.execute_query(
                """SELECT indexname, indexdef
                   FROM pg_indexes
                   WHERE schemaname='public' AND tablename=%s""",
                (source,)
            ))
        except Exception:
            logger.warning(f"Index copying failed for {source}")
            return
        
        for idx in indexes:
            if idx.get('indexdef'):
                new_idx_sql = idx['indexdef'].replace(source, target)
                # Cambiar nombre del índice también
                new_idx_sql = new_idx_sql.replace(idx['indexname'], f"{idx['indexname']}_{target}")
                try:
                    self.core.db.execute_write(new_idx_sql)
                except Exception:
                    pass  # Índice ya existe
    
    def migrate_year_data(self, table: str, year: int, batch_size: int = 1000) -> Dict:
        """
        Migra datos de un año a su partición correspondiente.
        Procesa en lotes para no bloquear.
        """
        # SECURITY: Validate table against whitelist before using in SQL
        table = self._validate_table_name(table)

        # Use quoted identifiers for defense-in-depth
        q_table = self._quote_identifier(table)
        partition_name = f"{table}_{year}"
        q_partition = self._quote_identifier(partition_name)

        date_column = self._get_date_column(table)

        if not date_column:
            return {'error': f'No date column found for {table}'}

        q_date_col = self._quote_identifier(date_column)
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31 23:59:59"

        # Contar registros a migrar (using quoted identifiers)
        count_sql = f"""
            SELECT COUNT(*) as c FROM {q_table}
            WHERE CAST({q_date_col} AS DATE) BETWEEN %s AND %s
        """
        total_result = list(self.core.db.execute_query(count_sql, (start_date, end_date)))
        total = total_result[0]['c'] if total_result else 0

        if total == 0:
            return {'migrated': 0, 'message': 'No records to migrate'}

        # Migrar en lotes
        migrated = 0

        while migrated < total:
            # Insertar lote (using quoted identifiers)
            insert_sql = f"""
                INSERT INTO {q_partition}
                SELECT * FROM {q_table}
                WHERE CAST({q_date_col} AS DATE) BETWEEN %s AND %s
                LIMIT %s
            """
            self.core.db.execute_write(insert_sql, (start_date, end_date, batch_size))

            # Eliminar lote migrado (using quoted identifiers)
            delete_sql = f"""
                DELETE FROM {q_table}
                WHERE id IN (
                    SELECT id FROM {q_table}
                    WHERE CAST({q_date_col} AS DATE) BETWEEN %s AND %s
                    LIMIT %s
                )
            """
            self.core.db.execute_write(delete_sql, (start_date, end_date, batch_size))

            migrated += batch_size
            # SECURITY: No loguear migración de datos
            pass

        return {'table': table, 'partition': partition_name, 'migrated': total}
    
    def _get_date_column(self, table: str) -> Optional[str]:
        """Determina la columna de fecha para una tabla."""
        date_columns = {
            'sales': 'timestamp',
            'sale_items': 'sale_id',  # Usa join
            'audit_log': 'timestamp',
            'inventory_log': 'timestamp',
            'cash_movements': 'timestamp',
            'loss_records': 'created_at'
        }
        return date_columns.get(table)
    
    def create_unified_view(self, table: str) -> Dict:
        """
        Crea vista unificada que combina todas las particiones.
        Las queries normales usan esta vista de forma transparente.
        """
        # SECURITY: Validate table against whitelist
        table = self._validate_table_name(table)

        view_name = f"v_{table}"
        q_view = self._quote_identifier(view_name)

        # Encontrar todas las particiones (PostgreSQL compatible)
        try:
            # Try using DatabaseManager.list_tables() first
            all_tables = self.core.db.list_tables()
            partition_names = [t for t in all_tables if t.startswith(f"{table}_")]
        except Exception:
            # Fallback: use PostgreSQL information_schema
            partitions = list(self.core.db.execute_query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE %s",
                (f"{table}_%",)
            ))
            partition_names = [p.get('table_name') if isinstance(p, dict) else p[0] for p in partitions]

        if not partition_names:
            # Si no hay particiones, la vista apunta a la tabla original
            partition_names = [table]
        else:
            # Incluir tabla original también
            partition_names.insert(0, table)

        # SECURITY: Quote all partition names for defense-in-depth
        # Partition names come from database but could potentially be manipulated
        union_sql = " UNION ALL ".join([
            f"SELECT * FROM {self._quote_identifier(p)}" for p in partition_names
        ])

        view_sql = f"CREATE VIEW IF NOT EXISTS {q_view} AS {union_sql}"

        # Eliminar vista existente si hay
        # nosec B608 - q_view uses _quote_identifier for SQL escaping, table validated against whitelist
        self.core.db.execute_write(f"DROP VIEW IF EXISTS {q_view}")
        self.core.db.execute_write(view_sql)

        return {
            'view': view_name,
            'partitions': partition_names
        }
    
    def detach_partition(self, table: str, year: int,
                        archive_path: str = None) -> Dict[str, Any]:
        """
        Desprende (detach) una partición completa.

        Ventaja forense: En lugar de DELETE (lento, deja rastro),
        simplemente movemos/renombramos la tabla.
        """
        # SECURITY: Validate table against whitelist
        table = self._validate_table_name(table)

        partition_name = f"{table}_{year}"
        q_partition = self._quote_identifier(partition_name)

        # Verificar que existe (PostgreSQL compatible)
        try:
            tables = self.core.db.list_tables()
            exists = partition_name in tables
        except Exception:
            # Fallback: use PostgreSQL information_schema
            exists_result = list(self.core.db.execute_query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
                (partition_name,)
            ))
            exists = len(exists_result) > 0

        if not exists:
            return {'success': False, 'error': 'Partition not found'}

        if archive_path:
            # Exportar a archivo separado antes de eliminar
            self._export_partition(partition_name, archive_path)

        # Eliminar la tabla (DROP es instantáneo, no deja rastro)
        # nosec B608 - q_partition uses _quote_identifier, table validated against PARTITIONABLE_TABLES whitelist
        self.core.db.execute_write(f"DROP TABLE IF EXISTS {q_partition}")

        # Reconstruir vista unificada
        self.create_unified_view(table)

        # SECURITY: No loguear particiones desprendidas
        pass

        return {
            'success': True,
            'partition': partition_name,
            'archived_to': archive_path,
            'action': 'detached'
        }
    
    def _export_partition(self, partition_name: str, path: str):
        """Exporta una partición a archivo CSV."""
        import csv

        # SECURITY: Quote identifier for defense-in-depth
        q_partition = self._quote_identifier(partition_name)
        # nosec B608 - partition_name comes from internal method, quoted for defense-in-depth
        data = list(self.core.db.execute_query(f"SELECT * FROM {q_partition}"))
        
        if not data:
            return
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    
    def get_partition_stats(self) -> Dict[str, Any]:
        """Estadísticas de particionado."""
        stats = {}
        
        for table in self.PARTITIONABLE_TABLES:
            # Encontrar particiones (PostgreSQL compatible)
            try:
                all_tables = self.core.db.list_tables()
                partitions = [{'name': t} for t in all_tables if t.startswith(f"{table}_")]
            except Exception:
                # Fallback: use PostgreSQL information_schema
                partitions = list(self.core.db.execute_query(
                    "SELECT table_name as name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE %s",
                    (f"{table}_%",)
                ))
            
            partition_stats = []
            for p in partitions:
                count_result = list(self.core.db.execute_query(
                    f"SELECT COUNT(*) as c FROM {p['name']}"
                ))
                count = count_result[0]['c'] if count_result else 0
                partition_stats.append({
                    'name': p['name'],
                    'records': count
                })
            
            # Tabla principal
            try:
                main_result = list(self.core.db.execute_query(
                    f"SELECT COUNT(*) as c FROM {table}"
                ))
                main_count = main_result[0]['c'] if main_result else 0
            except Exception:
                main_count = 0
            
            stats[table] = {
                'main_table': main_count,
                'partitions': partition_stats
            }
        
        return stats
    
    def vacuum_all(self):
        """
        Ejecuta VACUUM para recuperar espacio después de detach.
        """
        self.core.db.execute_write("VACUUM")
        # SECURITY: No loguear VACUUM
        pass
    
    def prepare_for_year(self, year: int) -> Dict:
        """
        Prepara la base de datos para un nuevo año.
        - Crea particiones para el nuevo año
        - Migra datos del año anterior a su partición
        """
        previous_year = year - 1
        results = {}
        
        # Crear particiones para el nuevo año
        results['new_partitions'] = self.setup_partitioning(year)
        
        # Migrar datos del año anterior
        results['migrations'] = {}
        for table in self.PARTITIONABLE_TABLES:
            if table != 'sale_items':  # sale_items depende de sales
                result = self.migrate_year_data(table, previous_year)
                results['migrations'][table] = result
        
        # Recrear vistas
        results['views'] = {}
        for table in self.PARTITIONABLE_TABLES:
            result = self.create_unified_view(table)
            results['views'][table] = result
        
        # SECURITY: No loguear preparación de base de datos
        pass
        
        return results

# Función de utilidad para preparación de año nuevo
def prepare_database_new_year(core, year: int = None) -> Dict:
    """
    Prepara la base de datos para el nuevo año fiscal.
    Ejecutar el 31 de diciembre antes de medianoche.
    """
    if year is None:
        year = datetime.now().year + 1
    
    partitioner = DatabasePartitioner(core)
    return partitioner.prepare_for_year(year)

# Función de limpieza forense rápida
def forensic_wipe_year(core, year: int, require_confirmation: bool = True) -> Dict:
    """
    Borrado forense rápido de un año completo.
    DROP TABLE es instantáneo y no deja rastro en WAL.
    """
    if require_confirmation:
        confirm = input(f"¿Confirma borrado forense del año {year}? (escriba '{year}'): ")
        if confirm != str(year):
            return {'aborted': True}
    
    partitioner = DatabasePartitioner(core)
    results = {}
    
    for table in DatabasePartitioner.PARTITIONABLE_TABLES:
        result = partitioner.detach_partition(table, year)
        results[table] = result
    
    partitioner.vacuum_all()
    
    # SECURITY: No loguear borrados forenses
    pass
    
    return results
