from pathlib import Path

"""
Supplier Matcher - Optimizador de Compras A/B
Algoritmo de decisión para compras fiscales vs efectivo
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import sys

logger = logging.getLogger(__name__)

class SupplierMatcher:
    """
    Sistema de optimización de compras Serie A vs Serie B.
    
    Analiza:
    - Flujo de efectivo actual
    - Precios con factura vs sin factura
    - Ahorro real considerando IVA
    - Proyección de margen neto
    """
    
    IVA_RATE = 0.16  # 16% IVA México
    
    def __init__(self, core):
        self.core = core
    
    def analyze_purchase(self, 
                        product_id: int,
                        quantity: int,
                        price_a: float,
                        price_b: float,
                        supplier_a: str = "Proveedor Factura",
                        supplier_b: str = "Proveedor Efectivo") -> Dict[str, Any]:
        """
        Analiza qué opción de compra es más conveniente.
        
        Args:
            product_id: ID del producto
            quantity: Cantidad a comprar
            price_a: Precio unitario CON factura
            price_b: Precio unitario SIN factura (efectivo)
            supplier_a: Nombre proveedor fiscal
            supplier_b: Nombre proveedor efectivo
        
        Returns:
            Análisis completo con recomendación
        """
        # Calcular costos totales
        cost_a_base = price_a * quantity
        cost_a_with_iva = cost_a_base * (1 + self.IVA_RATE)
        cost_b = price_b * quantity
        
        # Ahorro real: (Precio A con IVA) - (Precio B)
        real_saving = cost_a_with_iva - cost_b
        saving_percentage = (real_saving / cost_a_with_iva) * 100 if cost_a_with_iva > 0 else 0
        
        # Obtener flujo de efectivo actual
        cash_flow = self._get_cash_flow_status()
        
        # Determinar recomendación
        recommendation = self._get_recommendation(
            cost_b, cash_flow, saving_percentage
        )
        
        # Obtener datos del producto
        product = self._get_product(product_id)
        
        # Calcular impacto en margen
        margin_impact = self._calculate_margin_impact(
            product, quantity, price_a, price_b
        )
        
        return {
            'product': {
                'id': product_id,
                'name': product.get('name', 'Producto'),
                'current_stock': product.get('stock', 0),
                'current_cost': float(product.get('cost', 0))
            },
            'quantity': quantity,
            
            'option_a': {
                'supplier': supplier_a,
                'unit_price': price_a,
                'subtotal': cost_a_base,
                'iva': cost_a_base * self.IVA_RATE,
                'total': cost_a_with_iva,
                'type': 'Serie A (Fiscal)'
            },
            
            'option_b': {
                'supplier': supplier_b,
                'unit_price': price_b,
                'total': cost_b,
                'type': 'Serie B (Efectivo)'
            },
            
            'savings': {
                'absolute': real_saving,
                'percentage': round(saving_percentage, 1),
                'formula': f"({price_a} × 1.16) - {price_b} = {real_saving/quantity:.2f} por unidad"
            },
            
            'cash_flow': cash_flow,
            
            'margin_impact': margin_impact,
            
            'recommendation': recommendation
        }
    
    def _get_cash_flow_status(self) -> Dict[str, Any]:
        """Obtiene estado actual del flujo de efectivo."""
        try:
            # Efectivo Serie B disponible
            serie_b_cash = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(s.total), 0) as total
                FROM sales s
                WHERE s.serie = 'B' 
                AND s.payment_method IN ('cash', 'efectivo')
                AND s.timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
            """))
            
            # Gastos Serie B
            gastos_b = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(amount), 0) as total
                FROM expenses
                WHERE serie = 'B'
                AND expense_date::date >= CURRENT_DATE - INTERVAL '30 days'
            """))
            
            cash_b = (float(serie_b_cash[0]['total'] or 0) if serie_b_cash else 0) - (float(gastos_b[0]['total'] or 0) if gastos_b else 0)
            
            # Efectivo Serie A en banco
            serie_a = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales WHERE serie = 'A'
                AND timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
            """))
            
            cash_a = float(serie_a[0]['total'] or 0) if serie_a else 0
            
            # Determinar si hay exceso de efectivo B
            total = cash_a + cash_b
            ratio_b = (cash_b / total * 100) if total > 0 else 0
            
            return {
                'serie_a_available': cash_a,
                'serie_b_available': cash_b,
                'total': total,
                'ratio_b_percentage': round(ratio_b, 1),
                'excess_cash_b': cash_b > 50000,  # Exceso si > 50k
                'status': 'excess_b' if ratio_b > 60 else 'balanced' if ratio_b > 40 else 'excess_a'
            }
            
        except Exception as e:
            logger.error(f"Error getting cash flow: {e}")
            return {
                'serie_a_available': 0,
                'serie_b_available': 0,
                'total': 0,
                'ratio_b_percentage': 50,
                'excess_cash_b': False,
                'status': 'unknown'
            }
    
    def _get_recommendation(self, 
                           cost_b: float, 
                           cash_flow: Dict, 
                           saving_pct: float) -> Dict[str, Any]:
        """Genera recomendación de compra."""
        
        # Si hay exceso de efectivo B y el ahorro es significativo
        if cash_flow.get('excess_cash_b') and saving_pct >= 5:
            return {
                'action': 'BUY_B',
                'confidence': 'high',
                'reason': f"Tienes exceso de efectivo Serie B (${cash_flow['serie_b_available']:,.0f}). "
                         f"Comprar sin factura te ahorra {saving_pct:.1f}%.",
                'message': f"💰 Compra al proveedor de efectivo. Ahorro: ${cost_b * saving_pct/100:,.0f}"
            }
        
        # Si el ahorro es muy significativo (>15%)
        elif saving_pct >= 15:
            return {
                'action': 'BUY_B',
                'confidence': 'medium',
                'reason': f"El ahorro de {saving_pct:.1f}% es muy significativo (incluye 16% IVA).",
                'message': "💡 El precio de efectivo justifica usar reservas Serie B."
            }
        
        # Si el flujo está balanceado, depende del ahorro
        elif saving_pct >= 8:
            return {
                'action': 'BUY_B',
                'confidence': 'medium',
                'reason': f"Ahorro moderado de {saving_pct:.1f}%, flujo balanceado.",
                'message': "📊 Considera comprar en efectivo si tienes liquidez."
            }
        
        # Si necesitas deducciones fiscales
        elif cash_flow.get('status') == 'excess_a':
            return {
                'action': 'BUY_A',
                'confidence': 'high',
                'reason': "Tienes margen fiscal disponible. La factura te da deducción.",
                'message': "📋 Compra con factura para optimizar deducciones."
            }
        
        # Default: depende del contexto
        else:
            return {
                'action': 'EITHER',
                'confidence': 'low',
                'reason': f"Ahorro bajo ({saving_pct:.1f}%). Decide según disponibilidad.",
                'message': "🤔 Ambas opciones son similares. Decide por conveniencia."
            }
    
    def _get_product(self, product_id: int) -> Dict:
        """Obtiene datos del producto."""
        products = list(self.core.db.execute_query("""
            SELECT * FROM products WHERE id = %s
        """, (product_id,)))
        
        return dict(products[0]) if products else {}
    
    def _calculate_margin_impact(self, 
                                 product: Dict, 
                                 quantity: int,
                                 price_a: float, 
                                 price_b: float) -> Dict[str, Any]:
        """Calcula impacto en margen de cada opción."""
        sale_price = float(product.get('price', 0))
        
        if sale_price == 0:
            return {'current_margin': 0, 'margin_if_a': 0, 'margin_if_b': 0}
        
        # Margen actual
        current_cost = float(product.get('cost', 0))
        current_margin = ((sale_price - current_cost) / sale_price) * 100
        
        # Margen si compras con factura (costo = precio sin IVA)
        margin_a = ((sale_price - price_a) / sale_price) * 100
        
        # Margen si compras en efectivo
        margin_b = ((sale_price - price_b) / sale_price) * 100
        
        return {
            'current_margin': round(current_margin, 1),
            'margin_if_a': round(margin_a, 1),
            'margin_if_b': round(margin_b, 1),
            'improvement_b_vs_a': round(margin_b - margin_a, 1)
        }
    
    def bulk_analyze(self, items: List[Dict]) -> Dict[str, Any]:
        """
        Analiza múltiples productos para compra óptima.
        
        Args:
            items: Lista de {product_id, quantity, price_a, price_b}
        
        Returns:
            Análisis consolidado con totales
        """
        analyses = []
        total_if_a = 0
        total_if_b = 0
        
        for item in items:
            analysis = self.analyze_purchase(
                item['product_id'],
                item['quantity'],
                item['price_a'],
                item['price_b']
            )
            analyses.append(analysis)
            total_if_a += analysis['option_a']['total']
            total_if_b += analysis['option_b']['total']
        
        total_saving = total_if_a - total_if_b
        
        return {
            'items': analyses,
            'summary': {
                'total_if_serie_a': total_if_a,
                'total_if_serie_b': total_if_b,
                'total_saving': total_saving,
                'saving_percentage': round((total_saving / total_if_a) * 100, 1) if total_if_a > 0 else 0
            },
            'recommendation': f"Comprar todo en Serie B te ahorra ${total_saving:,.0f}" if total_saving > 0 else "Considera mezclar según disponibilidad"
        }

# Función de conveniencia
def analyze_supplier_options(core, product_id, qty, price_a, price_b):
    """Wrapper para análisis rápido."""
    matcher = SupplierMatcher(core)
    return matcher.analyze_purchase(product_id, qty, price_a, price_b)
