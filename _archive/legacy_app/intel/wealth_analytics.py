from pathlib import Path

"""
Wealth Growth Dashboard - Analítica de Utilidad Real
Margen de Libertad: Utilidad B vs A
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import sys

logger = logging.getLogger(__name__)

class WealthGrowthDashboard:
    """
    Dashboard de crecimiento patrimonial real.
    
    Compara:
    - Utilidad Serie A (fiscal, con impuestos)
    - Utilidad Serie B (libre, reinversión directa)
    
    Te dice QUÉ productos usar para construir patrimonio.
    """
    
    def __init__(self, core):
        self.core = core
    
    def get_freedom_margin(self, period: str = 'month') -> Dict[str, Any]:
        """
        Calcula el Margen de Libertad.
        
        Cuánta utilidad tienes libre de impuestos.
        """
        try:
            if period == 'month':
                date_filter = "timestamp::date >= CURRENT_DATE - INTERVAL '1 month'"
            elif period == 'year':
                date_filter = "EXTRACT(YEAR FROM timestamp) = EXTRACT(YEAR FROM CURRENT_DATE)"
            else:
                date_filter = "timestamp::date >= CURRENT_DATE - INTERVAL '7 days'"

            # Ventas y costos por serie
            # nosec B608 - date_filter is hardcoded SQL fragment based on period enum, not user input
            result = list(self.core.db.execute_query(f"""
                SELECT
                    serie,
                    COALESCE(SUM(total), 0) as revenue,
                    COALESCE(SUM(cost), 0) as cost,
                    COUNT(*) as transactions
                FROM sales
                LEFT JOIN (
                    SELECT sale_id, COALESCE(SUM(si.qty * p.cost), 0) as cost
                    FROM sale_items si
                    JOIN products p ON si.product_id = p.id
                    GROUP BY sale_id
                ) costs ON sales.id = costs.sale_id
                WHERE {date_filter}
                GROUP BY serie
            """))
            
            data = {'A': {'revenue': 0, 'cost': 0}, 'B': {'revenue': 0, 'cost': 0}}
            for row in result:
                serie = row['serie']
                data[serie] = {
                    'revenue': float(row['revenue']),
                    'cost': float(row['cost'] or 0),
                    'transactions': row['transactions']
                }
            
            # Calcular utilidades
            utility_a = data['A']['revenue'] - data['A']['cost']
            utility_b = data['B']['revenue'] - data['B']['cost']
            
            # Impuestos estimados Serie A (ISR ~30% sobre utilidad fiscal)
            tax_rate = 0.30
            taxes_a = utility_a * tax_rate
            net_utility_a = utility_a - taxes_a
            
            # Serie B = 100% libre
            net_utility_b = utility_b
            
            # Margen de Libertad
            total_net = net_utility_a + net_utility_b
            freedom_margin = (net_utility_b / total_net * 100) if total_net > 0 else 0
            
            return {
                'period': period,
                'serie_a': {
                    'revenue': data['A']['revenue'],
                    'cost': data['A']['cost'],
                    'gross_utility': utility_a,
                    'taxes_estimated': taxes_a,
                    'net_utility': net_utility_a,
                    'transactions': data['A'].get('transactions', 0)
                },
                'serie_b': {
                    'revenue': data['B']['revenue'],
                    'cost': data['B']['cost'],
                    'gross_utility': utility_b,
                    'taxes': 0,
                    'net_utility': net_utility_b,
                    'transactions': data['B'].get('transactions', 0)
                },
                'totals': {
                    'total_net_utility': total_net,
                    'freedom_margin_percent': round(freedom_margin, 1),
                    'cash_available': net_utility_b
                }
            }
            
        except Exception as e:
            logger.error(f"Error en Freedom Margin: {e}")
            return {'error': str(e)}
    
    def get_product_contribution(self, top_n: int = 20) -> List[Dict]:
        """
        Análisis de contribución por producto.
        
        Qué productos generan utilidad en cada serie.
        """
        try:
            result = list(self.core.db.execute_query("""
                SELECT 
                    p.id,
                    p.name,
                    p.barcode,
                    s.serie,
                    COALESCE(SUM(si.qty), 0) as qty_sold,
                    COALESCE(SUM(si.subtotal), 0) as revenue,
                    COALESCE(SUM(si.qty * p.cost), 0) as cost,
                    SUM(si.subtotal) - COALESCE(SUM(si.qty * p.cost), 0) as utility
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN products p ON si.product_id = p.id
                WHERE CAST(s.timestamp AS DATE) >= CURRENT_DATE - INTERVAL '1 month'
                GROUP BY p.id, s.serie
                ORDER BY utility DESC
                LIMIT %s
            """, (top_n * 2,)))
            
            # Agrupar por producto
            products = {}
            for row in result:
                pid = row['id']
                if pid not in products:
                    products[pid] = {
                        'id': pid,
                        'name': row['name'],
                        'barcode': row['barcode'],
                        'utility_a': 0,
                        'utility_b': 0,
                        'revenue_a': 0,
                        'revenue_b': 0
                    }
                
                if row['serie'] == 'A':
                    products[pid]['utility_a'] = float(row['utility'] or 0)
                    products[pid]['revenue_a'] = float(row['revenue'] or 0)
                else:
                    products[pid]['utility_b'] = float(row['utility'] or 0)
                    products[pid]['revenue_b'] = float(row['revenue'] or 0)
            
            # Calcular ratio B/A
            for p in products.values():
                total_utility = p['utility_a'] + p['utility_b']
                p['total_utility'] = total_utility
                p['b_ratio'] = (p['utility_b'] / total_utility * 100) if total_utility > 0 else 0
                p['a_ratio'] = (p['utility_a'] / total_utility * 100) if total_utility > 0 else 0
            
            # Ordenar por utilidad total
            sorted_products = sorted(
                products.values(), 
                key=lambda x: x['total_utility'], 
                reverse=True
            )[:top_n]
            
            return sorted_products
            
        except Exception as e:
            logger.error(f"Error en product contribution: {e}")
            return []
    
    def get_ai_recommendations(self) -> List[Dict]:
        """
        Recomendaciones de IA para optimizar patrimonio.
        """
        recommendations = []
        
        # Obtener datos
        freedom = self.get_freedom_margin()
        products = self.get_product_contribution(50)
        
        if 'error' in freedom:
            return recommendations
        
        # 1. Productos con alta utilidad B pero baja A
        for p in products:
            if p['b_ratio'] > 70 and p['a_ratio'] < 30:
                recommendations.append({
                    'type': 'OPTIMIZE_CASH_FLOW',
                    'product': p['name'],
                    'insight': f"El producto '{p['name']}' genera {p['b_ratio']:.0f}% de su utilidad en Serie B.",
                    'action': f"Deja de facturarlo. Úsalo solo para flujo de efectivo.",
                    'impact': f"Ahorro fiscal potencial: ${p['utility_b'] * 0.30:,.0f}"
                })
            
        # 2. Productos con utilidad fiscal alta (deducir)
        for p in products:
            if p['a_ratio'] > 80:
                recommendations.append({
                    'type': 'FISCAL_STAR',
                    'product': p['name'],
                    'insight': f"'{p['name']}' es tu producto estrella fiscal.",
                    'action': "Mantén facturación alta para maximizar deducciones.",
                    'impact': f"Base deducible generada: ${p['revenue_a']:,.0f}"
                })
        
        # 3. Freedom Margin bajo
        if freedom['totals']['freedom_margin_percent'] < 30:
            recommendations.append({
                'type': 'LOW_FREEDOM',
                'insight': f"Tu Margen de Libertad es solo {freedom['totals']['freedom_margin_percent']}%.",
                'action': "Incrementa ventas en efectivo (Serie B) para liberar capital.",
                'impact': "Meta: Subir a 50%+ de margen libre"
            })
        
        return recommendations[:5]  # Top 5 recomendaciones

class LocalIntelligence:
    """
    Inteligencia de contexto local Mérida.
    
    Correlaciona ventas con:
    - Clima (temperatura, humedad)
    - Eventos (quincenas, vacaciones, fiestas)
    - Estacionalidad regional
    """
    
    # Eventos conocidos de Yucatán
    YUCATAN_EVENTS = {
        1: ['Día de Reyes (6)', 'Inicio de calor'],
        2: ['Carnaval', 'Pico de calor'],
        3: ['Primavera', 'Semana Santa (variable)'],
        4: ['Semana Santa', 'Hanal Pixán prep'],
        5: ['Día de las Madres (10)', 'Temporada alta'],
        6: ['Día del Padre (16)', 'Vacaciones verano'],
        7: ['Vacaciones verano pico', 'Temporada huracanes'],
        8: ['Regreso a clases', 'Compras escolares'],
        9: ['Independencia (16)', 'Fiestas patrias'],
        10: ['Hanal Pixán (31-Nov2)', 'Día de Muertos'],
        11: ['Buen Fin', 'Inicio temporada alta'],
        12: ['Navidad', 'Año Nuevo', 'Máximo comercial'],
    }
    
    TEMPERATURE_IMPACT = {
        'above_40': {
            'categories': ['Bloqueadores', 'Bebidas', 'Ventiladores', 'Cremas'],
            'multiplier': 1.30
        },
        'above_35': {
            'categories': ['Bebidas', 'Helados', 'Abanicos'],
            'multiplier': 1.15
        },
        'rainy': {
            'categories': ['Paraguas', 'Impermeables', 'Medicamentos gripe'],
            'multiplier': 1.25
        }
    }
    
    def __init__(self, core):
        self.core = core
    
    def get_climate_correlation(self, product_id: int = None) -> Dict[str, Any]:
        """
        Correlaciona ventas con clima de Mérida.
        """
        # Simular datos de clima (en producción: API de clima)
        import random
        current_temp = random.randint(32, 44)  # Mérida 🥵
        
        analysis = {
            'current_temperature': current_temp,
            'climate_zone': 'hot' if current_temp > 35 else 'warm',
            'humidity': random.randint(60, 90),
            'recommendations': []
        }
        
        # Productos que se benefician del calor
        if current_temp > 40:
            analysis['recommendations'].append({
                'category': 'Bloqueadores solares',
                'insight': f"Con {current_temp}°C, ventas de bloqueadores +300%",
                'action': "Subir precio 5% y reabastecer urgente",
                'urgency': 'HIGH'
            })
        
        if current_temp > 35:
            analysis['recommendations'].append({
                'category': 'Bebidas y sueros',
                'insight': "Demanda alta por deshidratación",
                'action': "Stock de emergencia en todas las sucursales",
                'urgency': 'MEDIUM'
            })
        
        return analysis
    
    def get_event_impact(self) -> Dict[str, Any]:
        """
        Impacto de eventos locales en ventas.
        """
        month = datetime.now().month
        day = datetime.now().day
        
        events = self.YUCATAN_EVENTS.get(month, [])
        
        # Quincenas
        is_quincena = day <= 3 or (15 <= day <= 18)
        
        analysis = {
            'month_events': events,
            'is_quincena': is_quincena,
            'recommendations': []
        }
        
        if is_quincena:
            analysis['recommendations'].append({
                'insight': "Es quincena. Flujo de efectivo alto.",
                'action': "Maximizar ventas Serie B. Clientes con liquidez.",
                'expected_lift': '+25% ventas efectivo'
            })
        
        # Eventos específicos
        if month == 12:
            analysis['recommendations'].append({
                'insight': "Temporada alta navideña",
                'action': "Stock máximo. Precios optimizados. Horarios extendidos.",
                'expected_lift': '+80% vs promedio anual'
            })
        elif month == 11 and 15 <= day <= 20:
            analysis['recommendations'].append({
                'insight': "Buen Fin activo",
                'action': "Promociones agresivas Serie B para captar efectivo",
                'expected_lift': '+200% fin de semana'
            })
        
        return analysis
    
    def get_daily_brief(self) -> str:
        """
        Briefing diario con contexto local.
        """
        climate = self.get_climate_correlation()
        events = self.get_event_impact()
        
        brief = f"""
