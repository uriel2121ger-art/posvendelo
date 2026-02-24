"""
Turn Repository - Centralized turn data access
Moves all turn-related SQL logic from core.py to repository layer
"""
from typing import Any, Dict, List, Optional
import math

from app.repositories.base_repository import BaseRepository


class TurnRepository(BaseRepository):
    """Repository for turn data access"""
    
    def __init__(self):
        """Initialize turn repository"""
        super().__init__('turns')
    
    def _validate_user_id(self, user_id: int) -> int:
        """Validate user_id parameter."""
        if user_id is None:
            raise ValueError("user_id es requerido")
        if isinstance(user_id, bool):
            raise ValueError("user_id no puede ser booleano")
        if isinstance(user_id, (list, dict, tuple, set)):
            raise ValueError(f"user_id inválido: tipo {type(user_id).__name__}")
        try:
            uid = int(user_id)
            if uid <= 0:
                raise ValueError(f"user_id debe ser mayor a 0: {uid}")
            return uid
        except (TypeError, ValueError) as e:
            raise ValueError(f"user_id inválido: {e}")
    
    def _validate_cash(self, cash: float, param_name: str = "cash") -> float:
        """Validate cash amount parameter."""
        if cash is None:
            raise ValueError(f"{param_name} es requerido")
        if isinstance(cash, (list, dict, tuple, set)):
            raise ValueError(f"{param_name} inválido: tipo {type(cash).__name__}")
        try:
            amount = float(cash)
            if math.isnan(amount) or math.isinf(amount):
                raise ValueError(f"{param_name} no puede ser NaN o Infinito")
            if amount < 0:
                raise ValueError(f"{param_name} no puede ser negativo: {amount}")
            return amount
        except (TypeError, ValueError) as e:
            raise ValueError(f"{param_name} inválido: {e}")
    
    def find_current_by_user(self, user_id: int) -> Optional[Dict]:
        """
        Get current open turn for user
        
        Args:
            user_id: User ID
        
        Returns:
            Turn dict if found, None otherwise
        """
        uid = self._validate_user_id(user_id)
        # SECURITY: Especificar columnas en lugar de SELECT *
        rows = self.db.execute_query(
            "SELECT id, user_id, start_timestamp, end_timestamp, initial_cash, final_cash, status, notes, difference FROM turns WHERE user_id = %s AND status = 'OPEN' ORDER BY id DESC LIMIT 1",
            (uid,)
        )
        # FIX 2026-02-01: Validar rows antes de acceder a rows[0] para evitar IndexError
        if not rows or len(rows) == 0:
            return None
        return dict(rows[0])
    
    def create_turn(self, user_id: int, initial_cash: float, notes: str = None) -> int:
        """
        Create a new turn
        
        Args:
            user_id: User ID
            initial_cash: Initial cash amount
            notes: Optional notes
        
        Returns:
            New turn ID
        """
        from datetime import datetime

        # Validaciones
        uid = self._validate_user_id(user_id)
        cash = self._validate_cash(initial_cash, "initial_cash")
        
        query = """
            INSERT INTO turns (user_id, start_timestamp, initial_cash, status, notes)
            VALUES (%s, %s, %s, 'OPEN', %s)
        """
        
        turn_id = self.db.execute_write(
            query,
            (uid, datetime.now().isoformat(), cash, notes)
        )
        
        return turn_id
    
    def close_turn(self, turn_id: int, final_cash: float) -> None:
        """
        Close a turn
        
        Args:
            turn_id: Turn ID to close
            final_cash: Final cash count
        """
        from datetime import datetime

        # Validar turn_id
        if turn_id is None:
            raise ValueError("turn_id es requerido")
        if isinstance(turn_id, (list, dict, tuple, set)):
            raise ValueError(f"turn_id inválido: tipo {type(turn_id).__name__}")
        try:
            tid = int(turn_id)
            if tid <= 0:
                raise ValueError(f"turn_id debe ser mayor a 0: {tid}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"turn_id inválido: {e}")
        
        # Validar final_cash
        fcash = self._validate_cash(final_cash, "final_cash")
        
        # Get turn data
        turn = self.find_by_id(tid)
        if not turn:
            raise ValueError(f"Turn {turn_id} not found")
        
        # Calculate difference
        initial = float(turn.get('initial_cash', 0))
        difference = final_cash - initial
        
        query = """
            UPDATE turns 
            SET status = 'CLOSED',
                end_timestamp = %s,
                final_cash = %s,
                difference = %s
            WHERE id = %s
        """
        
        self.db.execute_write(
            query,
            (datetime.now().isoformat(), final_cash, difference, turn_id)
        )
    
    def get_summary(self, turn_id: int) -> Dict[str, Any]:
        """
        Get comprehensive turn summary with sales totals
        
        Args:
            turn_id: Turn ID
        
        Returns:
            Dictionary with turn summary data
        """
        turn = self.find_by_id(turn_id)
        if not turn:
            return {}
        
        turn_dict = dict(turn)
        initial_cash = float(turn_dict.get('initial_cash', 0))
        
        # Get sales breakdown by payment method
        payment_breakdown = self.db.execute_query("""
            SELECT 
                payment_method,
                COUNT(*) as transaction_count,
                COALESCE(SUM(total), 0) as total_amount,
                COALESCE(SUM(cash_received), 0) as cash_collected,
                COALESCE(SUM(mixed_cash), 0) as mixed_cash_amount
            FROM sales
            WHERE turn_id = %s AND status != 'cancelled'
            GROUP BY payment_method
        """, (turn_id,))
        
        # Convert to list of dicts
        breakdown = [dict(row) for row in payment_breakdown]
        
        # Calculate totals
        total_sales = sum(float(row.get('total_amount', 0)) for row in breakdown)
        cash_total = sum(
            float(row.get('cash_collected', 0) or row.get('total_amount', 0))
            for row in breakdown
            if row.get('payment_method') in ('cash', 'mixed')
        )
        cash_total += sum(float(row.get('mixed_cash_amount', 0)) for row in breakdown)
        
        # Get movements
        movements_in = self.db.execute_query("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM turn_movements
            WHERE turn_id = %s AND movement_type = 'in'
        """, (turn_id,))
        
        movements_out = self.db.execute_query("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM turn_movements
            WHERE turn_id = %s AND movement_type = 'out'
        """, (turn_id,))

        total_in = float(movements_in[0]['total'] or 0) if movements_in else 0
        total_out = float(movements_out[0]['total'] or 0) if movements_out else 0
        
        # Expected cash = initial + cash sales + in - out
        expected_cash = initial_cash + cash_total + total_in - total_out
        
        return {
            'turn_id': turn_id,
            'user_id': turn_dict.get('user_id'),
            'initial_cash': initial_cash,
            'final_cash': float(turn_dict.get('final_cash', 0)),
            'expected_cash': round(expected_cash, 2),
            'cash_sales': round(cash_total, 2),
            'total_sales': round(total_sales, 2),
            'total_in': round(total_in, 2),
            'total_out': round(total_out, 2),
            'difference': float(turn_dict.get('difference', 0)),
            'payment_breakdown': breakdown,
            'status': turn_dict.get('status'),
            'start_timestamp': turn_dict.get('start_timestamp'),
            'end_timestamp': turn_dict.get('end_timestamp'),
        }
    
    def find_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Find turns within date range
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            List of turn dicts
        """
        # SECURITY: Especificar columnas y agregar LIMIT
        rows = self.db.execute_query("""
            SELECT id, user_id, start_timestamp, end_timestamp, initial_cash, final_cash, status, notes, difference
            FROM turns
            WHERE start_timestamp BETWEEN %s AND %s
            ORDER BY start_timestamp DESC
            LIMIT 1000
        """, (start_date, end_date + " 23:59:59"))
        
        return [dict(row) for row in rows]
    
    def get_user_turns(self, user_id: int, limit: int = 50) -> List[Dict]:
        """
        Get recent turns for a user

        Args:
            user_id: User ID
            limit: Maximum number of turns to return

        Returns:
            List of turn dicts
        """
        # SECURITY: Parameterize LIMIT and specify columns
        limit = max(1, min(int(limit), 1000))  # Clamp between 1-1000
        rows = self.db.execute_query("""
            SELECT id, user_id, start_timestamp, end_timestamp, initial_cash, final_cash, status, notes, difference
            FROM turns
            WHERE user_id = %s
            ORDER BY start_timestamp DESC
            LIMIT %s
        """, (user_id, limit))

        return [dict(row) for row in rows]
