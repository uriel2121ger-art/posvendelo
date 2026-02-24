from PyQt6 import QtCore, QtWidgets


class TurnOpenDialog(QtWidgets.QDialog):
    def __init__(self, username, core, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Abrir Turno - {username}")
        self.resize(300, 150)
        self.result_data = None
        
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(f"Usuario: {username}"))
        layout.addWidget(QtWidgets.QLabel("Monto Inicial en Caja:"))
        
        self.amount_input = QtWidgets.QDoubleSpinBox()
        self.amount_input.setRange(0, 100000)
        self.amount_input.setPrefix("$")
        self.amount_input.setValue(0.0)
        layout.addWidget(self.amount_input)
        
        btn = QtWidgets.QPushButton("Abrir Turno")
        btn.clicked.connect(self.accept_turn)
        layout.addWidget(btn)
        
        self.setLayout(layout)
        
    def accept_turn(self):
        self.result_data = {
            "opening_amount": self.amount_input.value(),
            "notes": ""
        }
        self.accept()

    def get_initial_amount(self):
        return self.amount_input.value()

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
