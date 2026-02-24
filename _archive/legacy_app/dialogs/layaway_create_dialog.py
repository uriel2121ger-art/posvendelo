from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class LayawayCreateDialog(QDialog):
    def __init__(self, cart, total, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Apartado")
        self.resize(400, 300)
        self.total = total
        self.result_data = None
        self.customer_id = None
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(f"Total de Venta: ${total:.2f}"))
        
        self.lbl_customer = QLabel("Cliente: No asignado")
        layout.addWidget(self.lbl_customer)
        
        layout.addWidget(QLabel("Depósito Inicial:"))
        self.deposit_input = QtWidgets.QDoubleSpinBox()
        self.deposit_input.setRange(0, total)
        self.deposit_input.setPrefix("$")
        self.deposit_input.setValue(total * 0.10) # Default 10%
        layout.addWidget(self.deposit_input)
        
        layout.addWidget(QLabel("Fecha Límite:"))
        self.date_input = QtWidgets.QDateEdit()
        self.date_input.setDate(QtCore.QDate.currentDate().addDays(30))
        self.date_input.setCalendarPopup(True)
        layout.addWidget(self.date_input)
        
        layout.addWidget(QLabel("Notas:"))
        self.notes_input = QtWidgets.QLineEdit()
        layout.addWidget(self.notes_input)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Crear Apartado")
        btn_ok.clicked.connect(self.accept_data)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)

    def set_customer(self, customer_id, customer_name):
        self.customer_id = customer_id
        self.lbl_customer.setText(f"Cliente: {customer_name or 'Desconocido'}")

    def accept_data(self):
        if not self.customer_id:
            QtWidgets.QMessageBox.warning(self, "Error", "Se requiere asignar un cliente.")
            return
            
        deposit = self.deposit_input.value()
        if deposit <= 0:
             QtWidgets.QMessageBox.warning(self, "Error", "El depósito debe ser mayor a 0.")
             return

        self.result_data = {
            "customer_id": self.customer_id,
            "deposit": deposit,
            "due_date": self.date_input.date().toString("yyyy-MM-dd"),
            "notes": self.notes_input.text()
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