🌡️ CONTEXTO MÉRIDA - {datetime.now().strftime('%d/%m/%Y')}

Temperatura: {climate['current_temperature']}°C
Humedad: {climate['humidity']}%
Quincena: {'SÍ ✅' if events['is_quincena'] else 'NO'}

📅 Eventos del mes: {', '.join(events['month_events'])}

📊 RECOMENDACIONES:
"""
        for rec in climate['recommendations'] + events['recommendations']:
            brief += f"\n• {rec.get('insight', rec.get('category', ''))}"
            brief += f"\n  → {rec.get('action', '')}"
        
        return brief

class GhostWallet:
    """
    Monedero Anónimo NFC/QR.
    
    Puntos y crédito sin RFC ni nombre.
    Hash ID basado en objeto físico del cliente.
    
    "Paga en efectivo, acumula en tu Monedero Blue"
    """
    
    def __init__(self, core):
        self.core = core
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Crea tablas para Ghost Wallet."""
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS ghost_wallets (
                id BIGSERIAL PRIMARY KEY,
                hash_id TEXT UNIQUE NOT NULL,
                balance DOUBLE PRECISION DEFAULT 0,
                total_earned DOUBLE PRECISION DEFAULT 0,
                total_spent DOUBLE PRECISION DEFAULT 0,
                transactions_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                last_activity TEXT
            )
        """)
        
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS ghost_transactions (
                id BIGSERIAL PRIMARY KEY,
                wallet_hash TEXT,
                type TEXT,
                amount DOUBLE PRECISION,
                sale_id INTEGER,
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
    
    def generate_hash_id(self, seed: str = None) -> str:
        """
        Genera Hash ID único para cliente anónimo.
        """
        import hashlib
        import secrets
        
        if seed:
            # Hash basado en input (tarjeta física, QR del cliente)
            hash_input = seed + secrets.token_hex(8)
        else:
            # Hash completamente aleatorio
            hash_input = secrets.token_hex(16)
        
        hash_id = hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()
        
        # Formato legible: XXXX-XXXX-XXXX
        formatted = f"{hash_id[:4]}-{hash_id[4:8]}-{hash_id[8:]}"
        
        # Crear wallet
        self.core.db.execute_write("""
            INSERT INTO ghost_wallets (hash_id) VALUES (%s)
            ON CONFLICT (hash_id) DO NOTHING
        """, (formatted,))
        
        return formatted
    
    def add_points(self, hash_id: str, sale_amount: float, 
                   sale_id: int = None) -> Dict[str, Any]:
        """
        Acumula puntos por compra en efectivo (Serie B).
        
        5% de la compra = puntos Blue
        """
        points_rate = 0.05  # 5%
        points = sale_amount * points_rate
        
        try:
            self.core.db.execute_write("""
                UPDATE ghost_wallets 
                SET balance = balance + %s,
                    total_earned = total_earned + %s,
                    transactions_count = transactions_count + 1,
                    last_activity = %s
                WHERE hash_id = %s
            """, (points, points, datetime.now().isoformat(), hash_id))
            
            # Registrar transacción
            self.core.db.execute_write("""
                INSERT INTO ghost_transactions (wallet_hash, type, amount, sale_id)
                VALUES (%s, 'earn', %s, %s)
            """, (hash_id, points, sale_id))
            
            # Obtener balance actual
            wallets = list(self.core.db.execute_query("""
                SELECT balance, total_earned FROM ghost_wallets WHERE hash_id = %s
            """, (hash_id,)))
            
            balance = float(wallets[0]['balance']) if wallets else 0
            
            return {
                'success': True,
                'points_added': points,
                'new_balance': balance,
                'message': f"+${points:.0f} Blue. Saldo: ${balance:.0f}"
            }
            
        except Exception as e:
            logger.error(f"Error adding points: {e}")
            return {'success': False, 'error': str(e)}
    
    def redeem_points(self, hash_id: str, amount: float) -> Dict[str, Any]:
        """
        Canjea puntos Blue por descuento.
        """
        try:
            # Verificar balance
            wallets = list(self.core.db.execute_query("""
                SELECT balance FROM ghost_wallets WHERE hash_id = %s
            """, (hash_id,)))
            
            if not wallets or wallets[0]['balance'] < amount:
                return {
                    'success': False,
                    'error': 'Saldo insuficiente'
                }
            
            # Descontar
            self.core.db.execute_write("""
                UPDATE ghost_wallets 
                SET balance = balance - %s,
                    total_spent = total_spent + %s,
                    last_activity = %s
                WHERE hash_id = %s
            """, (amount, amount, datetime.now().isoformat(), hash_id))
            
            # Registrar
            self.core.db.execute_write("""
                INSERT INTO ghost_transactions (wallet_hash, type, amount)
                VALUES (%s, 'redeem', %s)
            """, (hash_id, -amount))
            
            new_balance = (wallets[0]['balance'] - amount) if wallets else 0
            
            return {
                'success': True,
                'redeemed': amount,
                'new_balance': new_balance,
                'message': f"Canjeaste ${amount:.0f}. Nuevo saldo: ${new_balance:.0f}"
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_wallet_stats(self) -> Dict[str, Any]:
        """
        Estadísticas globales de Ghost Wallets.
        """
        try:
            result = list(self.core.db.execute_query("""
                SELECT 
                    COUNT(*) as total_wallets,
                    COALESCE(SUM(balance), 0) as total_balance,
                    COALESCE(SUM(total_earned), 0) as total_earned,
                    COALESCE(SUM(total_spent), 0) as total_spent,
                    COALESCE(SUM(transactions_count), 0) as total_transactions
                FROM ghost_wallets
            """))
            
            # CRITICAL FIX: Validate result before accessing
            if not result or not result[0]:
                return {
                    'total_wallets': 0,
                    'total_balance': 0.0,
                    'total_earned': 0.0,
                    'total_spent': 0.0,
                    'total_transactions': 0,
                    'retention_rate': 0
                }

            row = result[0]

            # Safe type conversions with defaults
            total_earned = float(row.get('total_earned', 0) or 0)
            total_spent = float(row.get('total_spent', 0) or 0)

            return {
                'total_wallets': int(row.get('total_wallets', 0) or 0),
                'total_balance': float(row.get('total_balance', 0) or 0),
                'total_earned': total_earned,
                'total_spent': total_spent,
                'total_transactions': int(row.get('total_transactions', 0) or 0),
                'retention_rate': round((total_spent / total_earned * 100), 2)
                                  if total_earned > 0 else 0
            }
            
        except Exception as e:
            return {'error': str(e)}
