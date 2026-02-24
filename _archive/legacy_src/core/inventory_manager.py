from decimal import Decimal
import math


class InventoryManager:
    def __init__(self, db_conn):
        if db_conn is None:
            raise ValueError("db_conn es requerido")
        self.db = db_conn

    def _verify_stock_available(self, product_id: int, qty: float) -> bool:
        """
        Verifica si hay stock suficiente SIN deducir.
        Usado para validar kits antes de deducir componentes.

        Args:
            product_id: ID del producto
            qty: Cantidad requerida

        Returns:
            True si hay stock suficiente, False si no

        Raises:
            ValueError: Si los parametros son invalidos
        """
        # Validacion de parametros
        if product_id is None:
            raise ValueError("product_id es requerido")
        if not isinstance(product_id, int) or product_id <= 0:
            raise ValueError(f"product_id debe ser entero positivo: {product_id}")
        if qty is None:
            raise ValueError("qty es requerido")
        try:
            qty = float(qty)
            if math.isnan(qty) or math.isinf(qty):
                raise ValueError("qty no puede ser NaN o Infinito")
            if qty < 0:
                raise ValueError(f"qty no puede ser negativo: {qty}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"qty invalido: {e}")

        # Verificar si es kit (recursivo)
        result = self.db.execute("SELECT is_kit FROM products WHERE id = %s", (product_id,)).fetchone()
        if not result:
            return False

        is_kit = result[0]

        if is_kit == 1:
            # Kit: verificar todos los componentes recursivamente
            components = self.db.execute(
                "SELECT child_product_id, qty FROM kit_items WHERE parent_product_id = %s",
                (product_id,)
            ).fetchall()
            for comp_product_id, comp_qty in components:
                required = qty * comp_qty
                if not self._verify_stock_available(comp_product_id, required):
                    return False
            return True
        else:
            # Producto normal: verificar suma de lotes
            total_stock = self.db.execute(
                "SELECT COALESCE(SUM(stock), 0) FROM product_lots WHERE product_id = %s AND stock > 0",
                (product_id,)
            ).fetchone()
            available = float(total_stock[0]) if total_stock else 0
            return available >= qty

    def deduct_stock(self, product_id: int, qty: float) -> bool:
        """
        Descuenta stock. Si es Kit, descuenta componentes.
        Si es producto normal, usa FIFO en lotes.

        Args:
            product_id: ID del producto
            qty: Cantidad a descontar

        Returns:
            True si se desconto exitosamente

        Raises:
            ValueError: Si los parametros son invalidos o no hay stock suficiente
        """
        # Validacion de parametros
        if product_id is None:
            raise ValueError("product_id es requerido")
        if not isinstance(product_id, int) or product_id <= 0:
            raise ValueError(f"product_id debe ser entero positivo: {product_id}")
        if qty is None:
            raise ValueError("qty es requerido")
        try:
            qty = float(qty)
            if math.isnan(qty) or math.isinf(qty):
                raise ValueError("qty no puede ser NaN o Infinito")
            if qty <= 0:
                raise ValueError(f"qty debe ser mayor a 0: {qty}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"qty invalido: {e}")

        # 1. Verificar si es Kit
        result = self.db.execute("SELECT is_kit, sku FROM products WHERE id = %s", (product_id,)).fetchone()

        if not result:
            raise ValueError(f"Product {product_id} not found")

        is_kit, sku = result[0], result[1]

        if is_kit == 1:
            # Es Kit: Descontar componentes recursivamente
            # Usa kit_items con columnas correctas: parent_product_id, child_product_id, qty
            components = self.db.execute(
                "SELECT child_product_id, qty FROM kit_items WHERE parent_product_id = %s",
                (product_id,)
            ).fetchall()

            # CRÍTICO: Auditoría 2026-01-30 - FIX ROLLBACK
            # FASE 1: Verificar que TODOS los componentes tienen stock suficiente
            # ANTES de deducir cualquiera. Evita deducción parcial sin rollback.
            for comp_product_id, comp_qty in components:
                required = qty * comp_qty
                if not self._verify_stock_available(comp_product_id, required):
                    return False  # Falla ANTES de deducir nada

            # FASE 2: Ahora sí deducir (sabemos que hay stock suficiente)
            for comp_product_id, comp_qty in components:
                required = qty * comp_qty
                if not self.deduct_stock(comp_product_id, required):
                    # Esto no debería pasar si _verify_stock_available funcionó
                    raise ValueError(f"Unexpected deduction failure for component {comp_product_id}")
            return True

        else:
            # Es Producto Normal: FIFO (First In, First Out)
            # Buscar lotes con stock, ordenados por fecha de caducidad
            # Usa product_lots con columna correcta: product_id (no sku)
            lots = self.db.execute(
                "SELECT id, stock FROM product_lots WHERE product_id = %s AND stock > 0 ORDER BY expiry_date ASC",
                (product_id,)
            ).fetchall()

            remaining_to_deduct = qty

            for lot_id, lot_stock in lots:
                if remaining_to_deduct <= 0:
                    break

                deduct = min(remaining_to_deduct, lot_stock)

                self.db.execute("UPDATE product_lots SET stock = stock - %s WHERE id = %s", (deduct, lot_id))
                remaining_to_deduct -= deduct

            if remaining_to_deduct > 0:
                # No hubo suficiente stock en lotes
                raise ValueError(f"Insufficient stock for product {product_id} / {sku} (Missing {remaining_to_deduct})")

            return True
