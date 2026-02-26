"""
Supplier Matcher - Optimizador de Compras A/B
Algoritmo de decisión para compras fiscales vs efectivo
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging

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
    
    def __init__(self, db):
        self.db = db
    
    async def analyze_purchase(self, 
                        product_id: int,
                        quantity: int,
                        price_a: float,
                        price_b: float,
                        supplier_a: str = "Proveedor Factura",
                        supplier_b: str = "Proveedor Efectivo") -> Dict[str, Any]:
        """Analiza qué opción de compra es más conveniente."""
        cost_a_base = price_a * quantity
        cost_a_with_iva = cost_a_base * (1 + self.IVA_RATE)
        cost_b = price_b * quantity
        
        real_saving = cost_a_with_iva - cost_b
        saving_percentage = (real_saving / cost_a_with_iva) * 100 if cost_a_with_iva > 0 else 0
        
        cash_flow = await self._get_cash_flow_status()
        recommendation = self._get_recommendation(cost_b, cash_flow, saving_percentage)
        
        product = await self._get_product(product_id)
        margin_impact = self._calculate_margin_impact(product, quantity, price_a, price_b)
        
        return {
            'product': {
                'id': product_id,
                'name': product.get('name', 'Producto'),
                'current_stock': product.get('stock', 0),
                'current_cost': round(float(product.get('cost', 0)), 2)
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
    
    async def _get_cash_flow_status(self) -> Dict[str, Any]:
        try:
            row_b = await self.db.fetchrow("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales 
                WHERE serie = 'B' AND payment_method IN ('cash', 'efectivo') AND timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            
            # Using try/except for expenses in case the table doesn't exist
            try:
                row_exp = await self.db.fetchrow("""
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM cash_expenses
                    WHERE expense_date >= CURRENT_DATE - INTERVAL '30 days'
                """)
                gastos_b = round(float(row_exp['total'] or 0), 2) if row_exp else 0
            except Exception:
                gastos_b = 0
            
            cash_b = (round(float(row_b['total'] or 0), 2) if row_b else 0) - gastos_b
            
            row_a = await self.db.fetchrow("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales WHERE serie = 'A' AND timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            cash_a = round(float(row_a['total'] or 0), 2) if row_a else 0
            
            total = cash_a + cash_b
            ratio_b = (cash_b / total * 100) if total > 0 else 0
            
            return {
                'serie_a_available': cash_a,
                'serie_b_available': cash_b,
                'total': total,
                'ratio_b_percentage': round(ratio_b, 1),
                'excess_cash_b': cash_b > 50000,
                'status': 'excess_b' if ratio_b > 60 else 'balanced' if ratio_b > 40 else 'excess_a'
            }
        except Exception as e:
            logger.error(f"Error getting cash flow: {e}")
            return {'serie_a_available': 0, 'serie_b_available': 0, 'total': 0, 'ratio_b_percentage': 50, 'excess_cash_b': False, 'status': 'unknown'}
    
    def _get_recommendation(self, cost_b: float, cash_flow: Dict, saving_pct: float) -> Dict[str, Any]:
        if cash_flow.get('excess_cash_b') and saving_pct >= 5:
            return {'action': 'BUY_B', 'confidence': 'high', 'reason': f"Exceso efectivo B (${cash_flow['serie_b_available']:,.0f}). Ahorro {saving_pct:.1f}%.", 'message': f"💰 Compra en efectivo. Ahorro: ${cost_b * saving_pct/100:,.0f}"}
        elif saving_pct >= 15:
            return {'action': 'BUY_B', 'confidence': 'medium', 'reason': f"Ahorro de {saving_pct:.1f}% es muy significativo.", 'message': "💡 El precio justifica usar efectivo Serie B."}
        elif saving_pct >= 8:
            return {'action': 'BUY_B', 'confidence': 'medium', 'reason': f"Ahorro moderado {saving_pct:.1f}%.", 'message': "📊 Considera efectivo si hay liquidez."}
        elif cash_flow.get('status') == 'excess_a':
            return {'action': 'BUY_A', 'confidence': 'high', 'reason': "Margen fiscal habilitado.", 'message': "📋 Compra con factura para deducciones."}
        return {'action': 'EITHER', 'confidence': 'low', 'reason': f"Ahorro bajo ({saving_pct:.1f}%).", 'message': "🤔 Estima tu conveniencia."}
    
    async def _get_product(self, product_id: int) -> Dict:
        row = await self.db.fetchrow("SELECT * FROM products WHERE id = :pid", pid=product_id)
        return dict(row) if row else {}
    
    def _calculate_margin_impact(self, product: Dict, quantity: int, price_a: float, price_b: float) -> Dict[str, Any]:
        sale_price = round(float(product.get('price', 0)), 2)
        if sale_price == 0: return {'current_margin': 0, 'margin_if_a': 0, 'margin_if_b': 0}
        
        current_cost = round(float(product.get('cost', 0)), 2)
        return {
            'current_margin': ((sale_price - current_cost) / sale_price) * 100,
            'margin_if_a': ((sale_price - price_a) / sale_price) * 100,
            'margin_if_b': ((sale_price - price_b) / sale_price) * 100
        }
