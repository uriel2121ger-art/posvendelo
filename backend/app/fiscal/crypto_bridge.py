from pathlib import Path

"""
Crypto Bridge - Puente de Liquidez a Stablecoins
Gestión de salidas de efectivo Serie B hacia USDT/USDC
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import logging
import sys

logger = logging.getLogger(__name__)

class CryptoBridge:
    """
    Puente Cripto: Conversión de efectivo Serie B a stablecoins.
    
    Características:
    - Cálculo de efectivo disponible para conversión
    - Registro como "Gasto Operativo B" (inventario fantasma)
    - Tracking de wallets y conversiones
    - Límites de seguridad anti-patrones
    """
    
    # Stablecoins soportadas
    STABLECOINS = ['USDT', 'USDC', 'DAI', 'BUSD']
    
    # Límites de seguridad
    MAX_DAILY_CONVERSION = 50000      # MXN por día
    MAX_WEEKLY_CONVERSION = 150000    # MXN por semana
    MAX_SINGLE_TRANSACTION = 30000    # MXN por transacción
    
    # Tipo de cambio aproximado (actualizar manualmente)
    USD_TO_MXN = 17.5
    
    def __init__(self, core):
        self.core = core
        self._ensure_table()
    
    def _ensure_table(self):
        """Crea tabla de conversiones si no existe."""
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS crypto_conversions (
                id BIGSERIAL PRIMARY KEY,
                amount_mxn REAL NOT NULL,
                amount_usd REAL NOT NULL,
                stablecoin TEXT NOT NULL,
                wallet_address TEXT,
                exchange_rate REAL,
                cover_description TEXT,
                status TEXT DEFAULT 'pending',
                tx_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS cold_wallets (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                stablecoin TEXT NOT NULL,
                balance_usd REAL DEFAULT 0,
                last_updated TEXT,
                notes TEXT
            )
        """)
    
    def get_available_for_conversion(self) -> Dict[str, Any]:
        """
        Calcula cuánto efectivo de Serie B está disponible para conversión.
        """
        # Total Serie B del año
        year = datetime.now().year
        serie_b = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'B' AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
        """, (str(year),)))
        
        total_serie_b = float(serie_b[0]['total'] or 0) if serie_b else 0.0
        
        # Ya convertido este año
        converted = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(amount_mxn), 0) as total
            FROM crypto_conversions
            WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s AND status = 'completed'
        """, (str(year),)))
        
        total_converted = float(converted[0]['total'] or 0) if converted else 0.0
        
        # Gastos en efectivo registrados
        expenses = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM cash_expenses
            WHERE EXTRACT(YEAR FROM expense_date::timestamp) = %s
        """, (str(year),)))
        
        total_expenses = float(expenses[0]['total'] or 0) if expenses else 0.0
        
        # Disponible = Serie B - Convertido - Gastos
        available = total_serie_b - total_converted - total_expenses
        
        # Límites de hoy y semana
        today_limit = self._get_remaining_daily_limit()
        week_limit = self._get_remaining_weekly_limit()
        
        return {
            'serie_b_total': total_serie_b,
            'already_converted': total_converted,
            'cash_expenses': total_expenses,
            'available_mxn': max(0, available),
            'available_usd': max(0, available) / self.USD_TO_MXN,
            'daily_limit_remaining': today_limit,
            'weekly_limit_remaining': week_limit,
            'max_now': min(available, today_limit, week_limit, self.MAX_SINGLE_TRANSACTION)
        }
    
    def _get_remaining_daily_limit(self) -> float:
        """Obtiene límite diario restante."""
        today = datetime.now().strftime('%Y-%m-%d')
        converted_today = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(amount_mxn), 0) as total
            FROM crypto_conversions
            WHERE created_at::date = %s
        """, (today,)))
        
        return max(0, self.MAX_DAILY_CONVERSION - (float(converted_today[0]['total'] or 0) if converted_today else 0))
    
    def _get_remaining_weekly_limit(self) -> float:
        """Obtiene límite semanal restante."""
        week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        converted_week = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(amount_mxn), 0) as total
            FROM crypto_conversions
            WHERE created_at::date >= %s
        """, (week_start,)))
        
        return max(0, self.MAX_WEEKLY_CONVERSION - (float(converted_week[0]['total'] or 0) if converted_week else 0))
    
    def create_conversion(self, amount_mxn: float, stablecoin: str = 'USDT',
                         wallet_address: str = None,
                         cover_description: str = None) -> Dict[str, Any]:
        """
        Registra una conversión de efectivo a stablecoin.
        """
        # Validaciones
        if stablecoin not in self.STABLECOINS:
            return {'success': False, 'error': f'Stablecoin no soportada: {stablecoin}'}
        
        if amount_mxn > self.MAX_SINGLE_TRANSACTION:
            return {
                'success': False, 
                'error': f'Monto excede límite por transacción (${self.MAX_SINGLE_TRANSACTION:,.0f})'
            }
        
        available = self.get_available_for_conversion()
        if amount_mxn > available['max_now']:
            return {'success': False, 'error': f'Monto excede disponible (${available["max_now"]:,.0f})'}
        
        # Calcular USD
        amount_usd = amount_mxn / self.USD_TO_MXN
        
        # Generar descripción de cobertura si no hay
        if not cover_description:
            cover_description = self._generate_cover_description(amount_mxn)
        
        # Registrar conversión
        self.core.db.execute_write("""
            INSERT INTO crypto_conversions 
            (amount_mxn, amount_usd, stablecoin, wallet_address, 
             exchange_rate, cover_description, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
        """, (amount_mxn, amount_usd, stablecoin, wallet_address,
              self.USD_TO_MXN, cover_description, datetime.now().isoformat()))
        
        # Registrar como gasto operativo B
        self._register_cover_expense(amount_mxn, cover_description)
        
        # SECURITY: No loguear conversiones cripto
        pass
        
        return {
            'success': True,
            'amount_mxn': amount_mxn,
            'amount_usd': amount_usd,
            'stablecoin': stablecoin,
            'cover': cover_description,
            'status': 'pending',
            'next_step': 'Completar compra P2P y marcar como completada'
        }
    
    def _generate_cover_description(self, amount: float) -> str:
        """Genera descripción de cobertura creíble."""
        covers = [
            'Compra de mercancía a proveedor de calle',
            'Mantenimiento de local y reparaciones',
            'Servicios de limpieza y seguridad',
            'Fletes y transporte de mercancía',
            'Gastos de publicidad local',
            'Compra de insumos operativos',
            'Pago a contratistas de servicios',
            'Mercancía para reposición de stock'
        ]
        
        # Seleccionar basado en hash del monto y fecha
        idx = int(hashlib.sha256(f"{amount}{datetime.now().date()}".encode()).hexdigest(), 16) % len(covers)
        return covers[idx]
    
    def _register_cover_expense(self, amount: float, description: str):
        """Registra el gasto de cobertura en cash_expenses."""
        try:
            self.core.db.execute_write("""
                INSERT INTO cash_expenses
                (category, description, amount, expense_date, created_at)
                VALUES ('mercancia', %s, %s, %s, %s)
            """, (description, amount, datetime.now().strftime('%Y-%m-%d'),
                  datetime.now().isoformat()))
        except Exception as e:
            logger.warning(f"Could not register cover expense: {e}")
    
    def confirm_conversion(self, conversion_id: int, tx_hash: str = None) -> Dict:
        """Marca una conversión como completada."""
        self.core.db.execute_write("""
            UPDATE crypto_conversions 
            SET status = 'completed', tx_hash = %s
            WHERE id = %s
        """, (tx_hash, conversion_id))
        
        return {'success': True, 'status': 'completed'}
    
    def add_cold_wallet(self, name: str, address: str, 
                       stablecoin: str = 'USDT') -> Dict:
        """Registra una cold wallet."""
        self.core.db.execute_write("""
            INSERT INTO cold_wallets (name, address, stablecoin, last_updated)
            VALUES (%s, %s, %s, %s)
        """, (name, address, stablecoin, datetime.now().isoformat()))
        
        return {'success': True, 'name': name, 'address': address[:10] + '...'}
    
    def update_wallet_balance(self, wallet_id: int, balance_usd: float) -> Dict:
        """Actualiza balance de una wallet."""
        self.core.db.execute_write("""
            UPDATE cold_wallets 
            SET balance_usd = %s, last_updated = %s
            WHERE id = %s
        """, (balance_usd, datetime.now().isoformat(), wallet_id))
        
        return {'success': True, 'balance': balance_usd}
    
    def get_crypto_wealth(self) -> Dict[str, Any]:
        """Obtiene resumen de riqueza en crypto."""
        wallets = list(self.core.db.execute_query("""
            SELECT name, stablecoin, balance_usd, last_updated
            FROM cold_wallets
            ORDER BY balance_usd DESC
        """))
        
        total_usd = sum(float(w['balance_usd'] or 0) for w in wallets)
        
        conversions = list(self.core.db.execute_query("""
            SELECT stablecoin, COALESCE(SUM(amount_usd), 0) as total
            FROM crypto_conversions
            WHERE status = 'completed'
            GROUP BY stablecoin
        """))
        
        return {
            'wallets': wallets,
            'total_usd': total_usd,
            'total_mxn': total_usd * self.USD_TO_MXN,
            'by_stablecoin': {c['stablecoin']: float(c['total']) for c in conversions},
            'status': 'Este valor está fuera del sistema bancario mexicano'
        }

from datetime import timedelta


# Función de análisis de patrones
def analyze_conversion_patterns(core) -> Dict:
    """Analiza patrones de conversión para evitar detección."""
    bridge = CryptoBridge(core)
    
    # Obtener conversiones del mes
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    conversions = list(core.db.execute_query("""
        SELECT amount_mxn, created_at
        FROM crypto_conversions
        WHERE created_at::date >= %s
        ORDER BY created_at
    """, (month_start,)))
    
    if len(conversions) < 3:
        return {'status': 'ok', 'message': 'Pocas conversiones para analizar'}
    
    # Detectar patrones problemáticos
    amounts = [c['amount_mxn'] for c in conversions]
    
    warnings = []
    
    # Montos muy similares (patrón)
    if len(set(amounts)) / len(amounts) < 0.5:
        warnings.append('Demasiados montos idénticos - variar cantidades')
    
    # Demasiadas conversiones
    if len(conversions) > 10:
        warnings.append('Muchas conversiones este mes - espaciar más')
    
    return {
        'status': 'warning' if warnings else 'ok',
        'warnings': warnings,
        'recommendation': 'Variar montos y frecuencia para evitar patrones detectables'
    }
