from PyQt6 import QtCore, QtWidgets


class QuantityDialog(QtWidgets.QDialog):
    def __init__(self, current_qty=1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cantidad")
        self.qty = current_qty
        
        layout = QtWidgets.QVBoxLayout()
        self.input = QtWidgets.QSpinBox()
        self.input.setRange(1, 9999)
        self.input.setValue(int(current_qty))
        self.input.setStyleSheet("font-size: 24px; height: 50px;")
        layout.addWidget(self.input)
        
        btn = QtWidgets.QPushButton("Aceptar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.setLayout(layout)
        
    def get_quantity(self):
        return self.input.value()

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
