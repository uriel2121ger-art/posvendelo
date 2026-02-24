from PyQt6 import QtCore, QtGui, QtWidgets

from app.services.monedero_service import MonederoService
from app.utils.payment_helpers import build_cheque_reference, build_mixed_reference, safe_float
from app.utils.theme_manager import theme_manager


class PaymentDialog(QtWidgets.QDialog):
    def __init__(self, total_amount, core, parent=None, **kwargs):
        super().__init__(parent)
        self.original_total = total_amount  # Total original sin descuento
        self.total_amount = total_amount    # Total a pagar (puede reducirse por monedero)
        self.core = core
        self.payment_method = "cash"
        self.amount_paid = 0.0
        self.change = 0.0
        self.allow_credit = kwargs.get("allow_credit", False)
        self.credit_available = kwargs.get("credit_available", 0.0)
        self.customer_name = kwargs.get("customer_name", "Cliente")
        self.customer_id = kwargs.get("customer_id", None)
        self.wallet_balance = kwargs.get("wallet_balance", 0.0)
        self.gift_engine = kwargs.get("gift_engine", None)
        
        # Descuento por monedero (estilo OXXO)
        self.monedero_discount = 0.0
        self.monedero_source = None  # 'midas', 'anonymous', or 'anonymous_new'
        self.monedero_customer_id = None
        self.monedero_wallet_id = None
        self.monedero_accumulate = False  # Si debe acumular puntos después de la venta
        
        self.setWindowTitle("Cobrar")
        self.setFixedSize(500, 750)
        
        # FLUJO OXXO: Preguntar por monedero SOLO si no hay cliente asociado
        if not self.customer_id:
            self._ask_for_monedero()
        
        self._build_ui()
    
    def _get_cashback_percent(self) -> float:
        """Obtiene el % de cashback de las reglas MIDAS."""
        try:
            rules = list(self.core.db.execute_query("""
                SELECT multiplicador FROM loyalty_rules
                WHERE activo = 1 AND condicion_tipo = 'GLOBAL'
                ORDER BY prioridad DESC LIMIT 1
            """))
            if rules:
                return float(rules[0]['multiplicador']) * 100
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error obteniendo cashback: {e}")
        return 1.0  # Default 1%
    
    def _ask_for_monedero(self):
        """Pregunta estilo OXXO: ¿Tiene monedero? (solo para público general)"""
        from app.utils.ui_helpers import show_centered_question
        
        reply = show_centered_question(
            self,
            "💰 Monedero",
            "¿El cliente tiene monedero de puntos?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            # Preguntar si quiere registrarse
            register_reply = QtWidgets.QMessageBox.question(
                self,
                "📝 Registrarse",
                "¿Le gustaría registrarse para empezar a acumular puntos?\n\n"
                "Por cada compra acumulará puntos que podrá usar como descuento.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            
            if register_reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Pedir teléfono para crear monedero anónimo
                phone, ok = QtWidgets.QInputDialog.getText(
                    self,
                    "📱 Registrar Monedero",
                    "Ingrese el número de teléfono del cliente:",
                    QtWidgets.QLineEdit.EchoMode.Normal
                )
                
                if ok and phone.strip():
                    try:
                        from app.services.anonymous_loyalty import AnonymousLoyalty
                        loyalty = AnonymousLoyalty(self.core)
                        result = loyalty.create_wallet(phone.strip())
                        if result.get('wallet_id'):
                            self.monedero_source = 'anonymous_new'
                            self.monedero_wallet_id = result['wallet_id']
                            self.monedero_accumulate = True
                            # Calcular con % de cashback real (use round() to avoid truncation)
                            cashback = self._get_cashback_percent()
                            points_to_earn = round(self.original_total * (cashback / 100))
                            QtWidgets.QMessageBox.information(
                                self,
                                "✅ ¡Monedero Creado!",
                                f"Se registró el monedero exitosamente.\n\n"
                                f"Con esta compra ganará ~{points_to_earn} puntos ({cashback}%).\n"
                                f"¡Gracias por registrarse!"
                            )
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(self, "Error", str(e))
            return
        
        # Pedir teléfono o nombre
        search_term, ok = QtWidgets.QInputDialog.getText(
            self,
            "🔍 Buscar Monedero",
            "Ingrese teléfono o nombre del cliente:\n(puede buscar por cualquiera de los dos)",
            QtWidgets.QLineEdit.EchoMode.Normal
        )
        
        if not ok or not search_term.strip():
            return
        
        search_term = search_term.strip()
        
        # Buscar en MIDAS (clientes registrados) - por teléfono o nombre
        midas_result = self._search_midas(search_term)
        if midas_result:
            self._show_monedero_options(midas_result, 'midas', search_term)
            return
        
        # Buscar en monedero anónimo (solo por teléfono)
        anon_result = self._search_anonymous(search_term)
        if anon_result:
            self._show_monedero_options(anon_result, 'anonymous', search_term)
            return
        
        # No encontrado - ofrecer crear anónimo
        reply = QtWidgets.QMessageBox.question(
            self,
            "No Encontrado",
            f"No se encontró monedero con '{search_term}'.\n\n"
            "¿Desea crear un monedero anónimo para acumular puntos?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Si buscó por nombre, pedir teléfono para el wallet
            phone_for_wallet = search_term
            if not search_term.isdigit():
                phone_for_wallet, ok = QtWidgets.QInputDialog.getText(
                    self,
                    "📱 Teléfono Requerido",
                    "Ingrese el teléfono para crear el monedero:",
                    QtWidgets.QLineEdit.EchoMode.Normal
                )
                if not ok or not phone_for_wallet.strip():
                    return
                phone_for_wallet = phone_for_wallet.strip()
            
            try:
                from app.services.anonymous_loyalty import AnonymousLoyalty
                loyalty = AnonymousLoyalty(self.core)
                result = loyalty.create_wallet(phone_for_wallet)
                if result.get('wallet_id'):
                    self.monedero_source = 'anonymous_new'
                    self.monedero_wallet_id = result['wallet_id']
                    self.monedero_accumulate = True
                    QtWidgets.QMessageBox.information(
                        self,
                        "✅ Monedero Creado",
                        f"Se creó un nuevo monedero.\n"
                        f"Los puntos se acumularán después de la venta."
                    )
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", str(e))
    
    def _show_monedero_options(self, wallet_data, source_type, phone):
        """Muestra opciones: Acumular, Usar, o Ambos."""
        
        if source_type == 'midas':
            name = wallet_data['name']
            balance = wallet_data['balance']
            cashback_percent = self._get_cashback_percent()
            # Use round() to avoid truncation
            points_to_earn = round(self.original_total * (cashback_percent / 100))
        else:
            name = wallet_data.get('nickname', 'Cliente')
            balance = wallet_data.get('redeem_value', 0)
            # Calcular con % de cashback real (use round() to avoid truncation)
            cashback_percent = self._get_cashback_percent()
            points_to_earn = round(self.original_total * (cashback_percent / 100))
        
        # Crear diálogo personalizado
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("💰 Monedero de Puntos")
        dialog.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        # Info del cliente
        info = QtWidgets.QLabel(
            f"👤 {name}\n"
            f"💰 Saldo actual: ${balance:.2f}\n"
            f"🛒 Compra: ${self.original_total:.2f}\n"
            f"⭐ Puntos a ganar: ~{points_to_earn}"
        )
        info.setStyleSheet("font-size: 14px; padding: 10px; background: #f5f5f5; border-radius: 5px;")
        layout.addWidget(info)
        
        layout.addSpacing(10)
        
        # Opciones
        layout.addWidget(QtWidgets.QLabel("¿Qué desea hacer?"))
        
        self.rb_accumulate = QtWidgets.QRadioButton(f"⭐ Solo ACUMULAR puntos ({points_to_earn} pts)")
        self.rb_use = QtWidgets.QRadioButton(f"💸 Solo USAR puntos (hasta ${min(balance, self.original_total):.2f})")
        self.rb_both = QtWidgets.QRadioButton("🔄 Acumular Y Usar puntos")
        self.rb_none = QtWidgets.QRadioButton("❌ No hacer nada")
        
        self.rb_accumulate.setChecked(True)  # Default: acumular
        
        # Deshabilitar "usar" si no hay saldo
        if balance < 1:
            self.rb_use.setEnabled(False)
            self.rb_both.setEnabled(False)
            self.rb_use.setText("💸 Solo USAR puntos (sin saldo)")
            self.rb_both.setText("🔄 Acumular Y Usar (sin saldo)")
        
        layout.addWidget(self.rb_accumulate)
        layout.addWidget(self.rb_use)
        layout.addWidget(self.rb_both)
        layout.addWidget(self.rb_none)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        btn_ok = QtWidgets.QPushButton("✅ Continuar")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        
        # Procesar selección
        if self.rb_none.isChecked():
            return
        
        # Guardar datos para después
        self.monedero_source = source_type
        if source_type == 'midas':
            self.monedero_customer_id = wallet_data['customer_id']
        else:
            self.monedero_wallet_id = wallet_data['wallet_id']
        
        # Marcar opciones
        self.monedero_accumulate = self.rb_accumulate.isChecked() or self.rb_both.isChecked()
        want_use = self.rb_use.isChecked() or self.rb_both.isChecked()
        
        # Si quiere usar puntos
        if want_use and balance >= 1:
            max_discount = min(balance, self.original_total)
            amount, ok = QtWidgets.QInputDialog.getDouble(
                self,
                "💸 Usar Puntos",
                f"Saldo disponible: ${balance:.2f}\n"
                f"Total a pagar: ${self.total_amount:.2f}\n\n"
                f"¿Cuánto desea usar?",
                max_discount, 0, max_discount, 2
            )
            
            if ok and amount > 0:
                self.monedero_discount = amount
                self.total_amount = self.original_total - amount
                
                msg = f"Se usarán ${amount:.2f} de puntos.\n"
                if self.monedero_accumulate:
                    msg += f"Además, se acumularán puntos por la compra."
                msg += f"\n\nNuevo total: ${self.total_amount:.2f}"
                
                QtWidgets.QMessageBox.information(self, "✅ Configurado", msg)
        elif self.monedero_accumulate:
            QtWidgets.QMessageBox.information(
                self,
                "✅ Acumular Puntos",
                f"Se acumularán ~{points_to_earn} puntos después de la venta."
            )
    
    def _search_midas(self, search_term: str):
        """Busca cliente en MIDAS por teléfono o nombre."""
        try:
            # Buscar por teléfono primero, luego por nombre
            result = list(self.core.db.execute_query(
                """SELECT id, name, phone FROM customers 
                   WHERE (phone = %s OR name LIKE %s) AND is_active = 1 
                   LIMIT 5""",
                (search_term, f"%{search_term}%")
            ))
            
            if not result:
                return None
            
            # Si hay múltiples resultados, mostrar selector
            if len(result) > 1:
                items = [f"{r['name']} - {r['phone']}" for r in result]
                item, ok = QtWidgets.QInputDialog.getItem(
                    self,
                    "Múltiples Resultados",
                    "Se encontraron varios clientes.\nSeleccione uno:",
                    items, 0, False
                )
                if not ok:
                    return None
                selected_idx = items.index(item)
                selected = result[selected_idx] if selected_idx < len(result) else None
            else:
                selected = result[0] if result else None
            
            if not selected:
                return None
            
            customer_id = selected['id']
            customer_name = selected['name']
            
            # Buscar cuenta de lealtad
            loyalty = list(self.core.db.execute_query(
                "SELECT saldo_actual, nivel_lealtad FROM loyalty_accounts WHERE customer_id = %s",
                (customer_id,)
            ))
            
            # Si no tiene cuenta de lealtad, crear una
            if not loyalty:
                self.core.loyalty_engine.get_or_create_account(customer_id)
                loyalty = list(self.core.db.execute_query(
                    "SELECT saldo_actual, nivel_lealtad FROM loyalty_accounts WHERE customer_id = %s",
                    (customer_id,)
                ))
            
            balance = float(loyalty[0]['saldo_actual'] or 0) if loyalty else 0
            tier = loyalty[0]['nivel_lealtad'] if loyalty else 'BRONCE'
            
            return {
                'customer_id': customer_id,
                'name': customer_name,
                'balance': balance,
                'tier': tier or 'BRONCE'
            }
        except Exception as e:
            print(f"Error searching MIDAS: {e}")
            return None
    
    def _search_anonymous(self, phone: str):
        """Busca en monedero anónimo."""
        try:
            from app.services.anonymous_loyalty import AnonymousLoyalty
            loyalty = AnonymousLoyalty(self.core)
            
            # Find wallet first
            wallet = loyalty.find_wallet(phone)
            if not wallet:
                return None
            
            # Get full status
            status = loyalty.get_wallet_status(phone)
            
            return {
                'wallet_id': wallet['wallet_id'],
                'nickname': status.get('nickname', 'Cliente'),
                'balance': wallet.get('points_balance', 0),
                'redeem_value': status.get('redeem_value', 0)
            }
        except Exception as e:
            print(f"Error searching anonymous wallet: {e}")
            return None
    
    def _apply_midas_discount(self, midas_result, phone):
        """Aplica descuento desde MIDAS."""
        balance = midas_result['balance']
        max_discount = min(balance, self.total_amount)
        
        # Preguntar cuánto usar
        amount, ok = QtWidgets.QInputDialog.getDouble(
            self,
            f"🌟 MIDAS: {midas_result['name']}",
            f"Saldo disponible: ${balance:.2f}\n"
            f"Total a pagar: ${self.total_amount:.2f}\n\n"
            f"¿Cuánto desea usar?",
            max_discount, 0, max_discount, 2
        )
        
        if not ok or amount <= 0:
            return
        
        self.monedero_discount = amount
        self.monedero_source = 'midas'
        self.monedero_customer_id = midas_result['customer_id']
        self.total_amount = self.original_total - amount
        
        QtWidgets.QMessageBox.information(
            self,
            "✅ Descuento Aplicado",
            f"Se aplicaron ${amount:.2f} de puntos MIDAS\n"
            f"Nuevo total a pagar: ${self.total_amount:.2f}"
        )
    
    def _apply_anonymous_discount(self, anon_result, phone):
        """Aplica descuento desde monedero anónimo."""
        balance = anon_result['balance']
        redeem_value = anon_result['redeem_value']
        max_discount = min(redeem_value, self.total_amount)
        
        # Preguntar cuánto usar
        amount, ok = QtWidgets.QInputDialog.getDouble(
            self,
            f"🎁 Monedero: {anon_result['nickname']}",
            f"Puntos: {balance} = ${redeem_value:.2f}\n"
            f"Total a pagar: ${self.total_amount:.2f}\n\n"
            f"¿Cuánto desea usar?",
            max_discount, 0, max_discount, 2
        )
        
        if not ok or amount <= 0:
            return
        
        self.monedero_discount = amount
        self.monedero_source = 'anonymous'
        self.monedero_wallet_id = anon_result['wallet_id']
        self.total_amount = self.original_total - amount
        
        QtWidgets.QMessageBox.information(
            self,
            "✅ Descuento Aplicado",
            f"Se aplicaron ${amount:.2f} del monedero\n"
            f"Nuevo total a pagar: ${self.total_amount:.2f}"
        )
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout()
        
        # Total
        lbl_total = QtWidgets.QLabel(f"Total: ${self.total_amount:.2f}")
        lbl_total.setStyleSheet("font-size: 28px; font-weight: bold; color: green;")
        lbl_total.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_total)

        # --- Single Payment Input ---
        self.single_payment_widget = QtWidgets.QWidget()
        sp_layout = QtWidgets.QVBoxLayout(self.single_payment_widget)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        
        self.input_paid = QtWidgets.QLineEdit()
        self.input_paid.setPlaceholderText("Monto Recibido")
        self.input_paid.setStyleSheet("font-size: 24px; padding: 10px;")
        self.input_paid.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.input_paid.textChanged.connect(self._calc_change)
        sp_layout.addWidget(self.input_paid)
        
        self.lbl_ref = QtWidgets.QLabel("Referencia / Autorización:")
        self.input_ref = QtWidgets.QLineEdit()
        self.input_ref.setPlaceholderText("Ingrese número de referencia...")
        sp_layout.addWidget(self.lbl_ref)
        sp_layout.addWidget(self.input_ref)
        
        # Advanced Cheque fields (hidden by default)
        self.cheque_fields_widget = QtWidgets.QWidget()
        cheque_layout = QtWidgets.QFormLayout(self.cheque_fields_widget)
        cheque_layout.setContentsMargins(0, 10, 0, 0)
        
        self.cheque_bank = QtWidgets.QLineEdit()
        self.cheque_bank.setPlaceholderText("Ej: Banamex, BBVA, Santander")
        
        self.cheque_number = QtWidgets.QLineEdit()
        self.cheque_number.setPlaceholderText("Número del cheque")
        
        self.cheque_date = QtWidgets.QDateEdit()
        self.cheque_date.setCalendarPopup(True)
        self.cheque_date.setDate(QtCore.QDate.currentDate())
        
        self.cheque_account = QtWidgets.QLineEdit()
        self.cheque_account.setPlaceholderText("Últimos 4 dígitos")
        self.cheque_account.setMaxLength(4)
        
        cheque_layout.addRow("🏦 Banco:", self.cheque_bank)
        cheque_layout.addRow("🔢 Número Cheque:", self.cheque_number)
        cheque_layout.addRow("📅 Fecha:", self.cheque_date)
        cheque_layout.addRow("💳 Cuenta (4 díg):", self.cheque_account)
        
        sp_layout.addWidget(self.cheque_fields_widget)
        self.cheque_fields_widget.setVisible(False)
        
        layout.addWidget(self.single_payment_widget)

        # --- Mixed Payment Input ---
        self.mixed_payment_widget = QtWidgets.QWidget()
        mp_layout = QtWidgets.QGridLayout(self.mixed_payment_widget)
        mp_layout.setContentsMargins(0, 0, 0, 0)
        
        # Cash Row
        mp_layout.addWidget(QtWidgets.QLabel("Efectivo:"), 0, 0)
        self.mix_cash_amt = QtWidgets.QLineEdit()
        self.mix_cash_amt.setPlaceholderText("$0.00")
        self.mix_cash_amt.textChanged.connect(self._calc_mixed_total)
        mp_layout.addWidget(self.mix_cash_amt, 0, 1)
        
        # Card Row
        mp_layout.addWidget(QtWidgets.QLabel("Tarjeta:"), 1, 0)
        self.mix_card_amt = QtWidgets.QLineEdit()
        self.mix_card_amt.setPlaceholderText("$0.00")
        self.mix_card_amt.textChanged.connect(self._calc_mixed_total)
        mp_layout.addWidget(self.mix_card_amt, 1, 1)
        
        self.mix_card_ref = QtWidgets.QLineEdit()
        self.mix_card_ref.setPlaceholderText("Ref/Auth")
        mp_layout.addWidget(self.mix_card_ref, 1, 2)

        # Transfer Row
        mp_layout.addWidget(QtWidgets.QLabel("Transf.:"), 2, 0)
        self.mix_trans_amt = QtWidgets.QLineEdit()
        self.mix_trans_amt.setPlaceholderText("$0.00")
        self.mix_trans_amt.textChanged.connect(self._calc_mixed_total)
        mp_layout.addWidget(self.mix_trans_amt, 2, 1)
        
        self.mix_trans_ref = QtWidgets.QLineEdit()
        self.mix_trans_ref.setPlaceholderText("Ref/Auth")
        mp_layout.addWidget(self.mix_trans_ref, 2, 2)
        
        # Wallet/Points Row (only if customer has balance)
        if self.wallet_balance > 0:
            mp_layout.addWidget(QtWidgets.QLabel("Puntos:"), 3, 0)
            self.mix_wallet_amt = QtWidgets.QLineEdit()
            self.mix_wallet_amt.setPlaceholderText(f"$0.00 (Disp: ${self.wallet_balance:.2f})")
            self.mix_wallet_amt.textChanged.connect(self._calc_mixed_total)
            mp_layout.addWidget(self.mix_wallet_amt, 3, 1)
            
            wallet_info = QtWidgets.QLabel(f"💰 ${self.wallet_balance:.2f}")
            wallet_info.setStyleSheet("color: #4caf50; font-weight: bold;")
            mp_layout.addWidget(wallet_info, 3, 2)
        else:
            self.mix_wallet_amt = None
        
        # Gift Card Row (only if gift engine is available)
        next_row = 4 if self.wallet_balance > 0 else 3
        if self.gift_engine:
            mp_layout.addWidget(QtWidgets.QLabel("🎁 Gift Card:"), next_row, 0)
            self.mix_gift_amt = QtWidgets.QLineEdit()
            self.mix_gift_amt.setPlaceholderText("$0.00")
            self.mix_gift_amt.textChanged.connect(self._calc_mixed_total)
            mp_layout.addWidget(self.mix_gift_amt, next_row, 1)
            
            self.mix_gift_code = QtWidgets.QLineEdit()
            self.mix_gift_code.setPlaceholderText("Código")
            mp_layout.addWidget(self.mix_gift_code, next_row, 2)
        else:
            self.mix_gift_amt = None
            self.mix_gift_code = None
        
        # Other Row (Vales, Cheques, etc - Optional, kept simple for now)
        
        layout.addWidget(self.mixed_payment_widget)
        self.mixed_payment_widget.setVisible(False)

        self.lbl_change = QtWidgets.QLabel("Cambio: $0.00")
        self.lbl_change.setStyleSheet("font-size: 22px; font-weight: bold; color: blue;")
        self.lbl_change.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.lbl_change)
        
        # NOTE: "Requiere Factura" is now asked via modal popup in _finalize_payment()
        # instead of checkbox here - this blocks until the cashier answers
        
        layout.addSpacing(10)
        
        # Métodos de Pago Buttons
        lbl_methods = QtWidgets.QLabel("Método de Pago:")
        lbl_methods.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_methods)
        
        methods_layout = QtWidgets.QGridLayout()
        
        self.btn_cash = QtWidgets.QPushButton("💵 Efectivo")
        self.btn_card = QtWidgets.QPushButton("💳 Tarjeta")
        self.btn_transfer = QtWidgets.QPushButton("🏦 Transferencia")
        self.btn_usd = QtWidgets.QPushButton("💵 Dólares USD")
        self.btn_vales = QtWidgets.QPushButton("🎫 Vales")
        self.btn_cheque = QtWidgets.QPushButton("📄 Cheque")
        self.btn_mixed = QtWidgets.QPushButton("🔀 Mixto")
        self.btn_credit = QtWidgets.QPushButton("📝 Crédito")
        self.btn_points = QtWidgets.QPushButton(f"🌟 Puntos (${self.wallet_balance:.2f})")
        self.btn_gift_card = QtWidgets.QPushButton("🎁 Tarjeta Regalo")
        
        buttons = [self.btn_cash, self.btn_card, self.btn_transfer, self.btn_usd, 
                   self.btn_vales, self.btn_cheque, self.btn_mixed]
        
        # Solo agregar botón de crédito si está permitido
        if self.allow_credit:
            buttons.append(self.btn_credit)
            
        # Agregar botón de puntos si hay saldo
        if self.wallet_balance > 0:
            buttons.append(self.btn_points)
        
        # Agregar botón de Gift Card si el engine está disponible
        if self.gift_engine:
            buttons.append(self.btn_gift_card)
            
        # Theme-aware button styling
        is_dark = theme_manager.current_theme in ["Dark", "AMOLED"]
        checked_bg = "#3498db" if not is_dark else "#2980b9"
        
        for btn in buttons:
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ padding: 10px; font-size: 14px; }}
                QPushButton:checked {{ background-color: {checked_bg}; color: white; }}
            """)
            
        self.btn_cash.clicked.connect(lambda: self._set_method("cash"))
        self.btn_card.clicked.connect(lambda: self._set_method("card"))
        self.btn_transfer.clicked.connect(lambda: self._set_method("transfer"))
        self.btn_usd.clicked.connect(lambda: self._set_method("usd"))
        self.btn_vales.clicked.connect(lambda: self._set_method("vales"))
        self.btn_cheque.clicked.connect(lambda: self._set_method("cheque"))
        self.btn_mixed.clicked.connect(lambda: self._set_method("mixed"))
        if self.allow_credit:
            self.btn_credit.clicked.connect(lambda: self._set_method("credit"))
        if self.wallet_balance > 0:
            self.btn_points.clicked.connect(lambda: self._set_method("wallet"))
        if self.gift_engine:
            self.btn_gift_card.clicked.connect(lambda: self._set_method("gift_card"))
        
        # Layout: 3 columns, multiple rows
        methods_layout.addWidget(self.btn_cash, 0, 0)
        methods_layout.addWidget(self.btn_card, 0, 1)
        methods_layout.addWidget(self.btn_transfer, 0, 2)
        methods_layout.addWidget(self.btn_usd, 1, 0)
        methods_layout.addWidget(self.btn_vales, 1, 1)
        methods_layout.addWidget(self.btn_cheque, 1, 2)
        methods_layout.addWidget(self.btn_mixed, 2, 0)  # ALWAYS in row 2, col 0
        
        # Credit button in row 2, col 1 (if available)
        if self.allow_credit:
            methods_layout.addWidget(self.btn_credit, 2, 1)
            
        # Points button in row 2, col 2 (if available)
        if self.wallet_balance > 0:
            methods_layout.addWidget(self.btn_points, 2, 2)
            
        # Gift card button in row 3, col 0 (ALWAYS row 3 to avoid overlap)
        if self.gift_engine:
            methods_layout.addWidget(self.btn_gift_card, 3, 0)
        
        layout.addLayout(methods_layout)
        
        layout.addStretch()

        # Botones de Acción
        action_layout = QtWidgets.QHBoxLayout()
        
        # Theme-aware action buttons
        colors = theme_manager.get_colors()
        btn_success = colors.get("btn_success", "#27ae60")
        btn_warning = colors.get("btn_warning", "#f39c12")
        
        self.btn_pay_print = QtWidgets.QPushButton("Cobrar e Imprimir (F1)")
        self.btn_pay_print.setStyleSheet(f"background-color: {btn_success}; color: white; padding: 15px; font-weight: bold;")
        self.btn_pay_print.clicked.connect(lambda: self._finalize_payment(True))
        
        self.btn_pay_no_print = QtWidgets.QPushButton("Solo Cobrar (F2)")
        self.btn_pay_no_print.setStyleSheet(f"background-color: {btn_warning}; color: white; padding: 15px; font-weight: bold;")
        self.btn_pay_no_print.clicked.connect(lambda: self._finalize_payment(False))
        
        action_layout.addWidget(self.btn_pay_print)
        action_layout.addWidget(self.btn_pay_no_print)
        
        layout.addLayout(action_layout)

        self.setLayout(layout)
        self.result_data = None
        
        # Default
        self.btn_cash.click()
        self.input_paid.setFocus()

    def _calc_mixed_total(self):
        # Use safe_float helper to eliminate repetitive try/except
        c = safe_float(self.mix_cash_amt.text())
        cd = safe_float(self.mix_card_amt.text())
        t = safe_float(self.mix_trans_amt.text())
        w = safe_float(self.mix_wallet_amt.text()) if self.mix_wallet_amt else 0.0
        g = safe_float(self.mix_gift_amt.text()) if self.mix_gift_amt else 0.0
        
        # Validate wallet amount
        if w > self.wallet_balance:
            QtWidgets.QMessageBox.warning(self, "Puntos Insuficientes",
                f"El cliente solo tiene ${self.wallet_balance:.2f} en puntos.")
            if self.mix_wallet_amt:
                self.mix_wallet_amt.blockSignals(True)
                self.mix_wallet_amt.setText(f"{self.wallet_balance:.2f}")
                self.mix_wallet_amt.blockSignals(False)
            w = self.wallet_balance
        
        total_mixed = c + cd + t + w + g
        self.amount_paid = total_mixed
        self.change = total_mixed - self.total_amount
        self._update_change_ui()

    def _calc_change(self):
        if self.payment_method == "mixed":
            return # Handled by _calc_mixed_total
            
        try:
            text = self.input_paid.text()
            if not text:
                self.amount_paid = 0.0
                self.change = -self.total_amount
            else:
                self.amount_paid = float(text)
                self.change = self.amount_paid - self.total_amount
            self._update_change_ui()
        except ValueError:
            self.lbl_change.setText("Cambio: $0.00")
            self.btn_pay_print.setEnabled(False)
            self.btn_pay_no_print.setEnabled(False)

    def _update_change_ui(self):
        self.lbl_change.setText(f"Cambio: ${self.change:.2f}")
        self.lbl_change.setStyleSheet("color: red; font-size: 22px; font-weight: bold;" if self.change < -0.01 else "color: blue; font-size: 22px; font-weight: bold;")
        
        can_pay = self.change >= -0.01
        self.btn_pay_print.setEnabled(can_pay)
        self.btn_pay_no_print.setEnabled(can_pay)

    def _set_method(self, method):
        self.payment_method = method
        
        # Update buttons state
        self.btn_cash.setChecked(method == "cash")
        self.btn_card.setChecked(method == "card")
        self.btn_transfer.setChecked(method == "transfer")
        self.btn_usd.setChecked(method == "usd")
        self.btn_vales.setChecked(method == "vales")
        self.btn_cheque.setChecked(method == "cheque")
        self.btn_mixed.setChecked(method == "mixed")
        if self.allow_credit:
            self.btn_credit.setChecked(method == "credit")
        if self.wallet_balance > 0:
            self.btn_points.setChecked(method == "wallet")
        if self.gift_engine:
            self.btn_gift_card.setChecked(method == "gift_card")
        
        if method == "mixed":
            self.single_payment_widget.setVisible(False)
            self.mixed_payment_widget.setVisible(True)
            self._calc_mixed_total()
            self.mix_cash_amt.setFocus()
        elif method == "gift_card":
            # Handle Gift Card Payment
            from app.dialogs.gift_card_dialogs import GiftCardRedemptionDialog
            
            redemption_dialog = GiftCardRedemptionDialog(
                total_amount=self.total_amount,
                gift_engine=self.gift_engine,
                parent=self
            )
            
            if redemption_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                # Gift card was successfully applied
                amount_applied = redemption_dialog.result_amount
                card_code = redemption_dialog.card_code
                
                # Store gift card data for later redemption
                if not hasattr(self, 'gift_card_data'):
                    self.gift_card_data = {}
                
                self.gift_card_data = {
                    'code': card_code,
                    'amount': amount_applied
                }
                
                # Update UI to show gift card payment
                self.input_paid.setText(f"{amount_applied:.2f}")
                self.lbl_ref.setVisible(True)
                self.lbl_ref.setText(f"Tarjeta: {card_code[:12]}...")
                self.input_ref.setVisible(False)
                
                # If gift card covers full amount
                if amount_applied >= self.total_amount:
                    self.amount_paid = amount_applied
                    self.change = amount_applied - self.total_amount
                    self._update_change_ui()
                    QtWidgets.QMessageBox.information(
                        self,
                        "Pago Completo",
                        f"La tarjeta de regalo cubre el total.\nCambio: ${self.change:.2f}"
                    )
                else:
                    # Partial payment - switch to mixed mode
                    remaining = self.total_amount - amount_applied
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "Pago Parcial",
                        f"La tarjeta cubre: ${amount_applied:.2f}\n"
                        f"Restante: ${remaining:.2f}\n\n"
                        f"¿Desea pagar el resto con otro método?",
                        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                    )
                    
                    if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                        # Switch to mixed payment mode
                        self._set_method("mixed")
                        # Pre-fill the remaining amount that needs to be covered
                        QtWidgets.QMessageBox.information(
                            self,
                            "Pago Mixto",
                            f"Complete el pago de ${remaining:.2f} restante usando efectivo o tarjeta."
                        )
                    else:
                        # Cancel payment
                        self.payment_method = "cash"
                        self.btn_cash.setChecked(True)
                        return
            else:
                # User cancelled gift card redemption - return to cash
                self.payment_method = "cash"
                self.btn_cash.setChecked(True)
                return
        else:

            self.single_payment_widget.setVisible(True)
            self.mixed_payment_widget.setVisible(False)
            
            # Show/Hide reference in single mode
            needs_ref = method in ["card", "transfer", "cheque"]
            self.lbl_ref.setVisible(needs_ref)
            self.input_ref.setVisible(needs_ref and method != "cheque")
            
            # Show cheque fields if cheque is selected
            if hasattr(self, 'cheque_fields_widget'):
                self.cheque_fields_widget.setVisible(method == "cheque")
                if method == "cheque":
                    self.cheque_bank.setFocus()
            
            # Auto-fill amount for non-cash methods
            # Auto-fill amount for non-cash methods
            if method != "cash":
                self.input_paid.setText(f"{self.total_amount:.2f}")
                if method == "credit":
                    self.lbl_ref.setVisible(True)
                    self.lbl_ref.setText(f"Crédito Disponible: ${self.credit_available:,.2f}")
                    self.input_ref.setVisible(False) # No reference needed for credit usually
                    
                    if self.total_amount > self.credit_available:
                        QtWidgets.QMessageBox.warning(self, "Crédito Insuficiente", 
                            f"El cliente solo tiene ${self.credit_available:,.2f} disponibles.")
                        self.btn_pay_print.setEnabled(False)
                        self.btn_pay_no_print.setEnabled(False)
                        return
                elif method == "wallet":
                    self.lbl_ref.setVisible(True)
                    self.lbl_ref.setText(f"Saldo en Monedero: ${self.wallet_balance:,.2f}")
                    self.input_ref.setVisible(False)
                    
                    if self.total_amount > self.wallet_balance:
                        QtWidgets.QMessageBox.warning(self, "Saldo Insuficiente", 
                            f"El cliente solo tiene ${self.wallet_balance:,.2f} en puntos.")
                        self.btn_pay_print.setEnabled(False)
                        self.btn_pay_no_print.setEnabled(False)
                        return
                else:
                    self.lbl_ref.setText("Referencia / Autorización:")
                    self.input_ref.setFocus()
            else:
                self.input_paid.clear()
                self.input_paid.setFocus()
            self._calc_change()

    def keyPressEvent(self, event):
        # F1: Cobrar e Imprimir
        if event.key() == QtCore.Qt.Key.Key_F1:
            if self.btn_pay_print.isEnabled():
                self._finalize_payment(print_ticket=True)
            return
            
        # F2: Cobrar SIN Imprimir
        if event.key() == QtCore.Qt.Key.Key_F2:
            if self.btn_pay_no_print.isEnabled():
                self._finalize_payment(print_ticket=False)
            return
            
        # Enter: Cobrar (Default behavior)
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if self.btn_pay_print.isEnabled():
                self._finalize_payment(print_ticket=True)
            return
            
        super().keyPressEvent(event)

    def _finalize_payment(self, print_ticket=True):
        # CRITICAL VALIDATION 1: Block negative amounts in single payment mode
        if self.payment_method != "mixed":
            if self.amount_paid < 0:
                QtWidgets.QMessageBox.critical(
                    self,
                    "❌ Monto Inválido",
                    f"No se permite ingresar un monto negativo: ${self.amount_paid:.2f}\n\n"
                    "El monto debe ser mayor o igual a cero."
                )
                return
        
        # CRITICAL VALIDATION 2: Ensure payment covers total
        if self.amount_paid < self.total_amount - 0.01:
             QtWidgets.QMessageBox.warning(self, "Pago incompleto", "El monto cubierto es menor al total.")
             return

        mixed_data = {}
        reference = ""
        
        if self.payment_method == "mixed":
            # Use safe_float helper
            c = safe_float(self.mix_cash_amt.text())
            cd = safe_float(self.mix_card_amt.text())
            t = safe_float(self.mix_trans_amt.text())
            w = safe_float(self.mix_wallet_amt.text()) if self.mix_wallet_amt else 0.0
            g = safe_float(self.mix_gift_amt.text()) if self.mix_gift_amt else 0.0
            
            # CRITICAL: Validate no negative amounts
            if any(amount < 0 for amount in [c, cd, t, w, g]):
                QtWidgets.QMessageBox.critical(
                    self,
                    "❌ Montos Inválidos",
                    "No se permite ingresar cantidades negativas en ningún método de pago.\n\n"
                    "Todos los valores deben ser ≥ 0"
                )
                return
            
            mixed_data = {
                "cash": c,
                "card": cd,
                "transfer": t,
                "wallet": w,
                "gift_card": g,
                "card_ref": self.mix_card_ref.text(),
                "transfer_ref": self.mix_trans_ref.text(),
                "gift_card_code": self.mix_gift_code.text().strip() if self.mix_gift_code else ""
            }
            
            # Validate gift card if amount > 0
            if g > 0:
                gc_code = mixed_data.get('gift_card_code', '')
                if not gc_code:
                    QtWidgets.QMessageBox.warning(self, "Código Requerido", 
                        "Ingresa el código de la Gift Card.")
                    return
                
                # Validate gift card has sufficient balance
                if self.gift_engine:
                    validation = self.gift_engine.validate_card(gc_code)
                    if not validation.get('valid'):
                        QtWidgets.QMessageBox.warning(self, "Gift Card Inválida", 
                            validation.get('message', 'Tarjeta no válida'))
                        return
                    if float(validation.get('balance', 0)) < g:
                        QtWidgets.QMessageBox.warning(self, "Saldo Insuficiente", 
                            f"La Gift Card solo tiene ${float(validation['balance']):.2f} de saldo.\n"
                            f"Reduce el monto o usa otra tarjeta.")
                        return
            
            # Construct a composite reference string for simple storage if needed
            refs = []
            if cd > 0: refs.append(f"Tarj: {mixed_data['card_ref']}")
            if t > 0: refs.append(f"Transf: {mixed_data['transfer_ref']}")
            if w > 0: refs.append(f"Puntos: ${w:.2f}")
            if g > 0: refs.append(f"Gift: {mixed_data['gift_card_code']}")
            reference = "; ".join(refs)
        else:
            reference = self.input_ref.text().strip() if self.input_ref.isVisible() else ""
            
            # For cheque, build comprehensive reference using helper
            if self.payment_method == "cheque" and hasattr(self, 'cheque_bank'):
                reference = build_cheque_reference(
                    bank=self.cheque_bank.text(),
                    number=self.cheque_number.text(),
                    date=self.cheque_date.date().toString('dd/MM/yyyy'),
                    account_last4=self.cheque_account.text()
                )
        
        # --- GIFT CARD: NO REDIMIR AQUÍ ---
        # CRÍTICO: Auditoría 2026-01-30 - FIX RACE CONDITION / ROLLBACK
        # NO redimir la gift card aquí. Si la venta falla después, el balance
        # ya habría sido deducido sin venta asociada = dinero perdido.
        # En su lugar, pasar los datos para que sales_tab.py redima DESPUÉS
        # de confirmar que create_sale() fue exitoso.
        #
        # FIX 2026-02-04: Validar balance actual antes de confirmar pago y
        # guardar balance_before para posible rollback en sales_tab.py
        gift_card_info = {}
        if self.payment_method == "gift_card" and hasattr(self, 'gift_card_data'):
            gc_code = self.gift_card_data.get('code', '')
            gc_amount = self.gift_card_data.get('amount', 0)

            # Validar que tenemos gift_engine y balance suficiente
            balance_before = None
            if self.gift_engine and gc_code:
                try:
                    card_info = self.gift_engine.get_card_info(gc_code)
                    if card_info:
                        from decimal import Decimal, InvalidOperation
                        try:
                            balance_before = Decimal(str(card_info.get('balance', 0)))
                            if not balance_before.is_finite():
                                raise ValueError("Invalid balance value")
                            amount_decimal = Decimal(str(gc_amount))
                            if not amount_decimal.is_finite():
                                raise ValueError("Invalid amount value")

                            if balance_before < amount_decimal:
                                QtWidgets.QMessageBox.warning(
                                    self,
                                    "Balance Insuficiente",
                                    f"La tarjeta de regalo no tiene saldo suficiente.\n"
                                    f"Balance actual: ${float(balance_before):.2f}\n"
                                    f"Monto a redimir: ${gc_amount:.2f}"
                                )
                                return
                        except (InvalidOperation, ValueError) as e:
                            QtWidgets.QMessageBox.warning(
                                self,
                                "Error de Validación",
                                f"Error al validar montos de tarjeta de regalo: {e}"
                            )
                            return
                except Exception as e:
                    # Log but allow to continue - validation will happen in sales_tab
                    import logging
                    logging.getLogger("PAYMENT_DIALOG").warning(
                        f"Could not validate gift card balance: {e}"
                    )

            # Solo pasar datos para redemption posterior, NO redimir aquí
            gift_card_info = {
                'code': gc_code,
                'amount_to_redeem': gc_amount,
                'pending_redemption': True,  # Flag para indicar que falta redimir
                'balance_before': float(balance_before) if balance_before is not None else None,
                # Información para rollback en caso de fallo después de redención
                'rollback_info': {
                    'can_rollback': True,
                    'original_balance': float(balance_before) if balance_before is not None else None
                }
            }
            reference = f"Gift Card: {gc_code}"
        
        # === POPUP MODAL: ¿REQUIERE FACTURA? ===
        # Block until cashier answers - this determines Serie A or B
        respuesta = QtWidgets.QMessageBox.question(
            self,
            "📄 Factura",
            "¿El cliente requiere factura?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No  # Default: No
        )
        requiere_factura = (respuesta == QtWidgets.QMessageBox.StandardButton.Yes)
        
        self.result_data = {
            "method": self.payment_method,
            "amount": self.amount_paid,
            "change": self.change,
            "print_ticket": print_ticket,
            "reference": reference,
            "mixed_breakdown": mixed_data,
            "gift_card_info": gift_card_info,
            "requiere_factura": requiere_factura,
            # Información del monedero (estilo OXXO)
            "monedero": {
                "discount": self.monedero_discount,
                "source": self.monedero_source,
                "customer_id": self.monedero_customer_id,
                "wallet_id": self.monedero_wallet_id,
                "accumulate": self.monedero_accumulate
            } if self.monedero_source else None
        }
        self.accept()

    def closeEvent(self, event):
        """Cleanup on close."""
        self.result_data = None
        super().closeEvent(event)
