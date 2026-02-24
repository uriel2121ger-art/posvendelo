"""
Cross Audit - Auditoría Cruzada Automática
El General de Guerra que vigila el imperio cada domingo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Any, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CrossAudit:
    """
    Auditoría cruzada automática que compara:
    - Inventario teórico vs real
    - Ventas Serie A vs Serie B por sucursal
    - Márgenes de merma por sucursal
    - Capacidad RESICO por RFC
    """
    
    # Tolerancias
    MERMA_TOLERANCE = 2.0      # 2% máximo de diferencia inventario
    MARGIN_TOLERANCE = 5.0     # 5% variación de margen
    RESICO_WARNING = 70        # Alertar al 70% del límite
    RESICO_CRITICAL = 90       # Crítico al 90%
    
    def __init__(self, core=None):
        if core is None:
            from app.core import POSCore
            core = POSCore()
        self.core = core
        self.report_date = datetime.now()
        self.alerts = []
    
    def run_full_audit(self) -> Dict[str, Any]:
        """Ejecuta auditoría completa de todas las áreas."""
        self.alerts = []
        
        report = {
            'timestamp': self.report_date.isoformat(),
            'week': self.report_date.isocalendar()[1],
            'sections': {}
        }
        
        # 1. Auditoría de Inventario
        report['sections']['inventory'] = self._audit_inventory()
        
        # 2. Auditoría de Ventas por Serie
        report['sections']['sales'] = self._audit_sales()
        
        # 3. Auditoría de Mermas
        report['sections']['shrinkage'] = self._audit_shrinkage()
        
        # 4. Auditoría RESICO
        report['sections']['resico'] = self._audit_resico()
        
        # 5. Auditoría de Márgenes
        report['sections']['margins'] = self._audit_margins()
        
        # 6. Consolidado de alertas
        report['alerts'] = self.alerts
        report['summary'] = self._generate_summary(report)
        
        return report
    
    def _audit_inventory(self) -> Dict[str, Any]:
        """Audita discrepancias de inventario."""
        # Obtener sucursales
        try:
            branches = list(self.core.db.execute_query(
                "SELECT id, name FROM branches"
            ))
        except Exception:
            branches = [{'id': 1, 'name': 'Principal'}]
        
        results = []
        week_ago = (self.report_date - timedelta(days=7)).strftime('%Y-%m-%d')
        
        for branch in branches:
            b_id = branch['id']
            
            # Calcular inventario teórico
            # Stock inicial + Entradas - Ventas - Mermas = Stock teórico
            try:
                # Ventas de la semana
                sales_result = list(self.core.db.execute_query("""
                    SELECT COALESCE(SUM(si.qty), 0) as sold
                    FROM sale_items si
                    JOIN sales s ON si.sale_id = s.id
                    WHERE s.timestamp::date >= %s AND s.status = 'completed'
                """, (week_ago,)))
                sales_qty = sales_result[0].get('sold', 0) if sales_result and len(sales_result) > 0 and sales_result[0] else 0

                # Mermas de la semana
                shrink_result = list(self.core.db.execute_query("""
                    SELECT COALESCE(SUM(quantity), 0) as shrink
                    FROM loss_records WHERE created_at::date >= %s
                """, (week_ago,)))
                shrink_qty = shrink_result[0].get('shrink', 0) if shrink_result and len(shrink_result) > 0 and shrink_result[0] else 0

                # Stock actual total
                stock_result = list(self.core.db.execute_query(
                    "SELECT COALESCE(SUM(stock), 0) as total FROM products"
                ))
                current_stock = stock_result[0].get('total', 0) if stock_result and len(stock_result) > 0 and stock_result[0] else 0
                
                # Calcular varianza (simplificado)
                # En producción, comparar contra conteo físico
                variance_pct = (float(shrink_qty) / max(float(sales_qty), 1)) * 100
                
                status = 'OK'
                if variance_pct > self.MERMA_TOLERANCE:
                    status = 'WARNING'
                    self.alerts.append({
                        'type': 'INVENTORY',
                        'level': 'WARNING',
                        'branch': branch['name'],
                        'message': f"Varianza de inventario {variance_pct:.1f}% (tolerancia: {self.MERMA_TOLERANCE}%)"
                    })
                
                results.append({
                    'branch_id': b_id,
                    'branch_name': branch['name'],
                    'sales_qty': float(sales_qty),
                    'shrinkage_qty': float(shrink_qty),
                    'current_stock': float(current_stock),
                    'variance_pct': round(variance_pct, 2),
                    'status': status
                })
                
            except Exception as e:
                logger.error(f"Error auditando inventario: {e}")
        
        return {
            'period': f"{week_ago} - {self.report_date.strftime('%Y-%m-%d')}",
            'branches': results,
            'total_variance': sum(r['variance_pct'] for r in results) / len(results) if results else 0
        }
    
    def _audit_sales(self) -> Dict[str, Any]:
        """Audita distribución de ventas A/B."""
        week_ago = (self.report_date - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Ventas por serie
        sql = """
            SELECT serie, COUNT(*) as count, COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE timestamp::date >= %s AND status = 'completed'
            GROUP BY serie
        """
        by_serie = list(self.core.db.execute_query(sql, (week_ago,)))
        
        serie_a = next((s for s in by_serie if s['serie'] == 'A'), {'count': 0, 'total': 0})
        serie_b = next((s for s in by_serie if s['serie'] == 'B'), {'count': 0, 'total': 0})
        
        total = float(serie_a['total'] or 0) + float(serie_b['total'] or 0)
        
        # Ratio B/A (para monitorear fiscalización)
        ratio_b = (float(serie_b['total'] or 0) / total * 100) if total > 0 else 0
        
        # Si Serie B es muy alta, alertar
        if ratio_b > 60:
            self.alerts.append({
                'type': 'SALES_MIX',
                'level': 'INFO',
                'message': f"Serie B representa {ratio_b:.1f}% de ventas - considerar más facturación"
            })
        
        return {
            'period': f"{week_ago} - {self.report_date.strftime('%Y-%m-%d')}",
            'serie_a': {
                'count': serie_a['count'],
                'total': float(serie_a['total'] or 0)
            },
            'serie_b': {
                'count': serie_b['count'],
                'total': float(serie_b['total'] or 0)
            },
            'total': total,
            'ratio_b': round(ratio_b, 2)
        }
    
    def _audit_shrinkage(self) -> Dict[str, Any]:
        """Audita mermas y documentación."""
        week_ago = (self.report_date - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Mermas de la semana
        sql = """
            SELECT category, COUNT(*) as count, 
                   COALESCE(SUM(total_value), 0) as value,
                   COALESCE(SUM(CASE WHEN photo_path IS NOT NULL THEN 1 ELSE 0 END), 0) as documented
            FROM loss_records
            WHERE created_at::date >= %s
            GROUP BY category
        """
        by_category = list(self.core.db.execute_query(sql, (week_ago,)))
        
        total_value = sum(float(c['value'] or 0) for c in by_category)
        total_count = sum(c['count'] for c in by_category)
        documented = sum(c['documented'] for c in by_category)
        
        # Tasa de documentación
        doc_rate = (documented / total_count * 100) if total_count > 0 else 100
        
        if doc_rate < 100:
            self.alerts.append({
                'type': 'SHRINKAGE',
                'level': 'WARNING',
                'message': f"{total_count - documented} mermas sin evidencia fotográfica"
            })
        
        return {
            'period': f"{week_ago} - {self.report_date.strftime('%Y-%m-%d')}",
            'by_category': [{
                'category': c['category'],
                'count': c['count'],
                'value': float(c['value'] or 0),
                'documented': c['documented']
            } for c in by_category],
            'totals': {
                'count': total_count,
                'value': total_value,
                'documentation_rate': round(doc_rate, 1)
            }
        }
    
    def _audit_resico(self) -> Dict[str, Any]:
        """Audita estado de límites RESICO por RFC."""
        year = self.report_date.year
        limit = Decimal('3500000')
        
        # Obtener emisores
        try:
            emitters = list(self.core.db.execute_query(
                "SELECT id, rfc, razon_social FROM emitters WHERE is_active = 1"
            ))
        except Exception:
            emitters = []
        
        results = []
        total_capacity = Decimal('0')
        total_used = Decimal('0')
        
        for e in emitters:
            # Total facturado este año
            sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'A' AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
                AND status = 'completed'
            """
            result = list(self.core.db.execute_query(sql, (year,)))
            used = Decimal(str(result[0]['total'] or 0)) if result else Decimal('0')
            
            remaining = limit - used
            pct = (used / limit) * 100
            
            status = 'GREEN'
            if pct >= self.RESICO_CRITICAL:
                status = 'RED'
                self.alerts.append({
                    'type': 'RESICO',
                    'level': 'CRITICAL',
                    'message': f"RFC {e['rfc'][:4]}*** al {pct:.0f}% - CAMBIAR EMISOR INMEDIATO"
                })
            elif pct >= self.RESICO_WARNING:
                status = 'YELLOW'
                self.alerts.append({
                    'type': 'RESICO',
                    'level': 'WARNING',
                    'message': f"RFC {e['rfc'][:4]}*** al {pct:.0f}% - Considerar balanceo"
                })
            
            results.append({
                'rfc': e['rfc'][:4] + '***',
                'used': float(used),
                'remaining': float(remaining),
                'percentage': round(float(pct), 1),
                'status': status
            })
            
            total_capacity += limit
            total_used += used
        
        return {
            'year': year,
            'rfcs': results,
            'totals': {
                'capacity': float(total_capacity),
                'used': float(total_used),
                'remaining': float(total_capacity - total_used),
                'percentage': round(float((total_used / total_capacity) * 100), 1) if total_capacity > 0 else 0
            }
        }
    
    def _audit_margins(self) -> Dict[str, Any]:
        """Audita márgenes de ganancia."""
        week_ago = (self.report_date - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Calcular margen promedio
        sql = """
            SELECT 
                AVG((si.price - p.cost) / NULLIF(si.price, 0) * 100) as avg_margin,
                MIN((si.price - p.cost) / NULLIF(si.price, 0) * 100) as min_margin,
                MAX((si.price - p.cost) / NULLIF(si.price, 0) * 100) as max_margin
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.timestamp::date >= %s AND s.status = 'completed'
              AND p.cost > 0
        """
        try:
            # FIX 2026-01-30: Validar que result no esté vacío antes de acceder a [0]
            margin_result = list(self.core.db.execute_query(sql, (week_ago,)))
            if margin_result:
                margin = margin_result[0]
                avg_margin = float(margin['avg_margin'] or 20)
                min_margin = float(margin['min_margin'] or 0)
                max_margin = float(margin['max_margin'] or 50)
            else:
                avg_margin, min_margin, max_margin = 20, 0, 50
        except Exception:
            avg_margin, min_margin, max_margin = 20, 0, 50
        
        # Productos con margen negativo
        sql_negative = """
            SELECT COUNT(DISTINCT p.id) as count
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.timestamp::date >= %s
              AND si.price < p.cost AND p.cost > 0
        """
        try:
            negative_result = list(self.core.db.execute_query(sql_negative, (week_ago,)))
            negative = negative_result[0]['count'] if negative_result else 0
        except Exception:
            negative = 0
        
        if negative > 0:
            self.alerts.append({
                'type': 'MARGIN',
                'level': 'WARNING',
                'message': f"{negative} productos vendidos bajo costo esta semana"
            })
        
        return {
            'period': f"{week_ago} - {self.report_date.strftime('%Y-%m-%d')}",
            'average_margin': round(avg_margin, 2),
            'min_margin': round(min_margin, 2),
            'max_margin': round(max_margin, 2),
            'negative_margin_products': negative
        }
    
    def _generate_summary(self, report: Dict) -> Dict:
        """Genera resumen ejecutivo."""
        critical = len([a for a in self.alerts if a['level'] == 'CRITICAL'])
        warnings = len([a for a in self.alerts if a['level'] == 'WARNING'])
        
        health = 'EXCELLENT'
        if critical > 0:
            health = 'CRITICAL'
        elif warnings > 2:
            health = 'FAIR'
        elif warnings > 0:
            health = 'GOOD'
        
        return {
            'health_status': health,
            'alerts_critical': critical,
            'alerts_warning': warnings,
            'total_alerts': len(self.alerts),
            'generated_at': datetime.now().isoformat()
        }
    
    def get_printable_report(self) -> str:
        """Genera reporte en formato texto."""
        report = self.run_full_audit()
        
        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AUDITORÍA CRUZADA AUTOMÁTICA                              ║
║                    Semana {report['week']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                    ESTADO: {report['summary']['health_status']:<20}                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

📦 INVENTARIO
───────────────────────────────────────────────────────────────────────────────
   Varianza promedio:     {report['sections']['inventory']['total_variance']:.2f}%
   Tolerancia:            {self.MERMA_TOLERANCE}%

💰 VENTAS (Semana)
───────────────────────────────────────────────────────────────────────────────
   Serie A (Fiscal):      ${report['sections']['sales']['serie_a']['total']:,.2f}
   Serie B (Operativa):   ${report['sections']['sales']['serie_b']['total']:,.2f}
   Total:                 ${report['sections']['sales']['total']:,.2f}
   Ratio Serie B:         {report['sections']['sales']['ratio_b']:.1f}%

📋 MERMAS (Semana)
───────────────────────────────────────────────────────────────────────────────
   Total registradas:     {report['sections']['shrinkage']['totals']['count']}
   Valor:                 ${report['sections']['shrinkage']['totals']['value']:,.2f}
   Documentación:         {report['sections']['shrinkage']['totals']['documentation_rate']:.0f}%

📊 LÍMITES RESICO
───────────────────────────────────────────────────────────────────────────────"""
        
        for rfc in report['sections']['resico']['rfcs']:
            status_icon = '🟢' if rfc['status'] == 'GREEN' else ('🟡' if rfc['status'] == 'YELLOW' else '🔴')
            output += f"\n   {status_icon} {rfc['rfc']}: {rfc['percentage']:.0f}% (Disponible: ${rfc['remaining']:,.0f})"
        
        output += f"""

📈 MÁRGENES
───────────────────────────────────────────────────────────────────────────────
   Promedio:              {report['sections']['margins']['average_margin']:.1f}%
   Bajo costo vendidos:   {report['sections']['margins']['negative_margin_products']}
"""
        
        if report['alerts']:
            output += """
⚠️ ALERTAS
───────────────────────────────────────────────────────────────────────────────"""
            for alert in report['alerts']:
                icon = '🔴' if alert['level'] == 'CRITICAL' else '🟡'
                output += f"\n   {icon} [{alert['type']}] {alert['message']}"
        
        output += """

═══════════════════════════════════════════════════════════════════════════════
                         GENERAL DE GUERRA :: ANTIGRAVITY
═══════════════════════════════════════════════════════════════════════════════
"""
        
        return output
    
    def send_to_telegram(self, bot_token: str, chat_id: str) -> bool:
        """Envía reporte a Telegram."""
        import urllib.parse
        import urllib.request
        
        report = self.get_printable_report()
        
        # Truncar si es necesario
        if len(report) > 4000:
            report = report[:4000] + "\n... [ver completo en servidor]"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': report
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as response:
                _ = response.read()  # Consume response to release connection
            logger.info("📱 Reporte enviado a Telegram")
            return True
        except Exception as e:
            logger.error(f"Error enviando a Telegram: {e}")
            return False
    
    def save_report(self, path: str = None) -> str:
        """Guarda reporte con hash de integridad."""
        if path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            path = str(base_dir / f"docs/audits/cross_audit_{datetime.now().strftime('%Y%m%d')}.txt")
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        report = self.get_printable_report()
        Path(path).write_text(report)
        
        # Hash de integridad
        hash_value = hashlib.sha256(report.encode()).hexdigest()
        Path(path + '.sha256').write_text(hash_value)
        
        return path

# CLI
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Cross Audit - El General de Guerra')
    parser.add_argument('--telegram', nargs=2, metavar=('BOT_TOKEN', 'CHAT_ID'))
    parser.add_argument('--save', type=str, help='Path to save')
    parser.add_argument('--print', action='store_true')
    args = parser.parse_args()
    
    audit = CrossAudit()
    
    if args.print or (not args.telegram and not args.save):
        print(audit.get_printable_report())
    
    if args.telegram:
        audit.send_to_telegram(args.telegram[0], args.telegram[1])
    
    if args.save:
        path = audit.save_report(args.save)
        print(f"Guardado en: {path}")
