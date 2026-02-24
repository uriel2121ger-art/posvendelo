"""
TITAN POS - POS Customer Methods (extracted from pos_engine.py)

Contains all customer-related methods from the original POSEngine:
- Customer CRUD
- Credit info
- Wallet operations (monedero)
- Customer search
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger("POS_ENGINE.customers")

# Import cache system
try:
    from app.utils.query_cache import query_cache, CACHE_ENABLED
except ImportError:
    CACHE_ENABLED = False
    query_cache = None


class POSCustomersMixin:
    """
    Mixin class containing all customer-related methods extracted from POSEngine.

    Requires from POSEngine:
        - self.db: Database access
        - self._ensure_column_exists(): Column existence checker
    """

    def create_customer(self, data: Dict[str, Any]) -> int:
        """Crea un nuevo cliente con validaciones."""
        if not data.get('name'):
            raise ValueError("El nombre del cliente es obligatorio")

        email = data.get('email', '').strip()
        if email and '@' not in email:
            raise ValueError("Formato de email inválido")

        phone = data.get('phone', '').strip()
        if phone and len(phone) < 7:
            raise ValueError("Número de teléfono debe tener al menos 7 dígitos")

        credit_limit = data.get('credit_limit', 0)
        if credit_limit < 0:
            raise ValueError("Límite de crédito no puede ser negativo")

        keys = [
            "name", "rfc", "email", "phone", "credit_limit", "address", "notes",
            "first_name", "last_name", "email_fiscal", "razon_social", "regimen_fiscal",
            "domicilio1", "domicilio2", "colonia", "municipio", "estado", "pais", "codigo_postal",
            "vip", "credit_authorized"
        ]
        valid_data = {k: data.get(k) for k in keys if k in data}

        for bool_field in ["vip", "credit_authorized"]:
            if bool_field in valid_data:
                val = valid_data[bool_field]
                if isinstance(val, bool):
                    valid_data[bool_field] = 1 if val else 0
                elif isinstance(val, str):
                    val_str = str(val).lower().strip()
                    valid_data[bool_field] = 1 if val_str in ["sí", "si", "yes", "true", "1", "verdadero"] else 0
                elif val is None:
                    valid_data[bool_field] = 0

        ALLOWED_CUSTOMER_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_CUSTOMER_COLUMNS:
                raise ValueError(f"Columna no permitida en customers: {col}")

        columns = ", ".join(valid_data.keys())
        placeholders = ", ".join(["%s"] * len(valid_data))
        values = tuple(valid_data.values())

        sql = f"INSERT INTO customers ({columns}, synced) VALUES ({placeholders}, 0)"
        result = self.db.execute_write(sql, values)

        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception as e: logger.warning(f"Cache clear failed: {e}")

        return result

    def update_customer(self, customer_id: int, data: Dict[str, Any]):
        """Actualiza un cliente existente."""
        keys = [
            "name", "rfc", "email", "phone", "credit_limit", "address", "notes", "is_active",
            "first_name", "last_name", "email_fiscal", "razon_social", "regimen_fiscal",
            "domicilio1", "domicilio2", "colonia", "municipio", "estado", "pais", "codigo_postal",
            "vip", "credit_authorized"
        ]
        valid_data = {k: data.get(k) for k in keys if k in data}
        if not valid_data:
            return

        for bool_field in ["vip", "credit_authorized", "is_active"]:
            if bool_field in valid_data:
                val = valid_data[bool_field]
                if isinstance(val, bool):
                    valid_data[bool_field] = 1 if val else 0
                elif isinstance(val, str):
                    val_str = str(val).lower().strip()
                    valid_data[bool_field] = 1 if val_str in ["sí", "si", "yes", "true", "1", "verdadero"] else 0
                elif val is None:
                    valid_data[bool_field] = 0

        ALLOWED_CUSTOMER_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_CUSTOMER_COLUMNS:
                raise ValueError(f"Columna no permitida en customers: {col}")

        set_clause = ", ".join([f"{k} = %s" for k in valid_data.keys()])
        values = tuple(valid_data.values()) + (customer_id,)

        sql = f"UPDATE customers SET {set_clause}, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, values)

        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception as e: logger.warning(f"Cache clear failed: {e}")

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query("SELECT * FROM customers WHERE id = %s", (customer_id,))
        return dict(rows[0]) if rows else None

    def list_customers(self, query: str = None, limit: int = 300) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM customers WHERE is_active = 1"
        params = []
        if query:
            sql += " AND (name LIKE %s OR rfc LIKE %s)"
            params = [f"%{query}%", f"%{query}%"]
        sql += " LIMIT %s"
        params.append(limit)
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def delete_customer(self, customer_id: int):
        sql = "UPDATE customers SET is_active = 0, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, (customer_id,))

    def search_customers(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM customers WHERE is_active = 1 AND (name LIKE %s OR rfc LIKE %s OR phone LIKE %s) LIMIT %s"
        params = [f"%{query}%", f"%{query}%", f"%{query}%", limit]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_customer_credit_info(self, customer_id: int) -> Dict[str, Any]:
        rows = self.db.execute_query("SELECT credit_limit, credit_balance FROM customers WHERE id = %s", (customer_id,))
        if rows:
            row = dict(rows[0])
            limit = row.get('credit_limit') or 0.0
            balance = row.get('credit_balance') or 0.0
            return {"credit_limit": limit, "credit_balance": balance, "credit_authorized": limit > 0}
        return {"credit_limit": 0, "credit_balance": 0, "credit_authorized": False}

    def get_wallet_balance(self, customer_id: int) -> float:
        rows = self.db.execute_query("SELECT wallet_balance FROM customers WHERE id = %s", (customer_id,))
        if rows:
            return float(rows[0]['wallet_balance'] or 0.0)
        return 0.0

    def deduct_from_wallet(self, customer_id: int, amount: float, reason: str, ref_id: int = None):
        """Deduce cantidad del monedero (transacción atómica con FOR UPDATE)."""
        has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
        has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")

        def validate_sufficient_balance(select_results):
            if not select_results or select_results[0] is None:
                raise ValueError(f"Cliente {customer_id} no encontrado")
            balance_before = float(select_results[0].get('wallet_balance') or 0.0)
            if balance_before < amount:
                raise ValueError(
                    f"Saldo insuficiente en monedero. "
                    f"Disponible: ${balance_before:.2f}, Solicitado: ${amount:.2f}"
                )

        ops = [
            ("SELECT wallet_balance FROM customers WHERE id = %s FOR UPDATE", (customer_id,)),
            ("UPDATE customers SET wallet_balance = wallet_balance - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (amount, customer_id)),
        ]

        if has_movement_type and has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, movement_type)
                SELECT %s, 'WALLET_DEDUCT', %s, wallet_balance + %s, wallet_balance, NOW(), %s, %s, 'WALLET'
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, -amount, amount, reason or 'Deducción de monedero', ref_id, customer_id)))
        elif has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id)
                SELECT %s, 'WALLET_DEDUCT', %s, wallet_balance + %s, wallet_balance, NOW(), %s, %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, -amount, amount, reason or 'Deducción de monedero', ref_id, customer_id)))
        else:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes)
                SELECT %s, 'WALLET_DEDUCT', %s, wallet_balance + %s, wallet_balance, NOW(), %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, -amount, amount, reason or 'Deducción de monedero', customer_id)))

        result = self.db.execute_transaction(ops, timeout=5, validation_callback=validate_sufficient_balance)
        if not result.get('success'):
            raise RuntimeError("Error al deducir del monedero: transacción falló")

    def add_to_wallet(self, customer_id: int, amount: float, reason: str, ref_id: int = None):
        """Agrega cantidad al monedero (transacción atómica con FOR UPDATE)."""
        has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
        has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")

        def validate_customer_exists(select_results):
            if not select_results or select_results[0] is None:
                raise ValueError(f"Cliente {customer_id} no encontrado")

        ops = [
            ("SELECT wallet_balance FROM customers WHERE id = %s FOR UPDATE", (customer_id,)),
            ("UPDATE customers SET wallet_balance = wallet_balance + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (amount, customer_id)),
        ]

        if has_movement_type and has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, movement_type)
                SELECT %s, 'WALLET_ADD', %s, wallet_balance - %s, wallet_balance, NOW(), %s, %s, 'WALLET'
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, amount, amount, reason or 'Adición a monedero', ref_id, customer_id)))
        elif has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id)
                SELECT %s, 'WALLET_ADD', %s, wallet_balance - %s, wallet_balance, NOW(), %s, %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, amount, amount, reason or 'Adición a monedero', ref_id, customer_id)))
        else:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes)
                SELECT %s, 'WALLET_ADD', %s, wallet_balance - %s, wallet_balance, NOW(), %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, amount, amount, reason or 'Adición a monedero', customer_id)))

        result = self.db.execute_transaction(ops, timeout=5, validation_callback=validate_customer_exists)
        if not result.get('success'):
            raise RuntimeError("Error al agregar al monedero: transacción falló")


__all__ = ["POSCustomersMixin"]
