from pathlib import Path

"""
Fiscal Noise Generator - IA de Ruido Estadístico
Rompe patrones para engañar algoritmos del SAT
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import math
import random
import sys
import threading
import time

logger = logging.getLogger(__name__)

class FiscalNoiseGenerator:
    """
    Generador de transacciones fantasma Serie A.
    
    Objetivo: Romper la linealidad de ventas para que
    los algoritmos de IA del SAT vean comportamiento
    "orgánico, caótico y humano".
    
    Los patrones perfectos son sospechosos.
    El ruido es tu amigo.
    """
    
    # Rangos de montos para ruido (ventas pequeñas)
    NOISE_AMOUNT_RANGES = [
        (15, 50),     # Dulces, chicles
        (50, 150),    # Productos pequeños
        (150, 350),   # Productos medianos
        (350, 800),   # Productos premium
    ]
    
    # Probabilidad por hora (distribución más realista)
    HOURLY_PROBABILITY = {
        0: 0.01, 1: 0.01, 2: 0.01, 3: 0.01, 4: 0.01, 5: 0.02,
        6: 0.03, 7: 0.05, 8: 0.08, 9: 0.12, 10: 0.15, 11: 0.18,
        12: 0.20, 13: 0.22, 14: 0.18, 15: 0.15, 16: 0.12, 17: 0.10,
        18: 0.08, 19: 0.06, 20: 0.04, 21: 0.03, 22: 0.02, 23: 0.01,
    }
    
    def __init__(self, core):
        self.core = core
        self.is_running = False
        self.noise_count = 0
        self.daily_target = 0
    
    def calculate_optimal_noise(self) -> Dict[str, Any]:
        """
        Calcula la cantidad óptima de ruido basado en ventas reales.
        
        Regla: El ruido debe ser 5-15% de las transacciones totales
        para ser estadísticamente significativo pero no dominante.
        """
        try:
            # Obtener ventas reales del mes (PostgreSQL syntax)
            result = list(self.core.db.execute_query("""
                SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'A'
                AND timestamp::date >= DATE_TRUNC('month', CURRENT_DATE)::date
            """))
            
            if not result:
                return {'daily_noise_target': 3}
            
            real_count = result[0]['count'] or 0
            real_total = float(result[0]['total'] or 0)
            
            # Calcular ruido óptimo
            noise_ratio = random.uniform(0.05, 0.15)  # 5-15%
            optimal_noise_count = int(real_count * noise_ratio)
            
            # Mínimo de ruido diario - calcular días restantes del mes correctamente
            from calendar import monthrange
            today = datetime.now()
            last_day_of_month = monthrange(today.year, today.month)[1]
            days_remaining = last_day_of_month - today.day + 1
            daily_noise = max(2, optimal_noise_count // max(1, days_remaining))
            
            return {
                'real_transactions': real_count,
                'real_total': real_total,
                'noise_ratio': noise_ratio,
                'optimal_noise_count': optimal_noise_count,
                'daily_noise_target': daily_noise,
                'noise_per_rfc': daily_noise // 3  # Distribuir entre RFCs
            }
            
        except Exception as e:
            logger.error(f"Error calculando ruido: {e}")
            return {'daily_noise_target': 3}
    
    def generate_noise_transaction(self, rfc: str = None) -> Dict[str, Any]:
        """
        Genera una transacción de ruido Serie A.
        
        Características:
        - Monto pequeño pero realista
        - Hora semi-aleatoria (más probable en horas pico)
        - Producto real del inventario
        """
        # Seleccionar producto aleatorio con stock
        products = list(self.core.db.execute_query("""
            SELECT id, name, price, barcode
            FROM products 
            WHERE stock > 10 
            AND price BETWEEN 10 AND 500
            ORDER BY RANDOM() 
            LIMIT 5
        """))
        
        if not products:
            return {'success': False, 'error': 'No hay productos disponibles'}
        
        product = random.choice(products)
        
        # Cantidad pequeña (1-3)
        qty = random.choice([1, 1, 1, 2, 2, 3])
        total = float(product['price']) * qty
        
        # Seleccionar hora basada en probabilidad
        hour = self._select_weighted_hour()
        
        # Timestamp con jitter
        noise_time = datetime.now().replace(
            hour=hour,
            minute=random.randint(0, 59),
            second=random.randint(0, 59)
        )
        
        # Si la hora ya pasó hoy, es para mañana
        if noise_time < datetime.now():
            noise_time += timedelta(days=1)
        
        # RFC aleatorio si no se especifica
        if not rfc:
            rfc = self._select_available_rfc()
        
        noise_transaction = {
            'type': 'noise',
            'serie': 'A',
            'rfc': rfc,
            'product_id': product['id'],
            'product_name': product['name'],
            'quantity': qty,
            'total': total,
            'scheduled_time': noise_time.isoformat(),
            'payment_method': random.choice(['cash', 'card', 'card']),  # Más cards
            'is_noise': True  # Flag interno
        }
        
        # Programar la transacción
        self._schedule_noise(noise_transaction)
        
        self.noise_count += 1
        
        return {
            'success': True,
            'transaction': noise_transaction
        }
    
    def _select_weighted_hour(self) -> int:
        """Selecciona hora basada en probabilidad realista."""
        hours = list(self.HOURLY_PROBABILITY.keys())
        weights = list(self.HOURLY_PROBABILITY.values())
        
        return random.choices(hours, weights=weights)[0]
    
    def _select_available_rfc(self) -> str:
        """Selecciona RFC con más capacidad disponible."""
        try:
            # PostgreSQL syntax for year extraction
            rfcs = list(self.core.db.execute_query("""
                SELECT rfc, COALESCE(SUM(total), 0) as used
                FROM invoices
                WHERE EXTRACT(YEAR FROM fecha) = EXTRACT(YEAR FROM CURRENT_DATE)
                GROUP BY rfc
            """))
            
            if not rfcs:
                return 'RFC_DEFAULT'
            
            # Ordenar por menos usado
            rfcs.sort(key=lambda x: x['used'])
            return rfcs[0]['rfc'] if rfcs else 'RFC_DEFAULT'

        except Exception as e:
            logger.warning(f"Error seleccionando RFC: {e}")
            return 'RFC_DEFAULT'
    
    def _schedule_noise(self, transaction: Dict):
        """Programa la ejecución de la transacción de ruido."""
        scheduled_time = datetime.fromisoformat(transaction['scheduled_time'])
        delay_seconds = (scheduled_time - datetime.now()).total_seconds()
        
        if delay_seconds > 0:
            def execute_later():
                time.sleep(delay_seconds)
                self._execute_noise_transaction(transaction)
            
            thread = threading.Thread(target=execute_later, daemon=True)
            thread.start()
            
            # SECURITY: No loguear programación de ruido
            pass
        else:
            # Ejecutar inmediatamente
            self._execute_noise_transaction(transaction)
    
    def _execute_noise_transaction(self, transaction: Dict):
        """Ejecuta la transacción de ruido."""
        try:
            # Insertar venta real (Serie A) - Use execute_write() which returns ID automatically
            sale_id = self.core.db.execute_write("""
                INSERT INTO sales (
                    serie, total, payment_method, timestamp,
                    is_noise, cashier_id, branch_id, rfc_used, synced
                ) VALUES ('A', %s, %s, %s, 1, 0, 1, %s, 0)
            """, (
                transaction['total'],
                transaction['payment_method'],
                datetime.now().isoformat(),
                transaction['rfc']
            ))
            
            # If execute_write doesn't return ID (legacy SQLite), try to get it
            if sale_id == 0 or sale_id is None:
                try:
                    result = self.core.db.execute_query("""
                        SELECT id FROM sales 
                        WHERE serie = 'A' AND total = %s AND timestamp = %s 
                        ORDER BY id DESC LIMIT 1
                    """, (transaction['total'], datetime.now().isoformat()))
                    if result:
                        sale_id = result[0].get('id') if isinstance(result[0], dict) else result[0][0]
                except Exception:
                    sale_id = 0
            
            # Insertar item
            self.core.db.execute_write("""
                INSERT INTO sale_items (
                    sale_id, product_id, qty, price, subtotal, synced
                ) VALUES (%s, %s, %s, %s, %s, 0)
            """, (
                sale_id,
                transaction['product_id'],
                transaction['quantity'],
                transaction['total'] / transaction['quantity'],
                transaction['total']
            ))
            
            # Descontar stock
            self.core.db.execute_write("""
                UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (transaction['quantity'], transaction['product_id']))
            
            # SECURITY: No loguear ejecución de ruido
            pass
            
        except Exception as e:
            logger.error(f"Error ejecutando ruido: {e}")
    
    def start_daily_noise(self, target: int = None):
        """Inicia generación automática de ruido diario."""
        self.is_running = True
        
        if target is None:
            analysis = self.calculate_optimal_noise()
            target = analysis.get('daily_noise_target', 3)
        
        self.daily_target = target
        
        # SECURITY: No loguear inicio de generador de ruido
        pass
        
        # Generar ruido distribuido en el día
        for _ in range(target):
            self.generate_noise_transaction()
    
    def get_noise_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de ruido generado."""
        try:
            result = list(self.core.db.execute_query("""
                SELECT 
                    COUNT(*) as noise_count,
                    COALESCE(SUM(total), 0) as noise_total
                FROM sales
                WHERE is_noise = 1
                AND CAST(timestamp AS DATE) >= DATE_TRUNC('month', CURRENT_DATE)
            """))
            
            total = list(self.core.db.execute_query("""
                SELECT COUNT(*) as total_count
                FROM sales
                WHERE serie = 'A'
                AND CAST(timestamp AS DATE) >= DATE_TRUNC('month', CURRENT_DATE)
            """))
            
            noise_count = result[0]['noise_count'] or 0 if result else 0
            total_count = total[0]['total_count'] or 1 if total else 1
            
            ratio = (noise_count / total_count) * 100
            
            return {
                'noise_transactions': noise_count,
                'noise_total': float(result[0]['noise_total'] or 0) if result else 0,
                'total_transactions': total_count,
                'noise_ratio_percent': round(ratio, 1),
                'stealth_score': 'ÓPTIMO' if 5 <= ratio <= 15 else 'AJUSTAR'
            }
            
        except Exception as e:
            return {'error': str(e)}

# Función para cron
def run_daily_noise(core, target=None):
    """Ejecutar cada mañana."""
    generator = FiscalNoiseGenerator(core)
    generator.start_daily_noise(target)
