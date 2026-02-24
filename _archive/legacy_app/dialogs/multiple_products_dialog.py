from PyQt6 import QtCore, QtWidgets


class MultipleProductsDialog(QtWidgets.QDialog):
    """Dialog para agregar múltiples unidades de un producto (INS - Varios)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("INS - Agregar Varios")
        self.resize(400, 200)
        self.result_data = None
        
        layout = QtWidgets.QVBoxLayout()
        
        # Instructions
        info = QtWidgets.QLabel("Ingresa el código y la cantidad del producto")
        info.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(info)
        
        # Form
        form = QtWidgets.QFormLayout()
        
        # Product Code/SKU
        self.code_edit = QtWidgets.QLineEdit()
        self.code_edit.setPlaceholderText("Código, SKU o código de barras")
        form.addRow("Código del Producto*:", self.code_edit)
        
        # Quantity
        self.qty_spin = QtWidgets.QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 9999)
        self.qty_spin.setValue(1.0)
        self.qty_spin.setDecimals(2)
        form.addRow("Cantidad*:", self.qty_spin)
        
        layout.addLayout(form)
        layout.addStretch()
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        cancel_btn = QtWidgets.QPushButton("ESC - Cancelar")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setShortcut(QtCore.Qt.Key.Key_Escape)
        
        ok_btn = QtWidgets.QPushButton("ENTER - Agregar")
        ok_btn.clicked.connect(self.validate_and_accept)
        ok_btn.setShortcut(QtCore.Qt.Key.Key_Return)
        ok_btn.setDefault(True)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Focus on code input
        self.code_edit.setFocus()
        
    def validate_and_accept(self):
        code = self.code_edit.text().strip()
        if not code:
            QtWidgets.QMessageBox.warning(
                self,
                "Campo requerido",
                "Debes ingresar el código del producto"
            )
            self.code_edit.setFocus()
            return
            
        if self.qty_spin.value() <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Cantidad inválida",
                "La cantidad debe ser mayor a cero"
            )
            self.qty_spin.setFocus()
            return
            
        self.result_data = {
            "code": code,
            "qty": self.qty_spin.value()
        }
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

    def closeEvent(self, event):
        """Cleanup on close."""
        self.result_data = None
        super().closeEvent(event)
