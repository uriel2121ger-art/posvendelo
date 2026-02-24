from PyQt6 import QtCore, QtWidgets

from app.core import STATE
from app.utils.theme_manager import theme_manager


class WalletDialog(QtWidgets.QDialog):
    def __init__(self, parent, core, customer_id):
        super().__init__(parent)
        self.core = core
        self.customer_id = customer_id
        self.loyalty_engine = core.loyalty_engine  # Access MIDAS loyalty engine
        self.setWindowTitle("Monedero Electrónico")
        self.resize(700, 600)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # Get theme colors
        is_dark = theme_manager.current_theme in ["Dark", "AMOLED"]
        colors = theme_manager.get_colors()
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header with customer name
        self.lbl_customer = QtWidgets.QLabel("Cliente")
        self.lbl_customer.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.lbl_customer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_customer)
        
        # Balance Section
        balance_frame = QtWidgets.QFrame()
        balance_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {colors.get('bg_card', '#ffffff')};
                border: 2px solid {colors.get('accent', '#3498db')};
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        balance_layout = QtWidgets.QVBoxLayout(balance_frame)
        
        self.lbl_points = QtWidgets.QLabel("Puntos: 0")
        self.lbl_points.setStyleSheet("font-size: 32px; font-weight: bold; color: #27ae60;")
        self.lbl_points.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(self.lbl_points)
        
        self.lbl_value = QtWidgets.QLabel("Valor: $0.00")
        self.lbl_value.setStyleSheet("font-size: 18px; color: #7f8c8d;")
        self.lbl_value.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(self.lbl_value)
        
        # Tier info
        self.lbl_tier = QtWidgets.QLabel("")
        self.lbl_tier.setStyleSheet("font-size: 14px; color: #95a5a6; margin-top: 5px;")
        self.lbl_tier.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        balance_layout.addWidget(self.lbl_tier)
        
        layout.addWidget(balance_frame)
        
        # Transaction History Section
        history_label = QtWidgets.QLabel("📜 Historial de Transacciones")
        history_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(history_label)
        
        # Table for transaction history
        self.history_table = QtWidgets.QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            "Fecha", "Tipo", "Puntos", "Ticket ID", "Descripción"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Set column widths
        self.history_table.setColumnWidth(0, 120)  # Fecha
        self.history_table.setColumnWidth(1, 100)  # Tipo
        self.history_table.setColumnWidth(2, 80)   # Puntos
        self.history_table.setColumnWidth(3, 80)   # Ticket ID
        
        layout.addWidget(self.history_table)
        
        # Manual Adjustment Section
        group = QtWidgets.QGroupBox("🔧 Ajuste Manual")
        g_layout = QtWidgets.QHBoxLayout(group)
        
        self.spin_adjust = QtWidgets.QSpinBox()
        self.spin_adjust.setRange(-10000, 10000)
        self.spin_adjust.setPrefix("Puntos: ")
        g_layout.addWidget(self.spin_adjust)
        
        self.input_reason = QtWidgets.QLineEdit()
        self.input_reason.setPlaceholderText("Motivo del ajuste...")
        g_layout.addWidget(self.input_reason)
        
        btn_adjust = QtWidgets.QPushButton("Aplicar Ajuste")
        btn_adjust.setStyleSheet(f"background-color: {colors.get('btn_warning', '#f39c12')}; color: white; padding: 8px; font-weight: bold;")
        btn_adjust.clicked.connect(self._apply_adjustment)
        g_layout.addWidget(btn_adjust)
        
        layout.addWidget(group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh.clicked.connect(self._load_data)
        button_layout.addWidget(btn_refresh)
        
        btn_close = QtWidgets.QPushButton("Cerrar")
        btn_close.setStyleSheet(f"background-color: {colors.get('btn_primary', '#3498db')}; color: white; padding: 8px;")
        btn_close.clicked.connect(self.accept)
        button_layout.addWidget(btn_close)
        
        layout.addLayout(button_layout)

    def _load_data(self):
        """Load customer wallet balance and transaction history from MIDAS loyalty system"""
        try:
            # Get customer data
            customer = self.core.get_customer(self.customer_id)
            if not customer:
                QtWidgets.QMessageBox.warning(self, "Error", "Cliente no encontrado")
                return
            
            # Update customer name
            customer_name = customer.get("first_name", "") + " " + customer.get("last_name", "")
            if not customer_name.strip():
                customer_name = "Cliente"
            self.lbl_customer.setText(f"💰 Monedero de {customer_name}")
            
            # Get MIDAS loyalty balance using engine method
            try:
                # Use get_balance which internally uses get_or_create_account
                wallet_balance = self.loyalty_engine.get_balance(self.customer_id)
                
                # Get account for tier info
                account = self.loyalty_engine.get_or_create_account(self.customer_id)
                
                if account and wallet_balance > 0:
                    tier = account.nivel_lealtad or "BRONCE"  # Fixed: use nivel_lealtad not tier
                    self.lbl_points.setText(f"{wallet_balance:.0f} pts")
                    self.lbl_value.setText(f"Valor: ${wallet_balance:.2f}")
                    self.lbl_tier.setText(f"Nivel: {tier}")
                else:
                    # Account exists but no balance yet
                    self.lbl_points.setText(f"{wallet_balance:.0f} pts")
                    self.lbl_value.setText(f"Valor: ${wallet_balance:.2f}")
                    tier = account.nivel_lealtad if account else "BRONCE"  # Fixed: use nivel_lealtad not tier
                    self.lbl_tier.setText(f"Nivel: {tier}")
            except Exception as e:
                print(f"Error loading MIDAS account: {e}")
                import traceback
                traceback.print_exc()
                # Fallback to zero
                self.lbl_points.setText("0 pts")
                self.lbl_value.setText("Valor: $0.00")
                self.lbl_tier.setText(f"Error: {str(e)}")
            
            # Load transaction history
            self._load_transaction_history()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al cargar datos: {e}")

    def _load_transaction_history(self):
        """Load and display transaction history from MIDAS loyalty_ledger"""
        try:
            # Use loyalty_engine's internal connection to query ledger
            transactions = self.loyalty_engine.connection.execute("""
                SELECT 
                    created_at,
                    tipo,
                    monto,
                    ticket_referencia_id,
                    descripcion
                FROM loyalty_ledger
                WHERE customer_id = %s
                ORDER BY created_at DESC
                LIMIT 100
            """, (self.customer_id,)).fetchall()
            
            if not transactions:
                # No transactions found
                self.history_table.setRowCount(1)
                msg_item = QtWidgets.QTableWidgetItem("No hay transacciones registradas")
                msg_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(0, 0, msg_item)
                self.history_table.setSpan(0, 0, 1, 5)
                return
            
            # Populate table
            self.history_table.clearSpans()
            self.history_table.setRowCount(len(transactions))
            
            for row, txn in enumerate(transactions):
                # Date
                date_str = txn[0][:16] if txn[0] else "N/A"  # Format: YYYY-MM-DD HH:MM
                self.history_table.setItem(row, 0, QtWidgets.QTableWidgetItem(date_str))
                
                # Type
                txn_type = txn[1] or "EARN"
                type_display = {
                    "EARN": "✅ Ganados",
                    "REDEEM": "🛍️ Canjeados",
                    "ADJUST": "🔧 Ajuste",
                    "EXPIRE": "⏰ Expirados",
                }.get(txn_type, txn_type)
                self.history_table.setItem(row, 1, QtWidgets.QTableWidgetItem(type_display))
                
                # Points (with +/- sign)
                amount = txn[2] or 0
                amount_text = f"+{amount:.0f}" if amount > 0 else f"{amount:.0f}"
                amount_item = QtWidgets.QTableWidgetItem(amount_text)
                amount_item.setForeground(QtCore.Qt.GlobalColor.green if amount > 0 else QtCore.Qt.GlobalColor.red)
                amount_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.history_table.setItem(row, 2, amount_item)
                
                # Ticket ID
                ticket_id = str(txn[3]) if txn[3] else "-"
                self.history_table.setItem(row, 3, QtWidgets.QTableWidgetItem(ticket_id))
                
                # Description
                desc = txn[4] or "-"
                self.history_table.setItem(row, 4, QtWidgets.QTableWidgetItem(desc))
                
        except Exception as e:
            # Table might not exist or error reading
            print(f"Error loading transactions from loyalty_ledger: {e}")
            import traceback
            traceback.print_exc()
            self.history_table.setRowCount(1)
            msg_item = QtWidgets.QTableWidgetItem(f"Error al cargar historial: {str(e)}")
            msg_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.history_table.setItem(0, 0, msg_item)
            self.history_table.setSpan(0, 0, 1, 5)

    def _apply_adjustment(self):
        """Apply manual adjustment to wallet balance using MIDAS loyalty engine"""
        from decimal import Decimal
        
        amount = self.spin_adjust.value()
        reason = self.input_reason.text().strip()
        
        if amount == 0:
            QtWidgets.QMessageBox.warning(self, "Error", "El ajuste no puede ser cero")
            return
        
        if not reason:
            QtWidgets.QMessageBox.warning(self, "Error", "Debe especificar un motivo para el ajuste")
            return
        
        try:
            # Use MIDAS loyalty engine to record the adjustment
            descripcion = f"Ajuste manual: {reason}"
            
            if amount > 0:
                # Positive adjustment - use acumular_puntos
                success = self.loyalty_engine.acumular_puntos(
                    customer_id=self.customer_id,
                    monto=Decimal(str(amount)),
                    ticket_id=None,
                    turn_id=STATE.current_turn_id,
                    user_id=STATE.user_id,
                    carrito=None,
                    descripcion=descripcion
                )
            else:
                # Negative adjustment - use redimir_puntos
                success = self.loyalty_engine.redimir_puntos(
                    customer_id=self.customer_id,
                    monto_a_usar=Decimal(str(abs(amount))),
                    ticket_id=None,
                    turn_id=STATE.current_turn_id,
                    user_id=STATE.user_id,
                    razon=descripcion
                )
            
            if success:
                QtWidgets.QMessageBox.information(self, "Éxito", 
                    f"Ajuste de {amount:+.0f} puntos aplicado correctamente")
                
                # Clear inputs and reload
                self.spin_adjust.setValue(0)
                self.input_reason.clear()
                self._load_data()
            else:
                QtWidgets.QMessageBox.warning(self, "Error",
                    "No se pudo aplicar el ajuste. Verifica que el cliente tenga saldo suficiente.")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo aplicar el ajuste: {e}")

    def closeEvent(self, event):
        """Cleanup on close."""
        super().closeEvent(event)
