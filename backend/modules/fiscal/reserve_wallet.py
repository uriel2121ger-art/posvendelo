"""
Ghost Wallet System (Monedero Blue)
Programa de Lealtad Anónimo (NFC/QR) para incentivar ventas Serie B.
Puntos y crédito sin RFC ni nombre del cliente.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import logging
import hashlib
import secrets

from modules.shared.constants import dec, money

logger = logging.getLogger(__name__)

class GhostWallet:
    """
    Monedero Anónimo NFC/QR.
    Paga en efectivo (Serie B), acumula puntos en tu Monedero Blue.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def _ensure_tables(self):
        """Crea tablas para Ghost Wallet."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS ghost_wallets (
                id BIGSERIAL PRIMARY KEY,
                hash_id TEXT UNIQUE NOT NULL,
                balance NUMERIC(12,2) DEFAULT 0,
                total_earned NUMERIC(12,2) DEFAULT 0,
                total_spent NUMERIC(12,2) DEFAULT 0,
                transactions_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                last_activity TIMESTAMP
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS ghost_transactions (
                id BIGSERIAL PRIMARY KEY,
                wallet_hash TEXT,
                type TEXT,
                amount NUMERIC(12,2),
                sale_id INTEGER,
                timestamp TIMESTAMP DEFAULT NOW()
            )
        """)
    
    async def generate_hash_id(self, seed: str = None) -> str:
        """
        Genera Hash ID único para cliente anónimo.
        """
        await self._ensure_tables()
        
        if seed:
            hash_input = seed + secrets.token_hex(8)
        else:
            hash_input = secrets.token_hex(16)
        
        hash_id = hashlib.sha256(hash_input.encode()).hexdigest()[:12].upper()
        formatted = f"{hash_id[:4]}-{hash_id[4:8]}-{hash_id[8:]}"
        
        await self.db.execute("""
            INSERT INTO ghost_wallets (hash_id) VALUES (:hid)
            ON CONFLICT (hash_id) DO NOTHING
        """, hid=formatted)
        
        return formatted
    
    async def add_points(self, hash_id: str, sale_amount: float,
                   sale_id: int = None) -> Dict[str, Any]:
        """
        Acumula puntos por compra en efectivo (Serie B).
        5% de la compra = puntos Blue.
        """
        await self._ensure_tables()
        sale_amount = Decimal(str(sale_amount))
        points_rate = Decimal("0.05")  # 5%
        points = (sale_amount * points_rate).quantize(Decimal("0.01"))

        try:
            conn = self.db.connection
            async with conn.transaction():
                await self.db.fetchrow(
                    "SELECT balance FROM ghost_wallets WHERE hash_id = :hid FOR UPDATE",
                    hid=hash_id,
                )
                await self.db.execute("""
                    UPDATE ghost_wallets
                    SET balance = balance + :pts,
                        total_earned = total_earned + :pts,
                        transactions_count = transactions_count + 1,
                        last_activity = CURRENT_TIMESTAMP
                    WHERE hash_id = :hid
                """, pts=points, hid=hash_id)

                if sale_id:
                    await self.db.execute("""
                        INSERT INTO ghost_transactions (wallet_hash, type, amount, sale_id)
                        VALUES (:hid, 'earn', :amt, :sid)
                    """, hid=hash_id, amt=points, sid=sale_id)

                row = await self.db.fetchrow("SELECT balance FROM ghost_wallets WHERE hash_id = :hid", hid=hash_id)
                balance = money(row['balance']) if row else 0

            return {
                'success': True,
                'points_added': points,
                'new_balance': balance,
                'message': f"+${points:.0f} Blue. Saldo: ${balance:.0f}"
            }
        except Exception as e:
            logger.error(f"Error adding points: {e}")
            return {'success': False, 'error': str(e)}
    
    async def redeem_points(self, hash_id: str, amount: float) -> Dict[str, Any]:
        """
        Canjea puntos Blue por descuento.
        Uses FOR UPDATE to prevent double-spend race conditions.
        """
        await self._ensure_tables()
        amount = Decimal(str(amount))
        try:
            conn = self.db.connection
            async with conn.transaction():
                row = await self.db.fetchrow(
                    "SELECT balance FROM ghost_wallets WHERE hash_id = :hid FOR UPDATE",
                    hid=hash_id,
                )

                if not row or Decimal(str(row['balance'] or 0)) < amount:
                    return {'success': False, 'error': 'Saldo insuficiente'}

                await self.db.execute("""
                    UPDATE ghost_wallets
                    SET balance = balance - :amt,
                        total_spent = total_spent + :amt,
                        last_activity = CURRENT_TIMESTAMP
                    WHERE hash_id = :hid
                """, amt=amount, hid=hash_id)

                await self.db.execute("""
                    INSERT INTO ghost_transactions (wallet_hash, type, amount)
                    VALUES (:hid, 'redeem', :amt)
                """, hid=hash_id, amt=(-amount).quantize(Decimal("0.01")))

                new_balance = Decimal(str(row['balance'] or 0)) - amount

            return {
                'success': True,
                'redeemed': amount,
                'new_balance': new_balance,
                'message': f"Canjeaste ${amount:.0f}. Nuevo saldo: ${new_balance:.0f}"
            }
        except Exception as e:
            logger.error(f"Error redeeming points: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_wallet_stats(self) -> Dict[str, Any]:
        """Estadísticas globales de Ghost Wallets."""
        await self._ensure_tables()
        try:
            row = await self.db.fetchrow("""
                SELECT 
                    COUNT(*) as total_wallets,
                    COALESCE(SUM(balance), 0) as total_balance,
                    COALESCE(SUM(total_earned), 0) as total_earned,
                    COALESCE(SUM(total_spent), 0) as total_spent,
                    COALESCE(SUM(transactions_count), 0) as total_transactions
                FROM ghost_wallets
            """)
            
            if not row:
                return {
                    'total_wallets': 0, 'total_balance': 0.0, 'total_earned': 0.0,
                    'total_spent': 0.0, 'total_transactions': 0, 'retention_rate': 0
                }

            total_earned = dec(row.get('total_earned', 0))
            total_spent = dec(row.get('total_spent', 0))

            return {
                'total_wallets': int(row.get('total_wallets', 0) or 0),
                'total_balance': money(row.get('total_balance', 0)),
                'total_earned': money(total_earned),
                'total_spent': money(total_spent),
                'total_transactions': int(row.get('total_transactions', 0) or 0),
                'retention_rate': str((total_spent / total_earned * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if total_earned > 0 else '0.00'
            }
        except Exception as e:
            logger.error(f"Error ghost wallet stats: {e}")
            return {'error': str(e)}

