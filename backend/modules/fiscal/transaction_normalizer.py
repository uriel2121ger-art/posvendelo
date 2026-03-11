"""
Fiscal Noise Generator - IA de Ruido Estadístico
Rompe patrones para engañar algoritmos mediante Historical Behavioral Cloning.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import secrets
import threading
import time

from modules.shared.constants import money

_rng = secrets.SystemRandom()

logger = logging.getLogger(__name__)

class FiscalNoiseGenerator:
    """
    Generador de transacciones fantasma Serie A.
    Clona estadísticamente la distribución histórica de ventas reales.
    """
    
    # Fallback si no hay historial
    DEFAULT_HOURLY_PROBABILITY = {
        0: 0.01, 1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01, 5: 0.02,
        6: 0.03, 7: 0.05, 8: 0.08, 9: 0.12, 10: 0.15, 11: 0.18,
        12: 0.20, 13: 0.22, 14: 0.18, 15: 0.15, 16: 0.12, 17: 0.10,
        18: 0.08, 19: 0.06, 20: 0.04, 21: 0.03, 22: 0.02, 23: 0.01,
    }
    
    def __init__(self, db):
        self.db = db
        self.is_running = False
        self.noise_count = 0
        self.daily_target = 0
    
    async def calculate_optimal_noise(self) -> Dict[str, Any]:
        """Calcula 5-15% de ruido basado en el volumen reciente."""
        try:
            result = await self.db.fetch("""
                SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
                FROM sales 
                WHERE serie = 'A' AND is_noise = false
                AND timestamp >= CURRENT_DATE - INTERVAL '1 month'
            """)
            
            if not result:
                return {'daily_noise_target': 3}
            
            real_count = result[0]['count'] or 0
            real_total = money(result[0]['total'])
            
            noise_ratio = _rng.uniform(0.05, 0.15)
            optimal_noise_count = int(real_count * noise_ratio)
            
            days_remaining = (datetime.now().replace(day=28) - datetime.now()).days + 1
            daily_noise = max(2, optimal_noise_count // max(1, days_remaining))
            
            return {
                'real_transactions': real_count,
                'real_total': real_total,
                'noise_ratio': noise_ratio,
                'optimal_noise_count': optimal_noise_count,
                'daily_noise_target': daily_noise
            }
        except Exception as e:
            logger.error(f"Error calculando ruido: {e}")
            return {'daily_noise_target': 3}
    
    async def _get_historical_hourly_weights(self) -> Dict[int, float]:
        """Historical Behavioral Cloning: Lee el pulso real de los últimos 6 meses."""
        try:
            rows = await self.db.fetch("""
                SELECT EXTRACT(HOUR FROM timestamp) as hr, COUNT(*) as cnt
                FROM sales
                WHERE timestamp >= CURRENT_DATE - INTERVAL '6 months'
                AND is_noise = false
                GROUP BY hr
            """)
            if not rows:
                return self.DEFAULT_HOURLY_PROBABILITY
            
            total = sum(r['cnt'] for r in rows)
            if total == 0:
                return self.DEFAULT_HOURLY_PROBABILITY
                
            return {int(r['hr']): r['cnt']/total for r in rows}
        except Exception as e:
            logger.error(f"Error clone behavior: {e}")
            return self.DEFAULT_HOURLY_PROBABILITY
            
    async def _select_weighted_hour(self) -> int:
        weights_dict = await self._get_historical_hourly_weights()
        hours = list(weights_dict.keys())
        weights = list(weights_dict.values())
        return _rng.choices(hours, weights=weights)[0]
    
    async def generate_noise_transaction(self, rfc: str = None) -> Dict[str, Any]:
        """Genera metadata de la transacción fantasma."""
        products = await self.db.fetch("""
            SELECT id, name, price, barcode
            FROM products 
            WHERE stock > 10 AND price BETWEEN 10 AND 500
            ORDER BY RANDOM() LIMIT 5
        """)
        
        if not products:
            return {'success': False, 'error': 'No hay prod'}
        
        product = _rng.choice(products)
        qty = _rng.choice([1, 1, 1, 2, 2, 3])
        total = money(product['price']) * qty
        
        hour = await self._select_weighted_hour()
        
        noise_time = datetime.now().replace(
            hour=hour, minute=_rng.randint(0, 59), second=_rng.randint(0, 59)
        )
        if noise_time < datetime.now():
            noise_time += timedelta(days=1)
        
        if not rfc:
             try:
                from modules.fiscal.multi_emitter import MultiEmitterManager
                from decimal import Decimal
                mgr = MultiEmitterManager(self.db)
                optimal = await mgr.select_optimal_rfc(Decimal(total))
                rfc = optimal['rfc'] if optimal else 'PUBLICO_GENERAL'
             except Exception:
                rfc = 'PUBLICO_GENERAL'
                
        noise_transaction = {
            'type': 'noise',
            'serie': 'A',
            'rfc': rfc,
            'product_id': product['id'],
            'product_name': product['name'],
            'quantity': qty,
            'total': total,
            'scheduled_time': noise_time.isoformat(),
            'payment_method': _rng.choice(['cash', 'card', 'card']),
        }
        
        await self._schedule_noise(noise_transaction)
        self.noise_count += 1
        return {'success': True, 'transaction': noise_transaction}
        
    async def _schedule_noise(self, transaction: Dict):
        scheduled_time = datetime.fromisoformat(transaction['scheduled_time'])
        delay_seconds = (scheduled_time - datetime.now()).total_seconds()
        
        if delay_seconds > 0:
            def execute_later():
                time.sleep(delay_seconds)
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # Requiere crear db pool local aquí, o enviar por endpoint interno.
                # Como es conceptual la demo, saltamos esto por ahora
            
            thread = threading.Thread(target=execute_later, daemon=True)
            thread.start()
        else:
            await self._execute_noise_transaction(transaction)
    
    async def _execute_noise_transaction(self, t: Dict):
        try:
            row = await self.db.fetchrow("""
                INSERT INTO sales (
                    serie, total, payment_method, timestamp,
                    is_noise, cashier_id, branch_id, rfc_used, synced, status
                ) VALUES ('A', :total, :method, :ts, true, 0, 1, :rfc, 0, 'completed')
                RETURNING id
            """, {
                "total": t['total'], "method": t['payment_method'],
                "ts": datetime.now().isoformat(), "rfc": t['rfc']
            })
            if not row: return
            sale_id = row['id']
            
            await self.db.execute("""
                INSERT INTO sale_items (sale_id, product_id, qty, price, subtotal, synced)
                VALUES (:sid, :pid, :qty, :precio, :sub, 0)
            """, {
                "sid": sale_id, "pid": t['product_id'], "qty": t['quantity'],
                "precio": t['total']/t['quantity'], "sub": t['total']
            })
        except Exception as e:
            logger.error(f"Error insertando shadow noise: {e}")
    
    async def start_daily_noise(self, target: int = None):
        self.is_running = True
        if target is None:
            analysis = await self.calculate_optimal_noise()
            target = analysis.get('daily_noise_target', 3)
        self.daily_target = target
        for _ in range(target):
            await self.generate_noise_transaction()

