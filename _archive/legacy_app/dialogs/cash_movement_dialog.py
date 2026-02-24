from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class CashMovementDialog(QDialog):
    def __init__(self, movement_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Movimiento de Efectivo")
        self.resize(300, 200)
        self.result_data = None
        
        layout = QVBoxLayout()
        
        title = "Entrada de Efectivo" if movement_type == "in" else "Salida de Efectivo"
        layout.addWidget(QLabel(title))
        
        layout.addWidget(QLabel("Monto:"))
        self.amount_input = QtWidgets.QDoubleSpinBox()
        self.amount_input.setRange(0, 999999)
        self.amount_input.setPrefix("$")
        layout.addWidget(self.amount_input)
        
        layout.addWidget(QLabel("Motivo / Razón:"))
        self.reason_input = QtWidgets.QLineEdit()
        layout.addWidget(self.reason_input)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar")
        btn_ok.clicked.connect(self.accept_data)
        btn_ok.setDefault(True)  # Make Guardar the default button (activated by Enter)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)
        self.amount_input.setFocus()
        self.amount_input.selectAll()

    def accept_data(self):
        amount = self.amount_input.value()
        reason = self.reason_input.text().strip()

        if amount <= 0:
            return

        # CRÍTICO: Razón obligatoria para auditoría de movimientos de caja
        # Auditoría 2026-01-30: Agregada validación
        if not reason:
            from PyQt6 import QtWidgets
            QtWidgets.QMessageBox.warning(
                self,
                "Motivo Requerido",
                "Debe ingresar un motivo para el movimiento de caja.\n"
                "Esto es necesario para la auditoría financiera."
            )
            return

        self.result_data = {
            "amount": amount,
            "reason": reason
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
