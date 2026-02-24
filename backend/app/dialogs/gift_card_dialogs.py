"""
GIFT CARD ACTIVATION DIALOG
Dialog for activating gift cards when selling them
"""

from datetime import datetime, timedelta
from decimal import Decimal

from PyQt6 import QtCore, QtGui, QtWidgets


class GiftCardActivationDialog(QtWidgets.QDialog):
    """
    Dialog for activating a gift card.
    
    Appears when selling a "Gift Card" product.
    Generates secure code and activates the card.
    """
    
    def __init__(self, amount: float, gift_engine, parent=None):
        super().__init__(parent)
        self.amount = amount
        self.gift_engine = gift_engine
        self.card_code = None
        
        self.setWindowTitle("Activar Tarjeta de Regalo")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._build_ui()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel("🎁 Activación de Tarjeta de Regalo")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #27ae60;")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Amount
        amount_label = QtWidgets.QLabel(f"Monto: ${self.amount:.2f}")
        amount_label.setStyleSheet("font-size: 14pt; margin: 10px;")
        amount_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(amount_label)
        
        # Code input (optional - for pre-printed cards)
        code_group = QtWidgets.QGroupBox("Código de Tarjeta")
        code_layout = QtWidgets.QVBoxLayout()
        
        self.manual_radio = QtWidgets.QRadioButton("Escanear/Ingresar código manualmente")
        self.auto_radio = QtWidgets.QRadioButton("Generar código automáticamente")
        self.auto_radio.setChecked(True)
        
        code_layout.addWidget(self.manual_radio)
        code_layout.addWidget(self.auto_radio)
        
        self.code_input = QtWidgets.QLineEdit()
        self.code_input.setPlaceholderText("GC-XXXX-XXXX-XXXX")
        self.code_input.setEnabled(False)
        self.code_input.setMaxLength(17)
        code_layout.addWidget(self.code_input)
        
        self.manual_radio.toggled.connect(lambda checked: self.code_input.setEnabled(checked))
        
        code_group.setLayout(code_layout)
        layout.addWidget(code_group)
        
        # Expiration
        exp_group = QtWidgets.QGroupBox("Vigencia")
        exp_layout = QtWidgets.QFormLayout()
        
        self.exp_months = QtWidgets.QSpinBox()
        self.exp_months.setRange(1, 60)
        self.exp_months.setValue(12)
        self.exp_months.setSuffix(" meses")
        
        exp_date = datetime.now() + timedelta(days=30 * 12)
        self.exp_label = QtWidgets.QLabel(f"Expira: {exp_date.strftime('%d/%m/%Y')}")
        self.exp_months.valueChanged.connect(self._update_exp_date)
        
        exp_layout.addRow("Validez:", self.exp_months)
        exp_layout.addRow("", self.exp_label)
        
        exp_group.setLayout(exp_layout)
        layout.addWidget(exp_group)
        
        # Notes
        notes_group = QtWidgets.QGroupBox("Notas (Opcional)")
        notes_layout = QtWidgets.QVBoxLayout()
        
        self.notes_input = QtWidgets.QTextEdit()
        self.notes_input.setPlaceholderText("Ej: Regalo para María, Promoción 2x1, etc.")
        self.notes_input.setMaximumHeight(60)
        notes_layout.addWidget(self.notes_input)
        
        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.cancel_btn = QtWidgets.QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.activate_btn = QtWidgets.QPushButton("✓ Activar Tarjeta")
        self.activate_btn.setStyleSheet("background: #27ae60; color: white; font-weight: bold; padding: 10px;")
        self.activate_btn.setDefault(True)
        self.activate_btn.clicked.connect(self._activate)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.activate_btn)
        
        layout.addLayout(button_layout)
    
    def _update_exp_date(self, months):
        exp_date = datetime.now() + timedelta(days=30 * months)
        self.exp_label.setText(f"Expira: {exp_date.strftime('%d/%m/%Y')}")
    
    def _activate(self):
        """Activate the gift card."""
        try:
            # Get or generate code
            if self.manual_radio.isChecked():
                code = self.code_input.text().strip().upper()
                if not code:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Código Requerido",
                        "Ingresa el código de gift card a escanear/ingresar manualmente"
                    )
                    return
                # Validate format: GC-XXXX-XXXX-XXXX
                import re
                pattern = re.compile(r'^GC-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$')
                if not pattern.match(code):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Formato Inválido",
                        "El código debe tener el formato: GC-XXXX-XXXX-XXXX\n"
                        "Ejemplo: GC-A1B2-C3D4-E5F6"
                    )
                    return
            else:
                # Generate new code
                code = self.gift_engine.generate_code()
            
            # Create card
            notes = self.notes_input.toPlainText().strip() or None
            exp_months = self.exp_months.value()
            
            # Check if code already exists (for manual entry)
            if self.manual_radio.isChecked():
                try:
                    existing = self.gift_engine.validate_card(code)
                    if existing['valid'] or existing['status'] != 'not_found':
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Código Duplicado",
                            f"El código {code} ya existe con status: {existing['status']}"
                        )
                        return
                except Exception:
                    pass  # Card doesn't exist, OK to create
            
            # Create card (inactive) via engine (works for both manual and auto codes)
            manual_code = code if self.manual_radio.isChecked() else None
            code = self.gift_engine.create_card(
                initial_balance=Decimal(str(self.amount)),
                expiration_months=exp_months,
                notes=notes,
                code=manual_code
            )
            
            # Activate immediately
            self.gift_engine.activate_card(code)
            
            self.card_code = code
            
            # Show success message with code
            QtWidgets.QMessageBox.information(
                self,
                "✓ Tarjeta Activada",
                f"<h2>¡Tarjeta Activada!</h2>"
                f"<p style='font-size: 14pt; font-weight: bold;'>Código: {code}</p>"
                f"<p>Saldo: ${self.amount:.2f}</p>"
                f"<p>Válida hasta: {(datetime.now() + timedelta(days=30 * exp_months)).strftime('%d/%m/%Y')}</p>"
                f"<p><small>Importante: Entregar este código al cliente</small></p>"
            )
            
            self.accept()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudo activar la tarjeta:\n{str(e)}"
            )

