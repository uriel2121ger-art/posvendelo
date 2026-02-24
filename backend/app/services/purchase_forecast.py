from pathlib import Path

"""
Purchase Forecast - Cerebro de Compras con predicción AI
Predice cuándo se agotarán productos basado en patrones de venta
"""

from typing import Any, Dict, List
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import statistics
import sys

logger = logging.getLogger(__name__)

class PurchaseForecast:
    """
    Motor de predicción de compras.
    Analiza patrones de venta para predecir agotamiento de stock.
    """
    
    # Configuración
    ANALYSIS_DAYS = 30     # Días a analizar
    FORECAST_DAYS = 14     # Días a predecir
    SAFETY_STOCK_DAYS = 3  # Días de stock de seguridad
    LEAD_TIME_DAYS = 2     # Tiempo de entrega del proveedor
    
    def __init__(self, core):
        self.core = core
    
    def analyze_product(self, product_id: int) -> Dict[str, Any]:
        """Analiza patrón de venta de un producto."""
        # Ventas de los últimos 30 días
        since = (datetime.now() - timedelta(days=self.ANALYSIS_DAYS)).strftime('%Y-%m-%d')
        
        daily_sales = list(self.core.db.execute_query("""
            SELECT CAST(s.timestamp AS DATE) as sale_date, 
                   COALESCE(SUM(si.qty), 0) as qty
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE si.product_id = %s
              AND s.timestamp::date >= %s
              AND s.status = 'completed'
            GROUP BY s.timestamp::date
            ORDER BY sale_date
        """, (product_id, since)))
        
        if not daily_sales:
            return {
                'product_id': product_id,
                'has_data': False,
                'message': 'Sin ventas en el período'
            }
        
        # Calcular estadísticas
        quantities = [float(d['qty']) for d in daily_sales]
        
        avg_daily = statistics.mean(quantities)
        std_dev = statistics.stdev(quantities) if len(quantities) > 1 else 0
        
        # Obtener stock actual
        product = list(self.core.db.execute_query(
            "SELECT name, stock, min_stock FROM products WHERE id = %s",
            (product_id,)
        ))
        
        if not product:
            return {'product_id': product_id, 'has_data': False}
        
        current_stock = float(product[0]['stock'] or 0)
        
        # Calcular días hasta agotamiento
        if avg_daily > 0:
            days_until_stockout = current_stock / avg_daily
        else:
            days_until_stockout = float('inf')
        
        # Fecha estimada de agotamiento
        if days_until_stockout < 365:
            stockout_date = (datetime.now() + timedelta(days=days_until_stockout)).strftime('%Y-%m-%d')
        else:
            stockout_date = None
        
        # Calcular recomendación de compra
        reorder_point = avg_daily * (self.SAFETY_STOCK_DAYS + self.LEAD_TIME_DAYS)
        
        # Cantidad recomendada (para 2 semanas)
        recommended_qty = max(0, (avg_daily * self.FORECAST_DAYS) - current_stock + reorder_point)
        
        return {
            'product_id': product_id,
            'product_name': product[0]['name'],
            'has_data': True,
            'current_stock': current_stock,
            'avg_daily_sales': round(avg_daily, 2),
            'std_deviation': round(std_dev, 2),
            'days_until_stockout': round(days_until_stockout, 1),
            'stockout_date': stockout_date,
            'reorder_point': round(reorder_point, 0),
            'recommended_order': round(recommended_qty, 0),
            'urgency': self._get_urgency(days_until_stockout)
        }
    
    def _get_urgency(self, days: float) -> str:
        """Determina urgencia de compra."""
        if days <= self.LEAD_TIME_DAYS:
            return 'CRITICAL'  # Ya no hay tiempo
        elif days <= (self.LEAD_TIME_DAYS + self.SAFETY_STOCK_DAYS):
            return 'URGENT'    # Pedir hoy
        elif days <= 7:
            return 'SOON'      # Esta semana
        elif days <= 14:
            return 'PLANNED'   # Próxima semana
        else:
            return 'OK'        # Sin prisa
    
    def get_critical_products(self, branch_id: int = None, include_zero_stock: bool = True) -> List[Dict]:
        """Obtiene productos que necesitan reabastecimiento urgente."""
        
        results = []
        
        # 1. Productos con stock 0 (SIEMPRE críticos si han tenido ventas)
        if include_zero_stock:
            sql_zero = """
                SELECT DISTINCT p.id, p.name, p.stock, p.min_stock
                FROM products p
                JOIN sale_items si ON si.product_id = p.id
                JOIN sales s ON si.sale_id = s.id
                WHERE p.stock <= 0 
                  AND p.is_active = 1
                  AND s.timestamp::timestamp >= NOW() - INTERVAL '60 days'
                ORDER BY p.name
                LIMIT 100
            """
            zero_stock = list(self.core.db.execute_query(sql_zero))
            
            for p in zero_stock:
                analysis = self.analyze_product(p['id'])
                if analysis.get('has_data'):
                    analysis['urgency'] = 'CRITICAL'  # Forzar crítico si está en 0
                    results.append(analysis)
        
        # 2. Productos con stock bajo (según min_stock)
        sql_low = """
            SELECT id, name, stock, min_stock
            FROM products
            WHERE stock <= min_stock * 1.5
              AND stock > 0
              AND min_stock > 0
              AND is_active = 1
            ORDER BY (stock / NULLIF(min_stock, 0)) ASC
            LIMIT 50
        """
        
        low_stock = list(self.core.db.execute_query(sql_low))
        
        for p in low_stock:
            # Evitar duplicados
            if any(r['product_id'] == p['id'] for r in results):
                continue
            analysis = self.analyze_product(p['id'])
            if analysis.get('has_data') and analysis.get('urgency') in ['CRITICAL', 'URGENT', 'SOON']:
                results.append(analysis)
        
        # Ordenar por urgencia
        urgency_order = {'CRITICAL': 0, 'URGENT': 1, 'SOON': 2, 'PLANNED': 3, 'OK': 4}
        results.sort(key=lambda x: urgency_order.get(x['urgency'], 99))
        
        return results
    
    def generate_purchase_list(self, branch_id: int = None) -> Dict[str, Any]:
        """Genera lista de compras sugerida."""
        critical = self.get_critical_products(branch_id)
        
        # Agrupar por proveedor (si existe la relación)
        by_supplier = defaultdict(list)
        no_supplier = []
        
        for p in critical:
            # Buscar proveedor
            supplier = list(self.core.db.execute_query("""
                SELECT s.id, s.name FROM suppliers s
                JOIN products p ON p.supplier_id = s.id
                WHERE p.id = %s
            """, (p['product_id'],)))
            
            if supplier:
                by_supplier[supplier[0]['name']].append(p)
            else:
                no_supplier.append(p)
        
        # Calcular totales
        total_items = len(critical)
        critical_count = len([p for p in critical if p['urgency'] == 'CRITICAL'])
        
        return {
            'generated_at': datetime.now().isoformat(),
            'total_items': total_items,
            'critical_count': critical_count,
            'by_supplier': dict(by_supplier),
            'no_supplier': no_supplier,
            'summary': self._generate_summary_text(critical)
        }
    
    def _generate_summary_text(self, products: List[Dict]) -> str:
        """Genera resumen en texto para notificación."""
        if not products:
            return "✅ Stock saludable, sin compras urgentes"
        
        critical = [p for p in products if p['urgency'] == 'CRITICAL']
        urgent = [p for p in products if p['urgency'] == 'URGENT']
        
        lines = []
        
        if critical:
            lines.append(f"🔴 {len(critical)} productos CRÍTICOS (agotados o por agotar)")
            for p in critical[:3]:
                lines.append(f"   • {p['product_name']}: Pedir {p['recommended_order']:.0f} uds")
        
        if urgent:
            lines.append(f"🟡 {len(urgent)} productos URGENTES (pedir hoy)")
            for p in urgent[:3]:
                lines.append(f"   • {p['product_name']}: {p['days_until_stockout']:.0f} días stock")
        
        return "\n".join(lines)
    
    def get_weekly_forecast(self, top_n: int = 20) -> List[Dict]:
        """Pronóstico semanal de productos más vendidos."""
        # Top productos de la última semana
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        top_products = list(self.core.db.execute_query("""
            SELECT p.id, p.name, p.stock, COALESCE(SUM(si.qty), 0) as weekly_sales
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.timestamp::timestamp >= %s::date AND s.status = 'completed'
            GROUP BY p.id
            ORDER BY weekly_sales DESC
            LIMIT %s
        """, (week_ago, top_n)))
        
        forecasts = []
        for p in top_products:
            avg_daily = float(p['weekly_sales']) / 7
            current = float(p['stock'] or 0)
            
            # Proyectar próxima semana
            projected_end = current - (avg_daily * 7)
            need_reorder = projected_end < (avg_daily * self.SAFETY_STOCK_DAYS)
            
            forecasts.append({
                'product_id': p['id'],
                'name': p['name'],
                'current_stock': current,
                'weekly_sales': float(p['weekly_sales']),
                'avg_daily': round(avg_daily, 2),
                'projected_end_week': round(max(0, projected_end), 0),
                'need_reorder': need_reorder,
                'recommended_order': round(avg_daily * 14, 0) if need_reorder else 0
            })
        
        return forecasts
    
    def get_alert_message(self) -> str:
        """Genera mensaje de alerta para PWA/Telegram."""
        critical = self.get_critical_products()
        
        if not critical:
            return "✅ Inventario saludable"
        
        message = f"⚠️ ALERTA DE INVENTARIO\n"
        message += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        
        for p in critical[:5]:
            icon = "🔴" if p['urgency'] == 'CRITICAL' else "🟡"
            message += f"{icon} {p['product_name']}\n"
            message += f"   Stock: {p['current_stock']:.0f} | "
            message += f"Días: {p['days_until_stockout']:.0f} | "
            message += f"Pedir: {p['recommended_order']:.0f}\n\n"
        
        if len(critical) > 5:
            message += f"... y {len(critical) - 5} productos más\n"
        
        return message
    
    def get_purchase_recommendations(self, limit: int = 20) -> List[Dict]:
        """
        Genera lista simplificada de recomendaciones de compra.
        
        Returns:
            Lista de productos con cantidad recomendada a ordenar
        """
        critical = self.get_critical_products()[:limit]
        
        recommendations = []
        for p in critical:
            if p.get('recommended_order', 0) > 0:
                recommendations.append({
                    'product_id': p.get('product_id'),
                    'sku': p.get('sku', ''),
                    'name': p.get('product_name', ''),
                    'current_stock': p.get('current_stock', 0),
                    'min_stock': p.get('min_stock', 0),
                    'recommended_qty': round(p.get('recommended_order', 0)),
                    'days_remaining': p.get('days_until_stockout', 0),
                    'urgency': p.get('urgency', 'UNKNOWN'),
                    'daily_sales': p.get('daily_sales', 0),
                })
        
        return recommendations

