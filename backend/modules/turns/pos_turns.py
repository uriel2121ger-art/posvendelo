"""
TITAN POS - POS Turn Methods (extracted from pos_engine.py)

Contains all turn/shift-related methods from the original POSEngine:
- Open/close turns
- Cash tracking
- Payment breakdown
"""

from typing import Any, Dict, Optional
from datetime import datetime
import logging
import math

logger = logging.getLogger("POS_ENGINE.turns")

# Import cache system
try:
    from app.utils.query_cache import query_cache, CACHE_ENABLED
except ImportError:
    CACHE_ENABLED = False
    query_cache = None


class POSTurnsMixin:
    """
    Mixin class containing all turn-related methods extracted from POSEngine.

    Requires from POSEngine:
        - self.db: Database access
        - self.current_turn_id: Current turn ID
    """

    def open_turn(self, user_id, initial_cash):
        """Abre un nuevo turno."""
        if user_id is None:
            raise ValueError("user_id es requerido")
        if isinstance(user_id, bool):
            raise ValueError("user_id no puede ser booleano")
        if isinstance(user_id, (list, dict, tuple, set)):
            raise ValueError(f"user_id inválido: tipo {type(user_id).__name__} no soportado")
        try:
            uid = int(user_id)
            if uid <= 0:
                raise ValueError(f"user_id debe ser mayor a 0, recibido: {uid}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"user_id inválido: {e}")

        if initial_cash is None:
            raise ValueError("initial_cash es requerido")
        if isinstance(initial_cash, (list, dict, tuple, set)):
            raise ValueError(f"initial_cash inválido: tipo {type(initial_cash).__name__} no soportado")
        try:
            cash = float(initial_cash)
            if math.isnan(cash) or math.isinf(cash):
                raise ValueError("initial_cash no puede ser NaN o Infinito")
            if cash < 0:
                raise ValueError(f"initial_cash no puede ser negativo: {cash}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"initial_cash inválido: {e}")

        rows = self.db.execute_query("SELECT id FROM turns WHERE user_id=%s AND status='open'", (uid,))
        if rows:
            self.current_turn_id = rows[0]['id']
            return self.current_turn_id

        sql = """
            INSERT INTO turns (user_id, start_timestamp, initial_cash, status)
            VALUES (%s, %s, %s, 'open')
        """
        self.current_turn_id = self.db.execute_write(sql, (uid, datetime.now().isoformat(), cash))

        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception as e: logger.warning(f"Cache clear failed: {e}")

        return self.current_turn_id

    def close_turn(self, user_id, final_cash, notes=None):
        """Cierra el turno actual y calcula diferencias."""
        if not self.current_turn_id:
            rows = self.db.execute_query("SELECT id, initial_cash FROM turns WHERE user_id=%s AND status='open'", (user_id,))
            if rows:
                self.current_turn_id = rows[0]['id']
                initial_cash = rows[0]['initial_cash']
            else:
                raise ValueError("No open turn found")
        else:
            rows = self.db.execute_query("SELECT initial_cash FROM turns WHERE id=%s", (self.current_turn_id,))
            initial_cash = rows[0]['initial_cash'] if rows else 0.0

        sales_rows = self.db.execute_query("""
            SELECT SUM(total) as total_sales
            FROM sales
            WHERE turn_id = %s AND payment_method = 'cash'
        """, (self.current_turn_id,))

        system_sales = sales_rows[0]['total_sales'] or 0.0 if sales_rows else 0.0

        payment_breakdown_rows = self.db.execute_query("""
            SELECT payment_method, COUNT(*) as transaction_count, SUM(total) as total_amount
            FROM sales
            WHERE turn_id = %s
            GROUP BY payment_method
        """, (self.current_turn_id,))

        payment_breakdown = {}
        total_sales_all_methods = 0.0
        for row in payment_breakdown_rows:
            method = row['payment_method'] or 'cash'
            payment_breakdown[method] = {
                'count': row['transaction_count'],
                'total': float(row['total_amount'] or 0.0)
            }
            total_sales_all_methods += float(row['total_amount'] or 0.0)

        movements_rows = self.db.execute_query("""
            SELECT
                SUM(CASE WHEN type = 'in' THEN amount ELSE 0 END) as total_in,
                SUM(CASE WHEN type = 'out' THEN amount ELSE 0 END) as total_out
            FROM cash_movements
            WHERE turn_id = %s
        """, (self.current_turn_id,))

        total_in = movements_rows[0]['total_in'] or 0.0 if movements_rows else 0.0
        total_out = movements_rows[0]['total_out'] or 0.0 if movements_rows else 0.0

        expected_cash = initial_cash + system_sales + total_in - total_out
        difference = final_cash - expected_cash

        sql = """
            UPDATE turns
            SET end_timestamp=%s, final_cash=%s, system_sales=%s, difference=%s, status='closed', notes=%s
            WHERE id=%s
        """
        self.db.execute_write(sql, (
            datetime.now().isoformat(),
            final_cash, system_sales, difference,
            notes or "", self.current_turn_id
        ))

        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception as e: logger.warning(f"Cache clear failed: {e}")

        self.current_turn_id = None
        return {
            "expected_cash": expected_cash,
            "difference": difference,
            "system_sales": system_sales,
            "total_in": total_in,
            "total_out": total_out,
            "initial_cash": initial_cash,
            "payment_breakdown": payment_breakdown,
            "total_sales_all_methods": total_sales_all_methods
        }


__all__ = ["POSTurnsMixin"]
