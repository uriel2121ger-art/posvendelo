"""
Crypto Bridge - Puente de Liquidez a Stablecoins
Gestión de salidas de efectivo Serie B hacia USDT/USDC simulando gastos.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)

class CryptoBridge:
    STABLECOINS = ['USDT', 'USDC', 'DAI', 'BUSD']
    MAX_DAILY_CONVERSION = 50000      # MXN por día
    MAX_WEEKLY_CONVERSION = 150000    # MXN por semana
    MAX_SINGLE_TRANSACTION = 30000    # MXN por transacción
    USD_TO_MXN = 18.5
    
    def __init__(self, db):
        self.db = db
    
    async def _ensure_table(self):
        await self.db.execute("""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS cold_wallets (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                stablecoin TEXT NOT NULL,
                balance_usd REAL DEFAULT 0,
                last_updated TIMESTAMP,
                notes TEXT
            )
        """)
        # Create cash_expenses if it doesn't exist
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS cash_expenses (
                id BIGSERIAL PRIMARY KEY,
                category TEXT,
                description TEXT,
                amount REAL,
                expense_date DATE,
                created_at TIMESTAMP
            )
        """)
    
    async def get_available_for_conversion(self) -> Dict[str, Any]:
        year = datetime.now().year
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-01-01"
        
        try:
            row_b = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'B' AND timestamp >= :ys AND timestamp < :ye AND status = 'completed'", ys=year_start, ye=year_end)
            total_serie_b = round(float(row_b['total'] or 0), 2) if row_b else 0.0
        except Exception:
            total_serie_b = 0.0
            
        await self._ensure_table()
        
        try:
            row_c = await self.db.fetchrow("SELECT COALESCE(SUM(amount_mxn), 0) as total FROM crypto_conversions WHERE created_at >= :ys::timestamp AND created_at < :ye::timestamp AND status = 'completed'", ys=year_start, ye=year_end)
            total_converted = round(float(row_c['total'] or 0), 2) if row_c else 0.0
            
            row_e = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_expenses WHERE expense_date >= :ys::date AND expense_date < :ye::date", ys=year_start, ye=year_end)
            total_expenses = round(float(row_e['total'] or 0), 2) if row_e else 0.0
        except Exception:
            total_converted = 0.0
            total_expenses = 0.0
            
        available = total_serie_b - total_converted - total_expenses
        today_limit = await self._get_remaining_daily_limit()
        week_limit = await self._get_remaining_weekly_limit()
        
        return {
            'serie_b_total': total_serie_b, 'already_converted': total_converted, 'cash_expenses': total_expenses,
            'available_mxn': max(0, available), 'available_usd': max(0, available) / self.USD_TO_MXN,
            'daily_limit_remaining': today_limit, 'weekly_limit_remaining': week_limit,
            'max_now': min(available, today_limit, week_limit, self.MAX_SINGLE_TRANSACTION)
        }
    
    async def _get_remaining_daily_limit(self) -> float:
        today = datetime.now().strftime('%Y-%m-%d')
        row = await self.db.fetchrow("SELECT COALESCE(SUM(amount_mxn), 0) as total FROM crypto_conversions WHERE created_at::date = :today", today=datetime.strptime(today, '%Y-%m-%d').date())
        return max(0, self.MAX_DAILY_CONVERSION - (round(float(row['total'] or 0), 2) if row else 0))
    
    async def _get_remaining_weekly_limit(self) -> float:
        week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        row = await self.db.fetchrow("SELECT COALESCE(SUM(amount_mxn), 0) as total FROM crypto_conversions WHERE created_at::date >= :week_start", week_start=datetime.strptime(week_start, '%Y-%m-%d').date())
        return max(0, self.MAX_WEEKLY_CONVERSION - (round(float(row['total'] or 0), 2) if row else 0))
    
    async def create_conversion(self, amount_mxn: float, stablecoin: str = 'USDT', wallet_address: str = None, cover_description: str = None) -> Dict[str, Any]:
        await self._ensure_table()
        if stablecoin not in self.STABLECOINS: return {'success': False, 'error': f'Stablecoin no soportada: {stablecoin}'}
        if amount_mxn > self.MAX_SINGLE_TRANSACTION: return {'success': False, 'error': f'Excede límite transacción (${self.MAX_SINGLE_TRANSACTION:,.0f})'}
        
        available = await self.get_available_for_conversion()
        if amount_mxn > available['max_now']: return {'success': False, 'error': f'Monto excede disponible (${available["max_now"]:,.0f})'}
        
        amount_usd = amount_mxn / self.USD_TO_MXN
        if not cover_description: cover_description = self._generate_cover_description(amount_mxn)
        
        await self.db.execute("""
            INSERT INTO crypto_conversions 
            (amount_mxn, amount_usd, stablecoin, wallet_address, exchange_rate, cover_description, status, created_at)
            VALUES (:amount_mxn, :amount_usd, :stablecoin, :wallet_address, :ex_rate, :cover_desc, 'pending', NOW())
        """, amount_mxn=amount_mxn, amount_usd=amount_usd, stablecoin=stablecoin, wallet_address=wallet_address, ex_rate=self.USD_TO_MXN, cover_desc=cover_description)
        
        await self._register_cover_expense(amount_mxn, cover_description)
        
        return {'success': True, 'amount_mxn': amount_mxn, 'amount_usd': amount_usd, 'cover': cover_description, 'status': 'pending'}
    
    def _generate_cover_description(self, amount: float) -> str:
        covers = ['Compra mercancía sin cfdi', 'Mantenimiento local', 'Servicios limpieza', 'Fletes operativos', 'Reparaciones menores']
        idx = int(hashlib.sha256(f"{amount}{datetime.now().date()}".encode()).hexdigest(), 16) % len(covers)
        return covers[idx]
    
    async def _register_cover_expense(self, amount: float, description: str):
        try:
            await self.db.execute("""
                INSERT INTO cash_expenses (category, description, amount, expense_date, created_at)
                VALUES ('mercancia', :desc, :amt, CURRENT_DATE, NOW())
            """, desc=description, amt=amount)
        except Exception as e:
            logger.warning(f"Failed to register cover expense: {e}")
            
    async def get_crypto_wealth(self) -> Dict[str, Any]:
        await self._ensure_table()
        wallets = await self.db.fetch("SELECT name, stablecoin, balance_usd, last_updated FROM cold_wallets ORDER BY balance_usd DESC")
        total_usd = sum(round(float(w['balance_usd'] or 0), 2) for w in wallets)
        
        conversions = await self.db.fetch("SELECT stablecoin, COALESCE(SUM(amount_usd), 0) as total FROM crypto_conversions WHERE status = 'completed' GROUP BY stablecoin")
        return {
            'wallets': [dict(w) for w in wallets], 'total_usd': total_usd, 'total_mxn': total_usd * self.USD_TO_MXN,
            'by_stablecoin': {c['stablecoin']: round(float(c['total']), 2) for c in conversions},
            'status': 'Fondos líquidos'
        }
