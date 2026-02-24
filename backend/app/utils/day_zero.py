"""
Day Zero Protocol - Protocolo de arranque para producción (1 enero 2026)
Checklist automatizado y orden de operaciones
"""

from typing import Any, Dict, List
from datetime import date, datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DayZeroProtocol:
    """
    Protocolo de arranque para el primer día de producción.
    Orden de operaciones para transición limpia.
    """
    
    def __init__(self, core):
        self.core = core
    
    def run_full_checklist(self) -> Dict[str, Any]:
        """
        Ejecuta checklist completo de día cero.
        NO ejecuta cambios, solo verifica.
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'ready_for_production': True
        }
        
        # 1. Verificar purga de datos de prueba
        check1 = self._check_purge_status()
        results['checks'].append(check1)
        if not check1['passed']:
            results['ready_for_production'] = False
        
        # 2. Verificar secuencias de folios
        check2 = self._check_sequences()
        results['checks'].append(check2)
        if not check2['passed']:
            results['ready_for_production'] = False
        
        # 3. Verificar inventario inicial
        check3 = self._check_initial_inventory()
        results['checks'].append(check3)
        
        # 4. Verificar emisores Multi-RFC
        check4 = self._check_emitters()
        results['checks'].append(check4)
        if not check4['passed']:
            results['ready_for_production'] = False
        
        # 5. Verificar RAMFS montado
        check5 = self._check_ramfs()
        results['checks'].append(check5)
        
        # 6. Verificar familiares para contratos
        check6 = self._check_related_persons()
        results['checks'].append(check6)
        
        # 7. Verificar tamaño de base de datos
        check7 = self._check_db_size()
        results['checks'].append(check7)
        
        # Resumen
        passed = sum(1 for c in results['checks'] if c['passed'])
        total = len(results['checks'])
        results['summary'] = {
            'passed': passed,
            'total': total,
            'percentage': round((passed / total) * 100, 1)
        }
        
        return results
    
    def _check_purge_status(self) -> Dict[str, Any]:
        """Verifica que no haya datos de prueba."""
        sales = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM sales"
        ))
        
        count = sales[0]['c'] if sales else 0
        passed = count == 0
        
        return {
            'name': 'Purga de datos de prueba',
            'passed': passed,
            'status': '🟢' if passed else '🔴',
            'value': count,
            'message': 'Base limpia' if passed else f'{count} ventas de prueba pendientes',
            'action': None if passed else 'Ejecutar db_purge.execute_purge(confirm=True)'
        }
    
    def _check_sequences(self) -> Dict[str, Any]:
        """Verifica que las secuencias estén en 1."""
        # SECURITY: Especificar columnas y agregar LIMIT
        seqs = list(self.core.db.execute_query("SELECT id, serie, ultimo_numero FROM secuencias LIMIT 100"))
        
        all_reset = all(s['ultimo_numero'] == 0 for s in seqs)
        
        return {
            'name': 'Secuencias de folios',
            'passed': all_reset,
            'status': '🟢' if all_reset else '🟡',
            'value': {s['serie']: s['ultimo_numero'] for s in seqs},
            'message': 'Folios en 0' if all_reset else 'Folios con valores de prueba'
        }
    
    def _check_initial_inventory(self) -> Dict[str, Any]:
        """Verifica inventario inicial."""
        products = list(self.core.db.execute_query(
            """SELECT COUNT(*) as c, COALESCE(SUM(stock), 0) as total_stock
               FROM products"""
        ))
        
        if not products:
            return {'name': 'Inventario inicial', 'passed': True, 'status': '🟡', 'value': {}, 'message': 'Sin datos'}
        
        return {
            'name': 'Inventario inicial',
            'passed': True,  # Informativo
            'status': '🟢',
            'value': {
                'productos': products[0]['c'],
                'stock_total': float(products[0]['total_stock'] or 0)
            },
            'message': f'{products[0]["c"]:,} productos, {products[0]["total_stock"]:,.0f} unidades'
        }
    
    def _check_emitters(self) -> Dict[str, Any]:
        """Verifica emisores Multi-RFC."""
        # SECURITY: Especificar columnas y agregar LIMIT
        emitters = list(self.core.db.execute_query(
            "SELECT id, rfc, razon_social, is_primary, is_active FROM emitters WHERE is_active = 1 LIMIT 100"
        ))
        
        passed = len(emitters) >= 1
        primary = [e for e in emitters if e['is_primary']]
        
        return {
            'name': 'Emisores Multi-RFC',
            'passed': passed,
            'status': '🟢' if passed else '🔴',
            'value': len(emitters),
            'primary': primary[0]['rfc'] if primary else None,
            'message': f'{len(emitters)} emisor(es) activo(s)'
        }
    
    def _check_ramfs(self) -> Dict[str, Any]:
        """Verifica que RAMFS esté montado."""
        import os
        
        ramfs_path = '/mnt/ghost_logs'
        mounted = os.path.ismount(ramfs_path) if os.path.exists(ramfs_path) else False
        
        return {
            'name': 'RAMFS Ghost Logs',
            'passed': mounted,
            'status': '🟢' if mounted else '🟡',
            'value': 'MONTADO' if mounted else 'NO MONTADO',
            'message': 'Logs volátiles activos' if mounted else 'Ejecutar ramfs_setup.sh',
            'action': None if mounted else 'sudo ./scripts/ramfs_setup.sh'
        }
    
    def _check_related_persons(self) -> Dict[str, Any]:
        """Verifica familiares para contratos de donación."""
        try:
            persons = list(self.core.db.execute_query(
                "SELECT COUNT(*) as c FROM related_persons WHERE is_active = 1"
            ))
            count = persons[0]['c'] if persons else 0
        except Exception:
            count = 0
        
        return {
            'name': 'Familiares para contratos',
            'passed': count >= 1,
            'status': '🟢' if count >= 1 else '🟡',
            'value': count,
            'message': f'{count} familiar(es) registrado(s)'
        }
    
    def _check_db_size(self) -> Dict[str, Any]:
        """Verifica tamaño de base de datos (post-VACUUM)."""
        import os
        
        db_path = str(Path(__file__).resolve().parent.parent.parent) + '/data/pos.db'
        
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            
            # Después de purga + VACUUM, debería ser < 50MB típicamente
            is_compact = size_mb < 100
            
            return {
                'name': 'Tamaño base de datos',
                'passed': is_compact,
                'status': '🟢' if is_compact else '🟡',
                'value': f'{size_mb:.1f} MB',
                'message': 'Tamaño óptimo' if is_compact else 'Considerar VACUUM adicional'
            }
        
        return {
            'name': 'Tamaño base de datos',
            'passed': False,
            'status': '🔴',
            'value': 'NO ENCONTRADA'
        }
    
    def get_operation_order(self) -> List[Dict[str, Any]]:
        """
        Orden de operaciones para el día cero.
        """
        return [
            {
                'step': 1,
                'name': 'EJECUTAR PURGA',
                'command': 'purge.execute_purge(confirm=True)',
                'description': 'Elimina datos de prueba, reinicia folios a 0',
                'critical': True
            },
            {
                'step': 2,
                'name': 'CONTEO FÍSICO',
                'command': 'Manual',
                'description': 'Realizar conteo real de inventario el 31 dic',
                'critical': True
            },
            {
                'step': 3,
                'name': 'AJUSTAR INVENTARIO',
                'command': 'UPDATE products SET stock = X WHERE id = Y',
                'description': 'Actualizar stock según conteo físico',
                'critical': True
            },
            {
                'step': 4,
                'name': 'VERIFICAR EMISORES',
                'command': 'multi.get_best_emitter()',
                'description': 'Confirmar RFC primario para enero',
                'critical': True
            },
            {
                'step': 5,
                'name': 'MONTAR RAMFS',
                'command': 'sudo ./scripts/startup_production.sh',
                'description': 'Activar logs volátiles en memoria',
                'critical': False
            },
            {
                'step': 6,
                'name': 'AGREGAR A CRONTAB',
                'command': '@reboot /path/startup_production.sh',
                'description': 'Asegurar que RAMFS se monte al reiniciar',
                'critical': False
            },
            {
                'step': 7,
                'name': 'VERIFICACIÓN FINAL',
                'command': 'day_zero.run_full_checklist()',
                'description': 'Ejecutar este checklist para confirmar',
                'critical': True
            }
        ]
    
    def print_report(self) -> str:
        """Genera reporte imprimible del estado."""
        results = self.run_full_checklist()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PROTOCOLO DÍA CERO - TITAN POS                            ║
║                    Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

ESTADO GENERAL: {'✅ LISTO' if results['ready_for_production'] else '⚠️ PENDIENTE'}
Verificaciones: {results['summary']['passed']}/{results['summary']['total']} ({results['summary']['percentage']}%)

───────────────────────────────────────────────────────────────────────────────
                              CHECKLIST
───────────────────────────────────────────────────────────────────────────────
"""
        
        for check in results['checks']:
            report += f"\n{check['status']} {check['name']}: {check.get('message', check['value'])}"
            if check.get('action'):
                report += f"\n   → {check['action']}"
        
        report += """

───────────────────────────────────────────────────────────────────────────────
                         ORDEN DE OPERACIONES
───────────────────────────────────────────────────────────────────────────────
"""
        
        for op in self.get_operation_order():
            critical = '⚠️' if op['critical'] else '  '
            report += f"\n{critical} {op['step']}. {op['name']}"
            report += f"\n      {op['description']}"
        
        return report