class GiftCardRedemptionDialog(QtWidgets.QDialog):
    """
    Dialog for redeeming a gift card as payment method.
    """
    
    def __init__(self, total_amount: float, gift_engine, parent=None):
        super().__init__(parent)
        self.total_amount = total_amount
        self.gift_engine = gift_engine
        self.result_amount = 0.0
        self.card_code = None
        
        self.setWindowTitle("Pagar con Tarjeta de Regalo")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self._build_ui()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel("🎁 Pago con Tarjeta de Regalo")
        header.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Total to pay
        total_label = QtWidgets.QLabel(f"Total a pagar: ${self.total_amount:.2f}")
        total_label.setStyleSheet("font-size: 14pt; margin: 10px;")
        total_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(total_label)
        
        # Code input
        code_group = QtWidgets.QGroupBox("Código de Tarjeta")
        code_layout = QtWidgets.QVBoxLayout()
        
        self.code_input = QtWidgets.QLineEdit()
        self.code_input.setPlaceholderText("GC-XXXX-XXXX-XXXX")
        self.code_input.setMaxLength(17)
        self.code_input.returnPressed.connect(self._check_balance)
        code_layout.addWidget(self.code_input)
        
        self.check_btn = QtWidgets.QPushButton("Verificar Saldo")
        self.check_btn.clicked.connect(self._check_balance)
        code_layout.addWidget(self.check_btn)
        
        code_group.setLayout(code_layout)
        layout.addWidget(code_group)
        
        # Balance info
        self.balance_group = QtWidgets.QGroupBox("Información de Tarjeta")
        self.balance_group.setVisible(False)
        balance_layout = QtWidgets.QFormLayout()
        
        self.balance_label = QtWidgets.QLabel()
        self.exp_label = QtWidgets.QLabel()
        self.amount_to_use_input = QtWidgets.QDoubleSpinBox()
        self.amount_to_use_input.setRange(0.01, 999999.99)
        self.amount_to_use_input.setPrefix("$ ")
        self.amount_to_use_input.setDecimals(2)
        
        balance_layout.addRow("Saldo disponible:", self.balance_label)
        balance_layout.addRow("Vigencia:", self.exp_label)
        balance_layout.addRow("Usar:", self.amount_to_use_input)
        
        self.balance_group.setLayout(balance_layout)
        layout.addWidget(self.balance_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.cancel_btn = QtWidgets.QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.apply_btn = QtWidgets.QPushButton("✓ Aplicar Pago")
        self.apply_btn.setStyleSheet("background: #27ae60; color: white; font-weight: bold;")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
    
    def _check_balance(self):
        """Check gift card balance."""
        code = self.code_input.text().strip().upper()
        if not code:
            return
        
        try:
            validation = self.gift_engine.validate_card(code)
            
            if not validation['valid']:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Tarjeta No Válida",
                    validation['message']
                )
                return
            
            # Show balance
            balance = validation['balance']
            exp_date = datetime.fromisoformat(validation['expiration_date'])
            
            self.balance_label.setText(f"${balance:.2f}")
            self.exp_label.setText(exp_date.strftime("%d/%m/%Y"))
            
            # Set amount to use (min of balance and total)
            amount_to_use = min(float(balance), self.total_amount)
            self.amount_to_use_input.setValue(amount_to_use)
            self.amount_to_use_input.setMaximum(min(float(balance), self.total_amount))
            
            self.balance_group.setVisible(True)
            self.apply_btn.setEnabled(True)
            self.card_code = code
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error al verificar tarjeta:\n{str(e)}"
            )
    
    def _apply(self):
        """Apply gift card payment."""
        self.result_amount = self.amount_to_use_input.value()
        self.accept()

    def showEvent(self, event):
        """Apply theme colors when dialog is shown."""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            for btn in self.findChildren(QtWidgets.QPushButton):
                text = btn.text().lower()
                if any(w in text for w in ['guardar', 'save', 'aceptar', 'ok', 'crear', 'agregar']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(w in text for w in ['cancelar', 'cancel', 'cerrar', 'eliminar', 'delete']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception:
            pass
