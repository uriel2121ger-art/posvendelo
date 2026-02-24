"""
GIFT CARD ENGINE
Sistema de tarjetas de regalo con seguridad y validación
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import secrets
import string
import logging

if TYPE_CHECKING:
    from src.infra.database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class GiftCard:
    """Gift card data structure."""
    code: str
    balance: Decimal
    initial_balance: Decimal
    status: str
    expiration_date: str
    created_at: str
    activated_at: Optional[str]
    customer_id: Optional[int]
    notes: Optional[str]

class GiftCardEngine:
    """
    Motor de Tarjetas de Regalo
    
    Features:
    - Generación de códigos seguros alfanuméricos
    - Activación de tarjetas
    - Consulta de saldo
    - Redención (uso parcial o total)
    - Expiración automática
    - Auditoría completa de transacciones
    """
    
    def __init__(self, db_manager: "DatabaseManager"):
        """
        Initialize Gift Card Engine.
        
        Args:
            db_manager: DatabaseManager instance (supports SQLite and PostgreSQL)
        """
        self.db = db_manager
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure gift card tables exist."""
        # Schema should already be created by schema_postgresql.sql
        # Just verify tables exist
        try:
            tables = self.db.list_tables()
            if 'gift_cards' not in tables:
                logger.warning("gift_cards table not found. Schema may need to be applied.")
        except Exception as e:
            logger.error(f"Error verifying gift_cards schema: {e}")
    
    def generate_code(self) -> str:
        """
        Generate a secure, unique gift card code.
        
        Format: GC-XXXX-XXXX-XXXX (16 alphanumeric characters)
        Uses cryptographically secure random generation.
        """
        # Generate 12 random alphanumeric characters
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(secrets.choice(chars) for _ in range(12))
        
        # Format as GC-XXXX-XXXX-XXXX
        code = f"GC-{random_part[:4]}-{random_part[4:8]}-{random_part[8:12]}"
        
        # Verify uniqueness
        existing = self.db.execute_query(
            "SELECT code FROM gift_cards WHERE UPPER(code) = UPPER(%s)",
            (code,)
        )
        if existing:
            # Extremely unlikely, but regenerate if collision
            return self.generate_code()
        
        return code
    
    def create_card(
        self,
        initial_balance: Decimal,
        customer_id: Optional[int] = None,
        expiration_months: int = 12,
        notes: Optional[str] = None,
        code: Optional[str] = None
    ) -> str:
        """
        Create a new gift card.

        Args:
            initial_balance: Initial amount loaded
            customer_id: Optional customer who purchased it
            expiration_months: Months until expiration (default 12)
            notes: Optional notes
            code: Optional custom code (auto-generated if None)

        Returns:
            Card code
        """
        if code is None:
            code = self.generate_code()
        created_at = datetime.now().isoformat()
        expiration_date = (datetime.now() + timedelta(days=30 * expiration_months)).isoformat()
        
        # Insert gift card - safe float conversion
        try:
            initial_balance_float = float(initial_balance)
        except (ValueError, TypeError):
            initial_balance_float = 0.0

        self.db.execute_write("""
            INSERT INTO gift_cards
            (code, balance, initial_balance, status, expiration_date, created_at, customer_id, notes, synced)
            VALUES (%s, %s, %s, 'inactive', %s, %s, %s, %s, 0)
        """, (code, 0.0, initial_balance_float, expiration_date, created_at, customer_id, notes))
        
        return code
    
    def activate_card(self, code: str, user_id: Optional[int] = None) -> bool:
        """
        Activate a gift card (load initial balance).
        
        Args:
            code: Gift card code
            user_id: User activating the card
            
        Returns:
            True if activated successfully
        """
        # Get card
        cards = self.db.execute_query(
            "SELECT * FROM gift_cards WHERE UPPER(code) = UPPER(%s)",
            (code,)
        )
        if not cards or len(cards) == 0 or not cards[0]:
            raise ValueError(f"Gift card {code} not found")

        card = dict(cards[0])
        if card.get('status') != 'inactive':
            raise ValueError(f"Card {code} already activated or invalid status: {card.get('status')}")
        
        # Activate card
        activated_at = datetime.now().isoformat()
        initial_balance = card.get('initial_balance', 0)
        
        # Use transaction for atomicity
        operations = [
            (
                """
                UPDATE gift_cards
                SET balance = %s, status = 'active', activated_at = %s
                WHERE code = %s
                """,
                (initial_balance, activated_at, code)
            ),
            (
                """
                INSERT INTO card_transactions
                (card_code, type, amount, balance_after, timestamp, user_id, notes)
                VALUES (%s, 'load', %s, %s, %s, %s, 'Initial activation')
                """,
                (code, initial_balance, initial_balance, activated_at, user_id)
            )
        ]
        
        self.db.execute_transaction(operations)
        
        return True
    
    def get_balance(self, code: str) -> Decimal:
        """
        Get current balance of a gift card.
        
        Args:
            code: Gift card code
            
        Returns:
            Current balance
        """
        cards = self.db.execute_query(
            "SELECT balance, status FROM gift_cards WHERE UPPER(code) = UPPER(%s)",
            (code,)
        )
        if not cards or len(cards) == 0 or not cards[0]:
            raise ValueError(f"Gift card {code} not found")

        card = dict(cards[0])
        return Decimal(str(card.get('balance', 0)))
    
    def validate_card(self, code: str) -> Dict:
        """
        Validate a gift card and return its status.
        
        Returns:
            {
                'valid': bool,
                'balance': Decimal,
                'status': str,
                'expiration_date': str,
                'message': str
            }
        """
        cards = self.db.execute_query(
            "SELECT * FROM gift_cards WHERE UPPER(code) = UPPER(%s)",
            (code,)
        )
        
        if not cards:
            return {
                'valid': False,
                'balance': Decimal('0'),
                'status': 'not_found',
                'message': 'Tarjeta no encontrada'
            }
        
        card = dict(cards[0])
        
        # Check expiration
        try:
            exp_date = datetime.fromisoformat(str(card['expiration_date']))
        except (ValueError, TypeError):
            return {
                'valid': False,
                'balance': Decimal(str(card.get('balance', 0))),
                'status': 'invalid',
                'message': 'Fecha de expiración inválida'
            }
        if exp_date < datetime.now():
            # Auto-expire
            self.db.execute_write(
                "UPDATE gift_cards SET status = 'expired' WHERE code = %s",
                (code,)
            )
            return {
                'valid': False,
                'balance': Decimal(str(card['balance'])),
                'status': 'expired',
                'expiration_date': card['expiration_date'],
                'message': 'Tarjeta expirada'
            }
        
        # Check status
        if card['status'] not in ('active', 'inactive'):
            return {
                'valid': False,
                'balance': Decimal(str(card['balance'])),
                'status': card['status'],
                'message': f"Tarjeta no válida: {card['status']}"
            }
        
        # Valid card
        return {
            'valid': True,
            'balance': Decimal(str(card['balance'])),
            'status': card['status'],
            'expiration_date': card['expiration_date'],
            'message': 'Tarjeta válida'
        }
    
    def redeem(
        self,
        code: str,
        amount: Decimal,
        sale_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Decimal:
        """
        Redeem (spend) from a gift card.
        
        Args:
            code: Gift card code
            amount: Amount to spend
            sale_id: Optional sale ID
            user_id: User performing redemption
            
        Returns:
            New balance after redemption
        """
        # Validate card
        validation = self.validate_card(code)
        if not validation['valid']:
            raise ValueError(validation['message'])
        
        current_balance = validation['balance']
        
        # Check sufficient balance
        if amount > current_balance:
            raise ValueError(f"Saldo insuficiente. Disponible: ${current_balance:.2f}")
        
        # Calculate new balance
        new_balance = current_balance - amount
        
        # Update card and record transaction atomically
        new_status = 'depleted' if new_balance <= Decimal('0.01') else 'active'
        operations = [
            (
                """
                UPDATE gift_cards
                SET balance = %s, status = %s
                WHERE code = %s
                """,
                (float(new_balance), new_status, code)
            ),
            (
                """
                INSERT INTO card_transactions
                (card_code, type, amount, balance_after, sale_id, timestamp, user_id)
                VALUES (%s, 'spend', %s, %s, %s, %s, %s)
                """,
                (code, float(amount), float(new_balance), sale_id, datetime.now().isoformat(), user_id)
            )
        ]
        
        self.db.execute_transaction(operations)
        
        return new_balance
    
    def get_card_history(self, code: str) -> List[Dict]:
        """Get transaction history for a card."""
        rows = self.db.execute_query("""
            SELECT * FROM card_transactions
            WHERE card_code = %s
            ORDER BY timestamp DESC
        """, (code,))
        
        return [dict(row) for row in rows]
    
    def list_cards(self, status: Optional[str] = None, customer_id: Optional[int] = None) -> List[Dict]:
        """List gift cards with optional filters."""
        query = "SELECT * FROM gift_cards WHERE 1=1"
        params = []

        if status:
            # FIX 2026-02-01: PostgreSQL usa %s en lugar de ?
            query += " AND status = %s"
            params.append(status)

        if customer_id:
            # FIX 2026-02-01: PostgreSQL usa %s en lugar de ?
            query += " AND customer_id = %s"
            params.append(customer_id)
        
        query += " ORDER BY created_at DESC"
        
        rows = self.db.execute_query(query, tuple(params))
        return [dict(row) for row in rows]
