from pathlib import Path

"""
Cross-Sell AI Oracle + Executive Narrative AI
Venta cruzada inteligente y briefings ejecutivos
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import random
import sys

logger = logging.getLogger(__name__)

class CrossSellOracle:
    """
    Oráculo de Venta Cruzada con IA.
    
    Analiza 14,000 productos para detectar
    qué productos "viajan juntos".
    
    "80% de probabilidad si ofrece producto Y ahora"
    """
    
    def __init__(self, core):
        self.core = core
        self.association_cache = {}
    
    def build_associations(self, min_support: float = 0.01, 
                          min_confidence: float = 0.5) -> Dict[int, List[Dict]]:
        """
        Construye reglas de asociación.
        
        Algoritmo simplified Apriori.
        """
        try:
            # Obtener transacciones recientes (últimos 3 meses)
            transactions = list(self.core.db.execute_query("""
                SELECT sale_id, product_id
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.timestamp >= CURRENT_DATE - INTERVAL '90 days'
            """))
            
            # Agrupar productos por transacción
            baskets = {}
            for row in transactions:
                sid = row['sale_id']
                if sid not in baskets:
                    baskets[sid] = set()
                baskets[sid].add(row['product_id'])
            
            # Calcular frecuencias de pares
            pair_counts = {}
            single_counts = {}
            
            for basket in baskets.values():
                items = list(basket)
                for item in items:
                    single_counts[item] = single_counts.get(item, 0) + 1
                
                for i, item_a in enumerate(items):
                    for item_b in items[i+1:]:
                        pair = tuple(sorted([item_a, item_b]))
                        pair_counts[pair] = pair_counts.get(pair, 0) + 1
            
            total_baskets = len(baskets)
            
            if total_baskets == 0:
                return {}
            
            # Calcular confidence para cada par
            associations = {}
            
            for pair, count in pair_counts.items():
                support = count / total_baskets

                if support >= min_support:
                    item_a, item_b = pair
                    count_a = single_counts.get(item_a, 0)
                    count_b = single_counts.get(item_b, 0)

                    # Skip if either count is zero to avoid division by zero
                    if count_a == 0 or count_b == 0:
                        continue

                    # Confidence A → B
                    conf_ab = count / count_a
                    if conf_ab >= min_confidence:
                        if item_a not in associations:
                            associations[item_a] = []
                        lift_ab = conf_ab / (count_b / total_baskets)
                        associations[item_a].append({
                            'product_id': item_b,
                            'confidence': round(conf_ab * 100, 1),
                            'support': round(support * 100, 2),
                            'lift': lift_ab
                        })

                    # Confidence B → A
                    conf_ba = count / count_b
                    if conf_ba >= min_confidence:
                        if item_b not in associations:
                            associations[item_b] = []
                        lift_ba = conf_ba / (count_a / total_baskets)
                        associations[item_b].append({
                            'product_id': item_a,
                            'confidence': round(conf_ba * 100, 1),
                            'support': round(support * 100, 2),
                            'lift': lift_ba
                        })
            
            # Ordenar por confidence
            for pid in associations:
                associations[pid].sort(key=lambda x: x['confidence'], reverse=True)
            
            self.association_cache = associations
            logger.info(f"Cross-Sell: {len(associations)} productos con asociaciones")
            
            return associations
            
        except Exception as e:
            logger.error(f"Error building associations: {e}")
            return {}
    
    def get_suggestions(self, product_id: int, top_n: int = 3) -> List[Dict]:
        """
        Obtiene sugerencias de venta cruzada para un producto.
        """
        if not self.association_cache:
            self.build_associations()
        
        suggestions = self.association_cache.get(product_id, [])[:top_n]
        
        # Enriquecer con datos de producto
        enriched = []
        for sug in suggestions:
            products = list(self.core.db.execute_query("""
                SELECT name, price FROM products WHERE id = %s
            """, (sug['product_id'],)))
            
            if products:
                product = products[0]
                enriched.append({
                    'product_id': sug['product_id'],
                    'name': product['name'],
                    'price': float(product['price']),
                    'confidence': sug['confidence'],
                    'message': f"80% de clientes también compran: {product['name']}"
                })
        
        return enriched
    
    def get_cashier_prompt(self, product_id: int) -> Optional[str]:
        """
        Genera prompt para la cajera.
        """
        suggestions = self.get_suggestions(product_id, 1)
        
        if suggestions:
            sug = suggestions[0]
            return f"💡 Sugerir: {sug['name']} (${sug['price']:.0f}) - {sug['confidence']}% prob"
        
        return None

class ExecutiveNarrativeAI:
    """
    Briefing Ejecutivo Narrativo.
    
    Cada mañana: resumen no técnico con decisiones masticadas.
    """
    
    def __init__(self, core):
        self.core = core
    
    def generate_daily_brief(self) -> Dict[str, Any]:
        """
        Genera briefing diario narrativo.
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Datos de ayer
        sales = list(self.core.db.execute_query("""
            SELECT 
                serie,
                COUNT(*) as count,
                COALESCE(SUM(total), 0) as total,
                branch
            FROM sales
            WHERE timestamp::date = %s
            GROUP BY serie, branch
        """, (yesterday,)))
        
        # Procesar datos
        by_branch = {}
        totals = {'A': 0, 'B': 0}
        
        for row in sales:
            branch = row['branch'] or 'General'
            if branch not in by_branch:
                by_branch[branch] = {'A': 0, 'B': 0, 'total': 0}
            
            by_branch[branch][row['serie']] = float(row['total'])
            by_branch[branch]['total'] += float(row['total'])
            totals[row['serie']] += float(row['total'])
        
        # Encontrar sucursal estrella
        star_branch = max(by_branch.items(), key=lambda x: x[1]['total'])[0] if by_branch else 'N/A'
        star_total = by_branch.get(star_branch, {}).get('total', 0)
        
        # Comparar con semana pasada
        last_week = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE CAST(timestamp AS DATE) = CURRENT_DATE - INTERVAL '7 days'
        """, (yesterday,)))
        
        last_week_total = float(last_week[0]['total']) if last_week else 0
        week_change = ((totals['A'] + totals['B']) / last_week_total - 1) * 100 if last_week_total > 0 else 0
        
        # Productos destacados
        top_product = list(self.core.db.execute_query("""
            SELECT p.name, COALESCE(SUM(si.subtotal), 0) as revenue
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE CAST(s.timestamp AS DATE) = %s
            GROUP BY p.id
            ORDER BY revenue DESC
            LIMIT 1
        """, (yesterday,)))
        
        top_product_name = top_product[0]['name'] if top_product else 'N/A'
        
        # Stock bajo
        low_stock = list(self.core.db.execute_query("""
            SELECT name, stock FROM products 
            WHERE stock < min_stock AND stock > 0
            ORDER BY stock
            LIMIT 3
        """))
        
        # Generar narrativa
        total_sales = totals['A'] + totals['B']
        
        narrative = self._build_narrative(
            total_sales=total_sales,
            serie_b=totals['B'],
            week_change=week_change,
            star_branch=star_branch,
            star_total=star_total,
            top_product=top_product_name,
            low_stock=low_stock
        )
        
        return {
            'date': yesterday,
            'narrative': narrative,
            'metrics': {
                'total_sales': total_sales,
                'serie_a': totals['A'],
                'serie_b': totals['B'],
                'week_change': week_change,
                'star_branch': star_branch
            },
            'alerts': [f"Stock bajo: {p['name']} ({p['stock']} unidades)" for p in low_stock]
        }
    
    def _build_narrative(self, total_sales, serie_b, week_change, 
                        star_branch, star_total, top_product, low_stock):
        """
        Construye narrativa ejecutiva.
        """
        # Greeting
        if week_change > 15:
            greeting = "Mano, ayer fue un día EXCELENTE."
        elif week_change > 0:
            greeting = "Mano, ayer fue un buen día."
        elif week_change > -10:
            greeting = "Mano, ayer estuvimos normales."
        else:
            greeting = "Mano, ayer bajamos ventas."
        
        # Main insight
        main = f"Vendimos ${total_sales:,.0f} en total"
        if week_change != 0:
            direction = "más" if week_change > 0 else "menos"
            main += f" ({abs(week_change):.0f}% {direction} que hace una semana)."
        else:
            main += "."
        
        # Serie B highlight
        b_ratio = (serie_b / total_sales * 100) if total_sales > 0 else 0
        cash_insight = f"Tu flujo de efectivo (Serie B) fue ${serie_b:,.0f} ({b_ratio:.0f}% del total)."
        
        # Star
        star = f"⭐ La sucursal {star_branch} fue la estrella con ${star_total:,.0f}."
        
        # Product
        product_insight = f"El producto más vendido: {top_product}."
        
        # Alerts
        alerts = ""
        if low_stock:
            first_item = low_stock[0]
            alerts = f"⚠️ OJO: {first_item['name']} tiene solo {first_item['stock']} unidades."
        
        # Action
        actions = []
        if b_ratio < 40:
            actions.append("Hoy empuja más ventas en efectivo.")
        if low_stock:
            first_item = low_stock[0]
            actions.append(f"Reabastece {first_item['name']} urgente.")
        
        action_text = " | ".join(actions) if actions else "Mantén el ritmo."
        
        return f"""
{greeting}

{main}

{cash_insight}

{star}

{product_insight}

{alerts}

💡 ACCIÓN: {action_text}
"""
    
    def send_morning_brief(self):
        """
        Envía briefing matutino (para cron job).
        """
        brief = self.generate_daily_brief()
        
        # En producción: enviar a Telegram/PWA
        logger.info(f"📰 Executive Brief generado:\n{brief['narrative']}")
        
        return brief
