"""
Database Purge - Limpieza forense para producción
Reinicia folios, limpia transacciones test, mantiene catálogos
"""

from typing import Any, Dict, List
from datetime import datetime
import logging
import os
import re
from pathlib import Path
import shutil
import subprocess

logger = logging.getLogger(__name__)

# FIX 2026-02-01: Patrón para validar nombres de tabla
_SAFE_TABLE_PATTERN = re.compile(r'^[a-z_][a-z0-9_]*$')


def _validate_table_name(table: str) -> str:
    """Valida que un nombre de tabla sea seguro."""
    if not _SAFE_TABLE_PATTERN.match(table):
        raise ValueError(f"Invalid table name: {table}")
    return table

class DatabasePurge:
    """
    Limpieza forense de base de datos para transición a producción.
    Mantiene catálogos (products, emitters), elimina transacciones test.
    """
    
    # Tablas a VACIAR completamente (datos de prueba)
    TABLES_TO_TRUNCATE = [
        'sales',
        'sale_items',
        'cash_extractions',
        'returns',
        'self_consumption',
        'loss_records',
        'pending_invoices',
        'cfdis',
        'turns',
        'turn_entries',
        'turn_exits',
        'audit_log',
        'personal_expenses',
        'loyalty_ledger',
    ]
    
    # Tablas a MANTENER (catálogos)
    TABLES_TO_KEEP = [
        'products',
        'categories',
        'customers',
        'users',
        'emitters',
        'related_persons',
        'permission_config',
        'loyalty_accounts',
    ]
    
    # Secuencias a REINICIAR
    SEQUENCES_TO_RESET = [
        ('A', 1),  # Serie A empieza en 1
        ('B', 1),  # Serie B empieza en 1
    ]
    
    def __init__(self, core):
        self.core = core
        self.backup_path = Path(__file__).resolve().parent.parent.parent / 'backups'
        self.backup_path.mkdir(parents=True, exist_ok=True)
    
    def preview_purge(self) -> Dict[str, Any]:
        """Preview de lo que se va a eliminar (sin ejecutar)."""
        preview = {
            'tables_to_truncate': [],
            'tables_to_keep': [],
            'sequences_to_reset': []
        }
        
        for table in self.TABLES_TO_TRUNCATE:
            try:
                # FIX 2026-02-01: Validar nombre de tabla
                safe_table = _validate_table_name(table)
                count = list(self.core.db.execute_query(
                    f"SELECT COUNT(*) as c FROM {safe_table}"
                ))
                preview['tables_to_truncate'].append({
                    'table': table,
                    'records': count[0]['c'] if count else 0
                })
            # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
            except Exception as e:
                logger.debug(f"Error counting table {table}: {e}")

        for table in self.TABLES_TO_KEEP:
            try:
                # FIX 2026-02-01: Validar nombre de tabla
                safe_table = _validate_table_name(table)
                count = list(self.core.db.execute_query(
                    f"SELECT COUNT(*) as c FROM {safe_table}"
                ))
                preview['tables_to_keep'].append({
                    'table': table,
                    'records': count[0]['c'] if count else 0
                })
            except Exception:
                pass
        
        preview['sequences_to_reset'] = self.SEQUENCES_TO_RESET
        preview['total_to_delete'] = sum(
            t['records'] for t in preview['tables_to_truncate']
        )
        
        return preview
    
    def create_backup(self) -> Dict[str, Any]:
        """Crea backup antes de la purga."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"pre_purge_backup_{timestamp}.db"
        backup_file = self.backup_path / backup_name
        
        # Copiar base de datos actual
        db_path = Path(__file__).resolve().parent.parent.parent / 'data/pos.db'
        
        if db_path.exists():
            shutil.copy2(str(db_path), str(backup_file))
            # SECURITY: No loguear creación de backups de purga
            pass
            
            return {
                'success': True,
                'backup_path': str(backup_file),
                'size_mb': round(backup_file.stat().st_size / (1024*1024), 2)
            }
        
        return {'success': False, 'error': 'DB not found'}
    
    def execute_purge(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Ejecuta la purga de datos de prueba.
        
        Args:
            confirm: Debe ser True para ejecutar (seguridad)
        """
        if not confirm:
            return {
                'success': False,
                'error': 'Debe confirmar con confirm=True',
                'preview': self.preview_purge()
            }
        
        # 1. Crear backup primero
        backup = self.create_backup()
        if not backup.get('success'):
            return {'success': False, 'error': 'Backup failed'}
        
        results = {
            'backup': backup,
            'truncated': [],
            'sequences_reset': [],
            'errors': []
        }
        
        # 2. Truncar tablas de transacciones
        for table in self.TABLES_TO_TRUNCATE:
            try:
                # FIX 2026-02-01: Validar nombre de tabla
                safe_table = _validate_table_name(table)
                # nosec B608 - table validated against _SAFE_TABLE_PATTERN regex
                self.core.db.execute_write(f"DELETE FROM {safe_table}")
                results['truncated'].append(table)
                # SECURITY: No loguear tablas truncadas
                pass
            except Exception as e:
                results['errors'].append(f"{table}: {e}")
        
        # 3. Reiniciar secuencias de folios
        for serie, start_folio in self.SEQUENCES_TO_RESET:
            try:
                self.core.db.execute_write(
                    "UPDATE secuencias SET ultimo_numero = %s WHERE serie = %s",
                    (start_folio - 1, serie)  # -1 porque incrementa antes de usar
                )
                results['sequences_reset'].append(serie)
                # SECURITY: No loguear reinicio de secuencias (incluye Serie B)
                pass
            except Exception as e:
                results['errors'].append(f"Secuencia {serie}: {e}")
        
        # 4. VACUUM para recuperar espacio
        # Nota: En PostgreSQL, VACUUM funciona pero puede requerir privilegios
        try:
            self.core.db.execute_write("VACUUM")
            results['vacuum'] = True
            # SECURITY: No loguear VACUUM
            pass
        except Exception as e:
            # En PostgreSQL, VACUUM puede fallar si no hay privilegios suficientes
            logger.warning(f"VACUUM no pudo ejecutarse (puede requerir privilegios): {e}")
            results['vacuum'] = False
        
        results['success'] = len(results['errors']) == 0
        results['timestamp'] = datetime.now().isoformat()
        
        # SECURITY: No loguear purgas completadas
        pass
        
        return results
    
    def secure_shred(self, file_path: str) -> Dict[str, Any]:
        """
        Shred seguro de archivo (sobrescribe multiples veces).
        Solo usar en archivos temporales, NO en la DB principal.
        """
        if not os.path.exists(file_path):
            return {'success': False, 'error': 'File not found'}
        
        try:
            # shred -vfz -n 3: 3 pasadas aleatorias + 1 pasada de ceros
            result = subprocess.run(
                ['shred', '-vfz', '-n', '3', file_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                os.remove(file_path)
                # SECURITY: No loguear operaciones de shred
                pass
                return {'success': True, 'message': 'File securely destroyed'}
            else:
                return {'success': False, 'error': result.stderr}
                
        except FileNotFoundError:
            # shred no disponible, usar fallback
            return self._fallback_shred(file_path)
    
    def _fallback_shred(self, file_path: str) -> Dict[str, Any]:
        """Fallback si shred no está disponible."""
        try:
            size = os.path.getsize(file_path)
            
            # Sobrescribir con datos aleatorios 3 veces
            for i in range(3):
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(size))
            
            # Sobrescribir con ceros
            with open(file_path, 'wb') as f:
                f.write(b'\x00' * size)
            
            os.remove(file_path)
            
            return {'success': True, 'message': 'Fallback shred completed'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_checklist(self) -> Dict[str, Any]:
        """Checklist de preparación para producción."""
        checklist = {
            'timestamp': datetime.now().isoformat(),
            'items': []
        }
        
        # 1. Verificar emisores
        emitters = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM emitters WHERE is_active = 1"
        ))
        checklist['items'].append({
            'name': 'Emisores configurados',
            'status': '🟢' if emitters and emitters[0]['c'] > 0 else '🔴',
            'value': emitters[0]['c'] if emitters else 0
        })
        
        # 2. Verificar secuencias
        seqs = list(self.core.db.execute_query("SELECT * FROM secuencias"))
        checklist['items'].append({
            'name': 'Secuencias de folios',
            'status': '🟢' if seqs else '🔴',
            'value': len(seqs)
        })
        
        # 3. Verificar productos
        prods = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM products"
        ))
        checklist['items'].append({
            'name': 'Productos activos',
            'status': '🟢' if prods and prods[0]['c'] > 0 else '🔴',
            'value': prods[0]['c'] if prods else 0
        })
        
        # 4. Verificar familiares registrados
        try:
            fam = list(self.core.db.execute_query(
                "SELECT COUNT(*) as c FROM related_persons WHERE is_active = 1"
            ))
            checklist['items'].append({
                'name': 'Familiares para contratos',
                'status': '🟢' if fam and fam[0]['c'] > 0 else '🟡',
                'value': fam[0]['c'] if fam else 0
            })
        except Exception:
            pass
        
        # 5. Verificar ventas pendientes de limpiar
        sales = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM sales"
        ))
        sales_count = sales[0]['c'] if sales else 0
        checklist['items'].append({
            'name': 'Ventas de prueba (limpiar)',
            'status': '🟡' if sales_count > 0 else '🟢',
            'value': sales_count,
            'action': 'Ejecutar purge' if sales_count > 0 else None
        })
        
        return checklist
