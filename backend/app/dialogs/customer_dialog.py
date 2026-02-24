"""
Customer Dialog for Quick Add/Edit
"""
from PyQt6 import QtCore, QtWidgets


class CustomerDialog(QtWidgets.QDialog):
    """Dialog for adding or editing customers quickly"""
    
    def __init__(self, parent=None, customer_data=None):
        super().__init__(parent)
        self.customer_data = customer_data or {}
        self.result_data = None
        self.setup_ui()
        
        if customer_data:
            self.load_customer(customer_data)
    
    def setup_ui(self):
        """Setup the UI"""
        self.setWindowTitle("Cliente" if not self.customer_data else "Editar Cliente")
        self.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Form layout
        form = QtWidgets.QFormLayout()
        
        # Name (required)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Nombre completo *")
        form.addRow("Nombre:*", self.name_edit)
        
        # Phone
        self.phone_edit = QtWidgets.QLineEdit()
        self.phone_edit.setPlaceholderText("Teléfono")
        form.addRow("Teléfono:", self.phone_edit)
        
        # Email
        self.email_edit = QtWidgets.QLineEdit()
        self.email_edit.setPlaceholderText("email@ejemplo.com")
        form.addRow("Email:", self.email_edit)
        
        # Address
        self.address_edit = QtWidgets.QTextEdit()
        self.address_edit.setMaximumHeight(60)
        self.address_edit.setPlaceholderText("Dirección (opcional)")
        form.addRow("Dirección:", self.address_edit)
        
        # Credit limit
        self.credit_limit_spin = QtWidgets.QDoubleSpinBox()
        self.credit_limit_spin.setRange(0, 1000000)
        self.credit_limit_spin.setPrefix("$ ")
        form.addRow("Límite Crédito:", self.credit_limit_spin)
        
        layout.addLayout(form)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def load_customer(self, customer_data):
        """Load existing customer data"""
        self.name_edit.setText(customer_data.get('name', ''))
        self.phone_edit.setText(customer_data.get('phone', ''))
        self.email_edit.setText(customer_data.get('email', ''))
        self.address_edit.setPlainText(customer_data.get('address', ''))
        self.credit_limit_spin.setValue(customer_data.get('credit_limit', 0))
    
    def validate_and_accept(self):
        """Validate input and accept"""
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Error", "El nombre es obligatorio")
            self.name_edit.setFocus()
            return
        
        email = self.email_edit.text().strip()
        if email and '@' not in email:
            QtWidgets.QMessageBox.warning(self, "Error", "Email inválido")
            self.email_edit.setFocus()
            return
        
        # Collect data
        self.result_data = {
            'name': name,
            'phone': self.phone_edit.text().strip(),
            'email': email,
            'address': self.address_edit.toPlainText().strip(),
            'credit_limit': self.credit_limit_spin.value()
        }
        
        if self.customer_data and 'id' in self.customer_data:
            self.result_data['id'] = self.customer_data['id']
        
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
