"""
GIFT CARD DIALOG
Dialog for creating gift cards for customers
"""
from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class GiftCardDialog(QtWidgets.QDialog):
    """Dialog for creating a new gift card. Customer is optional (can be for general public)."""
    
    def __init__(self, core, customer_id=None, parent=None):
        super().__init__(parent)
        self.core = core
        self.customer_id = customer_id  # None = público general
        self.gift_engine = core.gift_card_engine
        
        title = "Crear Gift Card" if not customer_id else f"Crear Gift Card (Cliente #{customer_id})"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._build_ui()
    
    def _build_ui(self):
        c = theme_manager.get_colors()
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QtWidgets.QLabel("🎁 Nueva Gift Card")
        header.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c['text_primary']};")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Amount input
        form = QtWidgets.QFormLayout()
        
        self.spin_amount = QtWidgets.QDoubleSpinBox()
        self.spin_amount.setRange(50, 10000)
        self.spin_amount.setValue(500)
        self.spin_amount.setPrefix("$ ")
        self.spin_amount.setDecimals(2)
        self.spin_amount.setFixedHeight(40)
        form.addRow("Monto:", self.spin_amount)
        
        # Expiration months
        self.spin_months = QtWidgets.QSpinBox()
        self.spin_months.setRange(1, 36)
        self.spin_months.setValue(12)
        self.spin_months.setSuffix(" meses")
        self.spin_months.setFixedHeight(40)
        form.addRow("Vigencia:", self.spin_months)
        
        # Notes
        self.txt_notes = QtWidgets.QLineEdit()
        self.txt_notes.setPlaceholderText("Notas opcionales...")
        self.txt_notes.setFixedHeight(40)
        form.addRow("Notas:", self.txt_notes)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.setFixedHeight(40)
        btn_cancel.clicked.connect(self.reject)
        
        btn_create = QtWidgets.QPushButton("✨ Crear Gift Card")
        btn_create.setFixedHeight(40)
        btn_create.setStyleSheet(f"background-color: {c['btn_success']}; color: white; font-weight: bold;")
        btn_create.clicked.connect(self._create_card)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_create)
        layout.addLayout(btn_layout)
    
    def _create_card(self):
        """Create the gift card."""
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        amount = Decimal(str(self.spin_amount.value()))
        months = self.spin_months.value()
        notes = self.txt_notes.text().strip()
        
        try:
            expiration = datetime.now() + timedelta(days=months * 30)
            
            # Define notes based on whether it's for a customer or general public
            if not notes:
                notes = f"Gift Card para cliente #{self.customer_id}" if self.customer_id else "Gift Card - Público General"
            
            code = self.gift_engine.create_card(
                initial_balance=float(amount),
                customer_id=self.customer_id,  # None is OK for general public
                expiration_months=months,
                notes=notes
            )
            
            if code:
                # Activar automáticamente la tarjeta para que tenga saldo
                self.gift_engine.activate_card(code)
                
                QtWidgets.QMessageBox.information(
                    self, "Éxito",
                    f"Gift Card creada y activada:\n\nCódigo: {code}\nMonto: ${amount:.2f}\nVigencia: {months} meses"
                )
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "No se pudo crear la gift card")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al crear gift card: {e}")
