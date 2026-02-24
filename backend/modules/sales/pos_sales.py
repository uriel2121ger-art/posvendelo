"""
TITAN POS - POS Sales Methods (extracted from pos_engine.py)

Contains all sales-related methods from the original POSEngine:
- Cart management (add_to_cart, calculate_cart_totals, get_cart_total)
- Checkout process
- Sale transaction creation
- Layaway operations
- Fiscal series and folio generation
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from src.core.finance import Money

logger = logging.getLogger("POS_ENGINE.sales")

# Import cache system
try:
    from app.utils.query_cache import query_cache, CACHE_ENABLED
except ImportError:
    CACHE_ENABLED = False
    query_cache = None


class POSSalesMixin:
    """
    Mixin class containing all sales-related methods extracted from POSEngine.

    This class is not meant to be instantiated directly. It should be
    mixed into POSEngine to provide sales functionality.

    Requires from POSEngine:
        - self.db: Database access
        - self.current_cart: List of cart items
        - self.current_customer: Current customer dict or None
        - self.current_turn_id: Current turn ID
        - self.global_discount_pct: Global discount percentage
        - self.TAX_RATE: Tax rate constant
        - self._ensure_column_exists(): Column existence checker
        - self.get_product_by_id(): Product lookup
        - self.get_kit_components(): Kit component lookup
    """

    def set_customer(self, customer_id: int):
        """Asigna un cliente a la venta actual."""
        if customer_id is None:
            raise ValueError("customer_id no puede ser None")
        if not isinstance(customer_id, int):
            raise ValueError("customer_id debe ser un entero")
        if customer_id <= 0:
            raise ValueError("customer_id debe ser mayor que 0")
        rows = self.db.execute_query("SELECT * FROM customers WHERE id = %s", (customer_id,))
        if rows:
            self.current_customer = dict(rows[0])
            return True
        return False

    def set_global_discount(self, percentage: float):
        """Aplica un descuento global (0-100)."""
        import math
        if math.isnan(percentage) or math.isinf(percentage):
            raise ValueError("El descuento no puede ser NaN ni infinito")
        if not (0 <= percentage <= 100):
            raise ValueError("El descuento debe estar entre 0 y 100")
        self.global_discount_pct = percentage

    def calculate_cart_totals(self) -> Dict[str, Money]:
        """Calcula subtotales, descuentos, impuestos y total."""
        subtotal = Money(0)
        for item in self.current_cart:
            subtotal += item['total']

        discount_amount = subtotal * (self.global_discount_pct / 100.0)
        subtotal_after_discount = subtotal - discount_amount

        tax = subtotal_after_discount * self.TAX_RATE
        total = subtotal_after_discount + tax

        return {
            "subtotal": subtotal,
            "discount": discount_amount,
            "tax": tax,
            "total": total
        }

    def determine_serie(self, payment_method: str, cliente_pide_factura: bool = False,
                        mixed_breakdown: dict = None) -> str:
        """
        Lógica Maestra de Asignación de Serie.
        'A' (Fiscal/SAT) or 'B' (Interno).
        """
        if cliente_pide_factura:
            return 'A'

        metodos_fiscales = ['card', 'transfer', 'check', 'usd']
        if payment_method in metodos_fiscales:
            return 'A'

        if payment_method == 'mixed' and mixed_breakdown:
            if float(mixed_breakdown.get('card', 0) or 0) > 0:
                return 'A'
            if float(mixed_breakdown.get('transfer', 0) or 0) > 0:
                return 'A'
            if float(mixed_breakdown.get('check', 0) or 0) > 0:
                return 'A'
            if float(mixed_breakdown.get('usd', 0) or 0) > 0:
                return 'A'

        return 'B'

    def get_next_folio(self, serie: str, terminal_id: int = 1) -> str:
        """Get next folio number atomically with terminal support."""
        try:
            self.db.execute_write(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) "
                "VALUES (%s, %s, 0, %s, 0) ON CONFLICT (serie, terminal_id) DO NOTHING",
                (serie, terminal_id, f"{serie} Terminal {terminal_id}")
            )
        except Exception as e:
            error_str = str(e).lower()
            if 'duplicate' not in error_str and 'unique' not in error_str:
                raise

        numero = self.db.execute_write(
            """UPDATE secuencias
               SET ultimo_numero = ultimo_numero + 1
               WHERE serie = %s AND terminal_id = %s
               RETURNING ultimo_numero""",
            (serie, terminal_id)
        )
        if numero:
            return f"{serie}{terminal_id}-{int(numero):06d}"

        fallback_result = self.db.execute_query(
            "SELECT ultimo_numero FROM secuencias WHERE serie = %s AND terminal_id = %s",
            (serie, terminal_id)
        )
        if fallback_result:
            numero = fallback_result[0]['ultimo_numero']
            return f"{serie}{terminal_id}-{numero:06d}"
        return f"{serie}{terminal_id}-000001"

    def add_to_cart(self, identifier: str, qty: float = 1.0) -> Dict[str, Any]:
        """Agrega producto al carrito por SKU o ID."""
        rows = self.db.execute_query("SELECT * FROM products WHERE sku = %s", (identifier,))
        if not rows:
            try:
                rows = self.db.execute_query("SELECT * FROM products WHERE id = %s", (int(identifier),))
            except (ValueError, TypeError):
                pass

        if not rows:
            raise ValueError(f"Producto no encontrado: {identifier}")

        product = dict(rows[0])

        current_stock = float(product.get('stock') or 0)
        sale_type = product.get('sale_type', 'unit')
        sku = product.get('sku', '')
        is_kit = product.get('is_kit', False) or sale_type == 'kit'
        is_common_product = sku.startswith('COM-') or sku.startswith('COMUN-')

        in_cart_qty = sum(item['qty'] for item in self.current_cart if item['product_id'] == product['id'])
        total_requested = in_cart_qty + qty

        if is_kit:
            components = self.get_kit_components(product['id'])
            for comp in components:
                comp_product_id = comp.get('child_product_id')
                comp_qty = float(comp.get('qty', 1.0))
                total_comp_qty = total_requested * comp_qty
                comp_product = self.get_product_by_id(comp_product_id)
                if comp_product:
                    comp_stock = float(comp_product.get('stock', 0))
                    comp_sku = comp_product.get('sku', '')
                    is_comp_common = comp_sku.startswith('COM-') or comp_sku.startswith('COMUN-')
                    if not is_comp_common and comp_stock < total_comp_qty:
                        comp_name = comp_product.get('name', f"ID {comp_product_id}")
                        raise ValueError(
                            f"Stock insuficiente de componente '{comp_name}' para KIT '{product['name']}'. "
                            f"Disponible: {comp_stock}, Necesario: {total_comp_qty}"
                        )
        elif not is_common_product and sale_type not in ['granel', 'weight']:
            if total_requested > current_stock:
                raise ValueError(f"Stock insuficiente. Disponible: {current_stock}, Solicitado: {total_requested}")

        price = Money(product['price'])
        item = {
            "product_id": product['id'],
            "sku": product['sku'],
            "name": product['name'],
            "qty": qty,
            "price": price,
            "total": price * qty
        }
        self.current_cart.append(item)
        return item

    def get_cart_total(self) -> float:
        totals = self.calculate_cart_totals()
        return float(totals['total'].amount)

    def checkout(self, payment_method: str, amount_paid: float) -> Dict[str, float]:
        """Process checkout: validate, create sale, reset cart."""
        if not self.current_cart:
            raise ValueError("Cart is empty")

        if not self.current_turn_id:
            turn_rows = self.db.execute_query(
                "SELECT id FROM turns WHERE status = 'open' ORDER BY id DESC LIMIT 1"
            )
            if turn_rows:
                self.current_turn_id = turn_rows[0]['id']
            else:
                raise ValueError(
                    "No hay turno abierto. Debe abrir un turno antes de crear ventas."
                )

        totals = self.calculate_cart_totals()
        total_val = float(totals['total'].amount)

        if amount_paid < total_val:
            raise ValueError("Insufficient payment")

        change = amount_paid - total_val

        timestamp = datetime.now().isoformat()
        customer_id = self.current_customer['id'] if self.current_customer else None

        ops = []

        sale_sql = """
            INSERT INTO sales (timestamp, subtotal, tax, total, payment_method, customer_id, synced)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            RETURNING id
        """
        ops.append((sale_sql, (
            timestamp,
            float(totals['subtotal'].amount),
            float(totals['tax'].amount),
            total_val,
            payment_method,
            customer_id
        )))

        item_sql = """INSERT INTO sale_items (sale_id, product_id, qty, price, subtotal, total, synced)
            VALUES ((SELECT id FROM sales WHERE timestamp = %s AND customer_id = %s ORDER BY id DESC LIMIT 1), %s, %s, %s, %s, 0)"""
        stock_sql = "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"

        for item in self.current_cart:
            item_total = float(item['total'].amount)
            ops.append((item_sql, (
                timestamp, customer_id,
                item['product_id'], item['qty'],
                float(item['price'].amount), item_total, item_total
            )))
            ops.append((stock_sql, (item['qty'], item['product_id'])))

        result = self.db.execute_transaction(ops, timeout=10)
        if not result.get('success'):
            raise RuntimeError("Transaction failed - sale not created")

        inserted_ids = result.get('inserted_ids', [])
        if not inserted_ids or inserted_ids[0] is None:
            raise RuntimeError("Failed to get sale_id from transaction")

        sale_id = inserted_ids[0]

        self.current_cart = []
        self.global_discount_pct = 0.0
        self.current_customer = None

        return {
            "sale_id": sale_id,
            "total": total_val,
            "change": change
        }

    # NOTE: create_sale_transaction (lines 837-1791) stays in pos_engine.py
    # because it's the largest method (~950 LOC) and deeply coupled to all domains.
    # It will be gradually decomposed in Phase 2 using events.


__all__ = ["POSSalesMixin"]
