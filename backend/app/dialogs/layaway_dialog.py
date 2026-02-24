from datetime import datetime, timedelta

from PyQt6 import QtCore, QtGui, QtWidgets


class LayawayCreateDialog(QtWidgets.QDialog):
    def __init__(self, total_amount, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Apartado")
        self.resize(400, 300)
        self.total_amount = total_amount
        self.result_data = None
        
        layout = QtWidgets.QVBoxLayout()
        
        # Info
        layout.addWidget(QtWidgets.QLabel(f"Total a Pagar: ${self.total_amount:,.2f}"))
        
        # Initial Payment
        form = QtWidgets.QFormLayout()
        self.initial_payment_spin = QtWidgets.QDoubleSpinBox()
        self.initial_payment_spin.setRange(0, self.total_amount)
        self.initial_payment_spin.setPrefix("$")
        self.initial_payment_spin.setValue(self.total_amount * 0.10) # Default 10%
        form.addRow("Pago Inicial:", self.initial_payment_spin)
        
        # Due Date
        self.due_date_edit = QtWidgets.QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QtCore.QDate.currentDate().addDays(30)) # Default 30 days
        form.addRow("Fecha Límite:", self.due_date_edit)
        
        # Notes
        self.notes_edit = QtWidgets.QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        form.addRow("Notas:", self.notes_edit)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = QtWidgets.QPushButton("Crear Apartado")
        btn_ok.clicked.connect(self.validate_and_accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def validate_and_accept(self):
        initial = self.initial_payment_spin.value()
        if initial >= self.total_amount:
            QtWidgets.QMessageBox.warning(self, "Error", "El pago inicial no puede cubrir el total. Usa una venta normal.")
            return
            
        self.result_data = {
            "initial_payment": initial,
            "due_date": self.due_date_edit.date().toString("yyyy-MM-dd"),
            "notes": self.notes_edit.toPlainText()
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
