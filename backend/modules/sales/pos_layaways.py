"""
TITAN POS - POS Layaway Methods (extracted from pos_engine.py)

Contains all layaway (apartado) operations:
- Create, cancel layaways
- Layaway payments
- Layaway listing and querying
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger("POS_ENGINE.layaways")


class POSLayawaysMixin:
    """
    Mixin class containing all layaway methods extracted from POSEngine.

    Requires from POSEngine:
        - self.db: Database access
        - self._ensure_column_exists(): Column existence checker
    """

    def create_layaway(self, customer_id: int, items: List[Dict], initial_payment: float,
                       due_date: str, notes: str, user_id: int = 1) -> int:
        """Crea un nuevo apartado con transacción atómica."""
        total_amount = sum(float(item['price']) * float(item['qty']) for item in items)
        balance_due = total_amount - initial_payment

        created_at = datetime.now().isoformat()
        has_user_id = self._ensure_column_exists("inventory_log", "user_id", "INTEGER")

        ops = []

        layaway_sql = """
            INSERT INTO layaways (customer_id, total_amount, amount_paid, balance_due, status, created_at, due_date, notes, synced)
            VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, 0)
            RETURNING id
        """
        ops.append((layaway_sql, (customer_id, total_amount, initial_payment, balance_due, created_at, due_date, notes)))

        for item in items:
            product_id = item['product_id']
            qty = float(item['qty'])
            price = float(item['price'])
            total = qty * price

            item_sql = """INSERT INTO layaway_items (layaway_id, product_id, qty, price, total, synced)
                VALUES ((SELECT id FROM layaways WHERE customer_id = %s AND created_at = %s ORDER BY id DESC LIMIT 1), %s, %s, %s, %s, 0)"""
            ops.append((item_sql, (customer_id, created_at, product_id, qty, price, total)))

            ops.append(("UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, product_id)))

            if has_user_id:
                log_sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp, user_id) VALUES (%s, %s, %s, %s, %s)"
                ops.append((log_sql, (product_id, -qty, "Apartado (pendiente ID)", created_at, user_id)))
            else:
                log_sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp) VALUES (%s, %s, %s, %s)"
                ops.append((log_sql, (product_id, -qty, "Apartado (pendiente ID)", created_at)))

        result = self.db.execute_transaction(ops, timeout=10)
        if not result.get('success'):
            raise RuntimeError("Transaction failed - layaway not created")

        inserted_ids = result.get('inserted_ids', [])
        if not inserted_ids or inserted_ids[0] is None:
            raise RuntimeError("Failed to get layaway_id from transaction")

        layaway_id = inserted_ids[0]

        # Update log reasons with real layaway_id (non-critical)
        for item in items:
            try:
                self.db.execute_write(
                    "UPDATE inventory_log SET reason = %s WHERE product_id = %s AND reason = %s AND timestamp = %s LIMIT 1",
                    (f"Apartado #{layaway_id}", item['product_id'], "Apartado (pendiente ID)", created_at)
                )
            except Exception as e:
                logger.warning(f"No se pudo actualizar reason en inventory_log: {e}")

        if initial_payment > 0:
            turn_rows = self.db.execute_query("SELECT id FROM turns WHERE user_id = %s AND status = 'open' ORDER BY id DESC LIMIT 1", (user_id,))
            if turn_rows:
                turn_id = turn_rows[0]['id']
                has_user_id_cm = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
                if has_user_id_cm:
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id) VALUES (%s, 'in', %s, %s, %s, %s)",
                        (turn_id, initial_payment, f"Abono Inicial Apartado #{layaway_id}", created_at, user_id)
                    )
                else:
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp) VALUES (%s, 'in', %s, %s, %s)",
                        (turn_id, initial_payment, f"Abono Inicial Apartado #{layaway_id}", created_at)
                    )

        return layaway_id

    def add_layaway_payment(self, layaway_id: int, amount: float, user_id: int = 1, payment_data: Dict = None):
        """Registra un abono a un apartado."""
        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS layaway_payments (
                id SERIAL PRIMARY KEY,
                layaway_id INTEGER, amount REAL, method TEXT,
                reference TEXT, timestamp TEXT, user_id INTEGER
            )
        """)

        rows = self.db.execute_query("SELECT * FROM layaways WHERE id = %s", (layaway_id,))
        if not rows:
            raise ValueError("Apartado no encontrado")
        layaway = dict(rows[0])

        method = 'cash'
        reference = ''
        cash_portion = amount

        if payment_data:
            method = payment_data.get('method', 'cash')
            reference = payment_data.get('reference', '')
            if method == 'cash':
                cash_portion = amount
            elif method == 'mixed':
                breakdown = payment_data.get('mixed_breakdown', {})
                cash_portion = float(breakdown.get('cash', 0))
            else:
                cash_portion = 0

        new_paid = float(layaway['amount_paid']) + amount
        new_balance = float(layaway['total_amount']) - new_paid

        status = 'active'
        if new_balance <= 0.01:
            status = 'completed'
            new_balance = 0

        self.db.execute_write(
            "UPDATE layaways SET amount_paid = %s, balance_due = %s, status = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
            (new_paid, new_balance, status, layaway_id)
        )

        timestamp = datetime.now().isoformat()

        has_user_id = self._ensure_column_exists("layaway_payments", "user_id", "INTEGER")
        if has_user_id:
            self.db.execute_write(
                "INSERT INTO layaway_payments (layaway_id, amount, method, reference, timestamp, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (layaway_id, amount, method, reference, timestamp, user_id)
            )
        else:
            self.db.execute_write(
                "INSERT INTO layaway_payments (layaway_id, amount, method, reference, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (layaway_id, amount, method, reference, timestamp)
            )

        if cash_portion > 0:
            turn_rows = self.db.execute_query("SELECT id FROM turns WHERE user_id = %s AND status = 'open' ORDER BY id DESC LIMIT 1", (user_id,))
            if turn_rows:
                turn_id = turn_rows[0]['id']
                has_user_id_cm = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
                if has_user_id_cm:
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id) VALUES (%s, 'in', %s, %s, %s, %s)",
                        (turn_id, cash_portion, f"Abono Apartado #{layaway_id} ({method})", timestamp, user_id)
                    )
                else:
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp) VALUES (%s, 'in', %s, %s, %s)",
                        (turn_id, cash_portion, f"Abono Apartado #{layaway_id} ({method})", timestamp)
                    )

        return status

    def cancel_layaway(self, layaway_id: int, user_id: int = 1):
        """Cancela un apartado y devuelve items al inventario."""
        rows = self.db.execute_query("SELECT * FROM layaways WHERE id = %s", (layaway_id,))
        if not rows:
            raise ValueError("Apartado no encontrado")
        layaway = dict(rows[0])

        if layaway['status'] != 'active':
            raise ValueError("Solo se pueden cancelar apartados activos")

        timestamp = datetime.now().isoformat()
        items = list(self.db.execute_query("SELECT * FROM layaway_items WHERE layaway_id = %s", (layaway_id,)))
        has_user_id = self._ensure_column_exists("inventory_log", "user_id", "INTEGER")

        ops = []
        ops.append(("UPDATE layaways SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s", (layaway_id,)))

        for item in items:
            qty = float(item['qty'])
            product_id = item['product_id']
            ops.append(("UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, product_id)))
            if has_user_id:
                ops.append(("INSERT INTO inventory_log (product_id, qty_change, reason, timestamp, user_id) VALUES (%s, %s, %s, %s, %s)",
                            (product_id, qty, f"Cancelación Apartado #{layaway_id}", timestamp, user_id)))
            else:
                ops.append(("INSERT INTO inventory_log (product_id, qty_change, reason, timestamp) VALUES (%s, %s, %s, %s)",
                            (product_id, qty, f"Cancelación Apartado #{layaway_id}", timestamp)))

        result = self.db.execute_transaction(ops, timeout=10)
        if not result.get('success'):
            raise RuntimeError("Transaction failed - layaway not cancelled")

    def list_layaways(self, branch_id: int = 1, status: str = "active", date_range: tuple = None) -> List[Dict]:
        sql = """
            SELECT l.*, c.name as customer_name,
                   l.total_amount as total, l.amount_paid as paid_total, l.balance_due as balance_calc
            FROM layaways l LEFT JOIN customers c ON l.customer_id = c.id WHERE 1=1
        """
        params = []
        if status and status != "all":
            sql += " AND l.status = %s"
            params.append(status)
        if date_range:
            start, end = date_range
            sql += " AND date(l.created_at) BETWEEN %s AND %s"
            params.extend([start, end])
        sql += " ORDER BY l.created_at DESC"
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_layaway(self, layaway_id: int) -> Optional[Dict]:
        rows = self.db.execute_query("""
            SELECT l.*, c.name as customer_name,
                   l.total_amount as total, l.amount_paid as paid_total, l.balance_due as balance_calc
            FROM layaways l LEFT JOIN customers c ON l.customer_id = c.id WHERE l.id = %s
        """, (layaway_id,))
        return dict(rows[0]) if rows else None

    def get_layaway_items(self, layaway_id: int) -> List[Dict]:
        sql = """SELECT li.*, p.name FROM layaway_items li JOIN products p ON li.product_id = p.id WHERE li.layaway_id = %s"""
        return [dict(row) for row in self.db.execute_query(sql, (layaway_id,))]

    def get_layaway_payments(self, layaway_id: int) -> List[Dict]:
        sql_new = "SELECT * FROM layaway_payments WHERE layaway_id = %s ORDER BY timestamp DESC"
        rows_new = self.db.execute_query(sql_new, (layaway_id,))
        if rows_new:
            return [dict(r) for r in rows_new]
        sql_legacy = """SELECT * FROM cash_movements WHERE reason LIKE %s OR reason LIKE %s ORDER BY timestamp DESC"""
        return [dict(row) for row in self.db.execute_query(sql_legacy, (f"Abono Apartado #{layaway_id}", f"Abono Inicial Apartado #{layaway_id}"))]


__all__ = ["POSLayawaysMixin"]
