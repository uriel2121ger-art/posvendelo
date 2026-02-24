import logging

from PyQt6 import QtWidgets

from app.utils.path_utils import get_debug_log_path_str, agent_log_enabled

logger = logging.getLogger(__name__)


class DiscountDialog(QtWidgets.QDialog):
    def __init__(self, base_amount, current_price=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplicar Descuento")
        self.resize(300, 200)
        self.base_amount = base_amount
        self.result_data = None
        
        layout = QtWidgets.QVBoxLayout()
        
        layout.addWidget(QtWidgets.QLabel(f"Monto Base: ${base_amount:.2f}"))
        
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["Porcentaje (%)", "Monto ($)"])
        layout.addWidget(self.type_combo)
        
        self.input = QtWidgets.QDoubleSpinBox()
        self.input.setRange(0, 100)
        self.input.setSuffix(" %")
        self.input.setValue(0)
        layout.addWidget(self.input)

        self.lbl_preview = QtWidgets.QLabel("Descuento: $0.00")
        layout.addWidget(self.lbl_preview)

        self.input.valueChanged.connect(self.update_preview)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.type_combo.currentIndexChanged.connect(self.update_preview)
        
        btn = QtWidgets.QPushButton("Aplicar")
        btn.clicked.connect(self.accept_discount)
        layout.addWidget(btn)
        
        self.setLayout(layout)
        self.input.setFocus()
        self.input.selectAll()

    def _on_type_changed(self, index):
        if index == 0:  # Porcentaje
            self.input.setRange(0, 100)
            self.input.setSuffix(" %")
        else:  # Monto
            self.input.setRange(0, self.base_amount)
            self.input.setSuffix("")

    def update_preview(self):
        val = self.input.value()
        is_percent = self.type_combo.currentIndex() == 0
        
        if is_percent:
            discount = self.base_amount * (val / 100.0)
        else:
            discount = val
            
        self.lbl_preview.setText(f"Descuento: ${discount:.2f}")

    def accept_discount(self):
        val = self.input.value()
        is_percent = self.type_combo.currentIndex() == 0
        
        if is_percent:
            discount_amount = self.base_amount * (val / 100.0)
            type_str = "percent"
        else:
            discount_amount = val
            type_str = "amount"
        
        # CRITICAL: Normalize -0.0 to 0.0 and clamp negative discounts to 0
        # Use tolerance check for floating point comparison
        if abs(discount_amount) < 1e-9:
            discount_amount = 0.0  # Normalize -0.0 and near-zero to 0.0
        else:
            discount_amount = max(0.0, discount_amount)  # Clamp negative discounts to 0
        
        # #region agent log
        if agent_log_enabled():
            import json
            import time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"discount_dialog.py:accept_discount","message":"Discount dialog result","data":{"base_amount":self.base_amount,"is_percent":is_percent,"val":val,"discount_amount":discount_amount,"type_str":type_str},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for discount result: %s", e)
        # #endregion
            
        self.result_data = {
            "type": type_str,
            "value": val,
            "discount_amount": discount_amount
        }
        self.accept()
        
    def get_discount(self):
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
        except Exception as e:
            logger.debug("Applying theme colors in showEvent: %s", e)
