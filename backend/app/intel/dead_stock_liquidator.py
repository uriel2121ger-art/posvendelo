from pathlib import Path

"""
Dead-Stock Resurrection - El Liquidador Silencioso
Resucita inventario estancado mediante traslados y bundles automáticos

Funciones:
- Detecta productos sin ventas en 90 días por sucursal
- Sugiere traslados a sucursales donde sí se vende
- Crea bundles automáticos: Producto Estrella + Producto Muerto con descuento
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import sys

logger = logging.getLogger(__name__)

class DeadStockLiquidator:
    """
    Resucita inventario estancado.
    
    El Problema: Con 14,000 productos, siempre habrá "muertos" que no se mueven.
    
    La Solución:
    1. Detectar productos sin ventas en 90+ días por sucursal
    2. Comparar con otras sucursales donde sí se venden
    3. Sugerir traslados automáticos
    4. Crear bundles: Estrella + Muerto con 50% descuento
    """
    
    DEAD_THRESHOLD_DAYS = 90
    DEFAULT_BUNDLE_DISCOUNT = 50  # 50% descuento en producto muerto
    
    def __init__(self, core):
        self.core = core
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Crea tablas para bundles de resurrección."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS resurrection_bundles (
                    id BIGSERIAL PRIMARY KEY,
                    bundle_code TEXT UNIQUE NOT NULL,
                    star_product_id INTEGER NOT NULL,
                    dead_product_id INTEGER NOT NULL,
                    dead_discount_pct REAL DEFAULT 50,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    branch TEXT,
                    status TEXT DEFAULT 'active',
                    times_sold INTEGER DEFAULT 0,
                    FOREIGN KEY(star_product_id) REFERENCES products(id),
                    FOREIGN KEY(dead_product_id) REFERENCES products(id)
                )
            """)
            
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS transfer_suggestions (
                    id BIGSERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    from_branch TEXT NOT NULL,
                    to_branch TEXT NOT NULL,
                    suggested_qty INTEGER,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    executed_at TEXT,
                    FOREIGN KEY(product_id) REFERENCES products(id)
                )
            """)
        except Exception as e:
            logger.error(f"Error creating resurrection tables: {e}")
    
    def detect_dead_stock(self, days: int = None, 
                          branch: str = None) -> List[Dict[str, Any]]:
        """
        Detecta productos sin ventas en los últimos N días.
        
        Args:
            days: Días sin ventas para considerar "muerto" (default: 90)
            branch: Filtrar por sucursal específica
            
        Returns:
            Lista de productos muertos con métricas
        """
        days = days or self.DEAD_THRESHOLD_DAYS
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Query para encontrar productos sin ventas recientes
        params = [cutoff_date]
        branch_filter = ""
        if branch:
            branch_filter = "AND s.branch = %s"
            params.append(branch)
        
        sql = f"""
            SELECT p.id, p.sku, p.name, p.stock, p.cost, p.price,
                   p.department, p.category,
                   COALESCE(MAX(s.timestamp), 'never') as last_sale,
                   COALESCE(SUM(si.qty), 0) as total_sold_90d
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id AND s.status = 'completed'
                AND s.timestamp::date >= %s {branch_filter}
            WHERE p.is_active = 1 AND p.stock > 0
            GROUP BY p.id
            HAVING total_sold_90d = 0 OR last_sale = 'never'
            ORDER BY p.stock DESC, p.cost DESC
            LIMIT 100
        """
        
        result = list(self.core.db.execute_query(sql, tuple(params)))
        
        dead_products = []
        for p in result:
            stock_value = float(p['stock'] or 0) * float(p['cost'] or 0)
            
            dead_products.append({
                'product_id': p['id'],
                'sku': p['sku'],
                'name': p['name'],
                'stock': p['stock'],
                'stock_value': round(stock_value, 2),
                'cost': float(p['cost'] or 0),
                'price': float(p['price'] or 0),
                'department': p['department'],
                'category': p['category'],
                'last_sale': p['last_sale'],
                'days_dead': days,
                'branch': branch or 'todas'
            })
        
        logger.info(f"🪦 Detected {len(dead_products)} dead products (>{days} days)")
        return dead_products
    
    def suggest_transfers(self, product_id: int) -> Dict[str, Any]:
        """
        Sugiere traslados de producto a sucursales donde sí se vende.
        
        Si el producto no se mueve en Norte pero sí en Poniente,
        sugiere mover stock de Norte → Poniente.
        """
        # Obtener ventas por sucursal en últimos 90 días
        cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        sales_by_branch = list(self.core.db.execute_query("""
            SELECT s.branch, COALESCE(SUM(si.qty), 0) as total_sold
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            WHERE si.product_id = %s 
              AND s.status = 'completed'
              AND s.timestamp::date >= %s
            GROUP BY s.branch
            ORDER BY total_sold DESC
        """, (product_id, cutoff)))
        
        # Obtener producto
        product = list(self.core.db.execute_query(
            "SELECT * FROM products WHERE id = %s", (product_id,)
        ))
        
        if not product:
            return {'success': False, 'error': 'Producto no encontrado'}
        
        product = dict(product[0])
        
        # Identificar branches con ventas vs sin ventas
        selling_branches = {r['branch']: r['total_sold'] for r in sales_by_branch}
        
        # Obtener todas las sucursales
        all_branches = list(self.core.db.execute_query(
            "SELECT id, name FROM branches WHERE is_active = 1"
        ))
        
        # Branches sin ventas (candidatos a enviar stock)
        dead_branches = [
            b['name'] for b in all_branches 
            if b['name'] not in selling_branches
        ]
        
        # Mejor destino
        best_destination = None
        if selling_branches:
            best_destination = max(selling_branches, key=selling_branches.get)
        
        # Crear sugerencias
        suggestions = []
        if best_destination and dead_branches:
            for from_branch in dead_branches:
                suggestions.append({
                    'from_branch': from_branch,
                    'to_branch': best_destination,
                    'reason': f"Producto vendió {selling_branches[best_destination]} unidades en {best_destination}, 0 en {from_branch}"
                })
                
                # Guardar sugerencia
                self.core.db.execute_write("""
                    INSERT INTO transfer_suggestions 
                    (product_id, from_branch, to_branch, reason)
                    VALUES (%s, %s, %s, %s)
                """, (product_id, from_branch, best_destination, suggestions[-1]['reason']))
        
        return {
            'success': True,
            'product': product['name'],
            'product_id': product_id,
            'selling_branches': selling_branches,
            'dead_branches': dead_branches,
            'suggestions': suggestions,
            'total_stock': product['stock']
        }
    
    def create_resurrection_bundle(self, dead_product_id: int, 
                                    star_product_id: int = None,
                                    discount_pct: float = None,
                                    branch: str = None) -> Dict[str, Any]:
        """
        Crea un Bundle de Resurrección.
        
        "Compra el Producto A (Estrella) y llévate el Producto B (Muerto) 
        con 50% de descuento"
        
        Args:
            dead_product_id: Producto muerto a liquidar
            star_product_id: Producto estrella (auto-detecta si no se especifica)
            discount_pct: Porcentaje de descuento (default: 50%)
            branch: Sucursal donde aplicar el bundle
        """
        discount_pct = discount_pct or self.DEFAULT_BUNDLE_DISCOUNT
        
        # Obtener producto muerto
        dead_product = list(self.core.db.execute_query(
            "SELECT * FROM products WHERE id = %s", (dead_product_id,)
        ))
        
        if not dead_product:
            return {'success': False, 'error': 'Producto muerto no encontrado'}
        
        dead_product = dict(dead_product[0])
        
        # Si no hay estrella especificada, buscar mejor producto de la misma categoría
        if not star_product_id:
            star_product_id = self._find_star_product(
                dead_product.get('category') or dead_product.get('department'),
                exclude_id=dead_product_id
            )
        
        if not star_product_id:
            return {'success': False, 'error': 'No se encontró producto estrella compatible'}
        
        # Obtener producto estrella
        star_product = list(self.core.db.execute_query(
            "SELECT * FROM products WHERE id = %s", (star_product_id,)
        ))
        
        if not star_product:
            return {'success': False, 'error': 'Producto estrella no encontrado'}
        
        star_product = dict(star_product[0])
        
        # Generar código del bundle
        bundle_code = f"RSRCT-{dead_product_id}-{star_product_id}-{datetime.now().strftime('%Y%m%d')}"
        
        # Calcular precio del bundle
        star_price = float(star_product['price'] or 0)
        dead_price = float(dead_product['price'] or 0)
        dead_discounted = dead_price * (1 - discount_pct / 100)
        bundle_price = star_price + dead_discounted
        
        # Crear bundle
        try:
            self.core.db.execute_write("""
                INSERT INTO resurrection_bundles 
                (bundle_code, star_product_id, dead_product_id, 
                 dead_discount_pct, branch, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                bundle_code, 
                star_product_id, 
                dead_product_id, 
                discount_pct,
                branch,
                (datetime.now() + timedelta(days=30)).isoformat()
            ))
            
            logger.info(f"🔥 Bundle creado: {bundle_code}")
            
            return {
                'success': True,
                'bundle_code': bundle_code,
                'star_product': {
                    'id': star_product_id,
                    'name': star_product['name'],
                    'price': star_price
                },
                'dead_product': {
                    'id': dead_product_id,
                    'name': dead_product['name'],
                    'original_price': dead_price,
                    'discounted_price': round(dead_discounted, 2),
                    'discount_pct': discount_pct
                },
                'bundle_price': round(bundle_price, 2),
                'savings': round(dead_price - dead_discounted, 2),
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat(),
                'cashier_prompt': f"🔥 OFERTA: Llévate {dead_product['name']} con {discount_pct}% de descuento si compras {star_product['name']}"
            }
            
        except Exception as e:
            logger.error(f"Error creating bundle: {e}")
            return {'success': False, 'error': str(e)}
    
    def _find_star_product(self, category: str, exclude_id: int = None) -> Optional[int]:
        """
        Encuentra el producto más vendido de una categoría.
        """
        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        exclude_clause = ""
        params = [cutoff]
        
        if category:
            exclude_clause = "AND (p.category = %s OR p.department = %s)"
            params.extend([category, category])
        
        if exclude_id:
            exclude_clause += " AND p.id != %s"
            params.append(exclude_id)
        
        sql = f"""
            SELECT p.id, COALESCE(SUM(si.qty), 0) as total_sold
            FROM products p
            JOIN sale_items si ON p.id = si.product_id
            JOIN sales s ON si.sale_id = s.id
            WHERE s.status = 'completed'
              AND s.timestamp::date >= %s
              AND p.stock > 0
              {exclude_clause}
            GROUP BY p.id
            ORDER BY total_sold DESC
            LIMIT 1
        """
        
        result = list(self.core.db.execute_query(sql, tuple(params)))
        
        if result:
            return result[0]['id']
        return None
    
    def get_action_plan(self, branch: str = None) -> Dict[str, Any]:
        """
        Genera plan de acción completo para resucitar inventario muerto.
        
        Returns:
            Plan con:
            - Lista de productos muertos
            - Sugerencias de traslado
            - Bundles recomendados
            - Valor total a recuperar
        """
        # 1. Detectar productos muertos
        dead_stock = self.detect_dead_stock(branch=branch)
        
        if not dead_stock:
            return {
                'success': True,
                'message': '✅ No hay inventario muerto detectado!',
                'dead_count': 0,
                'dead_value': 0,
                'transfers': [],
                'bundles': []
            }
        
        # 2. Para los top 10, generar sugerencias
        transfers = []
        bundles_suggested = []
        
        for product in dead_stock[:10]:
            # Sugerencia de traslado
            transfer = self.suggest_transfers(product['product_id'])
            if transfer.get('suggestions'):
                transfers.extend(transfer['suggestions'])
            
            # Sugerencia de bundle (auto-find star)
            bundle_preview = {
                'dead_product': product['name'],
                'dead_product_id': product['product_id'],
                'stock_value': product['stock_value'],
                'action': 'create_resurrection_bundle',
                'suggested_discount': self.DEFAULT_BUNDLE_DISCOUNT
            }
            bundles_suggested.append(bundle_preview)
        
        # Calcular valor total muerto
        total_dead_value = sum(p['stock_value'] for p in dead_stock)
        
        return {
            'success': True,
            'summary': f"🪦 {len(dead_stock)} productos muertos detectados",
            'dead_count': len(dead_stock),
            'dead_value': round(total_dead_value, 2),
            'dead_products': dead_stock[:20],  # Top 20
            'transfers': transfers,
            'bundles_suggested': bundles_suggested,
            'narrative': self._build_narrative(dead_stock, total_dead_value, transfers)
        }
    
    def _build_narrative(self, dead_stock: List, total_value: float, 
                         transfers: List) -> str:
        """Construye narrativa ejecutiva del plan."""
        lines = [
            f"Mano, tienes ${total_value:,.0f} en inventario muerto.",
            f"Son {len(dead_stock)} productos sin movimiento en 90+ días.",
            ""
        ]
        
        if transfers:
            lines.append(f"🚚 Tengo {len(transfers)} sugerencias de traslado entre sucursales.")
        
        if dead_stock:
            top = dead_stock[0]
            lines.append(f"💀 El más crítico: {top['name']} ({top['stock']} unidades, ${top['stock_value']:,.0f})")
            lines.append(f"   Sugerencia: Vincularlo con un producto estrella en bundle con 50% descuento.")
        
        lines.append("")
        lines.append("Acción sugerida: Ejecutar bundles para los top 5 productos y aprobar traslados.")
        
        return "\n".join(lines)
    
    def get_active_bundles(self) -> List[Dict]:
        """Obtiene bundles de resurrección activos."""
        result = list(self.core.db.execute_query("""
            SELECT rb.*, 
                   sp.name as star_name, sp.price as star_price,
                   dp.name as dead_name, dp.price as dead_price, dp.stock as dead_stock
            FROM resurrection_bundles rb
            JOIN products sp ON rb.star_product_id = sp.id
            JOIN products dp ON rb.dead_product_id = dp.id
            WHERE rb.status = 'active'
              AND (rb.expires_at IS NULL OR rb.expires_at > NOW())
            ORDER BY rb.created_at DESC
        """))
        
        return [dict(r) for r in result]

# Funciones de conveniencia
def detect_dead_stock(core, days=90, branch=None):
    """Detecta inventario muerto."""
    return DeadStockLiquidator(core).detect_dead_stock(days, branch)

def get_resurrection_plan(core, branch=None):
    """Obtiene plan completo de resurrección."""
    return DeadStockLiquidator(core).get_action_plan(branch)

def create_bundle(core, dead_id, star_id=None, discount=50):
    """Crea bundle de resurrección."""
    return DeadStockLiquidator(core).create_resurrection_bundle(dead_id, star_id, discount)
