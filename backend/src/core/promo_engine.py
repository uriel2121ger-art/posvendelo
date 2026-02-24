from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


class PromoEngine:
    def __init__(self, db_conn):
        if db_conn is None:
            raise ValueError("db_conn es requerido")
        self.db = db_conn

    def apply_promotions(self, cart: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Recibe un carrito y aplica reglas de negocio.
        Retorna el carrito con descuentos aplicados.

        Args:
            cart: Lista de items con 'sku', 'price', 'qty'

        Returns:
            Carrito con descuentos aplicados

        Raises:
            ValueError: Si el carrito es invalido
        """
        # Validacion de parametros
        if cart is None:
            raise ValueError("cart es requerido")
        if not isinstance(cart, list):
            raise ValueError(f"cart debe ser una lista, recibido: {type(cart).__name__}")

        current_hour = datetime.now().hour

        # Cargar reglas activas (PostgreSQL: usar %s para parametros)
        rules = self.db.execute("SELECT * FROM promotions WHERE active = %s", (1,)).fetchall()

        for item in cart:
            # Validar estructura del item
            if not isinstance(item, dict):
                raise ValueError(f"Cada item debe ser un diccionario, recibido: {type(item).__name__}")
            if 'price' not in item:
                raise ValueError("Cada item debe tener 'price'")
            if 'qty' not in item:
                item['qty'] = 1

            # Convertir a Decimal para calculos monetarios precisos
            price = Decimal(str(item.get('price', 0)))
            qty = Decimal(str(item.get('qty', 1)))

            item['discount'] = Decimal('0.00')
            item['promo_applied'] = None

            for rule in rules:
                r_id, name, r_type, target, trig_qty, val, s_h, e_h, _ = rule

                # Regla: Happy Hour
                if r_type == 'HAPPY_HOUR':
                    if s_h <= current_hour < e_h:
                        # Aplica descuento global o por producto
                        if target is None or target == item.get('sku'):
                            val_decimal = Decimal(str(val))
                            discount = (price * (val_decimal / Decimal('100'))).quantize(
                                Decimal('0.01'), rounding=ROUND_HALF_UP
                            )
                            item['discount'] = discount
                            item['promo_applied'] = name

                # Regla: 2x1 (Simple)
                elif r_type == '2x1':
                    if target == item.get('sku') and qty >= 2:
                        # Cada 2, 1 es gratis
                        free_items = int(qty // 2)
                        discount = (Decimal(str(free_items)) * price).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                        item['discount'] = discount
                        item['promo_applied'] = name

        return cart
