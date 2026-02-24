from PyQt6 import QtCore, QtWidgets


class PriceChangeDialog(QtWidgets.QDialog):
    """Dialog para cambiar el precio de un producto directamente (doble-click en TITAN)"""
    
    def __init__(self, product_name, current_price, base_price, qty=1.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cambiar Precio")
        self.resize(350, 250)
        self.current_price = current_price
        self.base_price = base_price
        self.qty = qty
        self.result_data = None
        
        layout = QtWidgets.QVBoxLayout()
        
        # Product info
        info_label = QtWidgets.QLabel(f"📦 {product_name}")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(info_label)
        
        # Price info
        price_info = QtWidgets.QLabel(
            f"Precio Base: ${base_price:.2f}\n"
            f"Precio Actual: ${current_price:.2f}\n"
            f"Cantidad: {qty:.2f}"
        )
        price_info.setStyleSheet("color: #7f8c8d; padding: 5px;")
        layout.addWidget(price_info)
        
        # New price input
        form = QtWidgets.QFormLayout()
        
        self.new_price_spin = QtWidgets.QDoubleSpinBox()
        self.new_price_spin.setRange(0, 999999)
        self.new_price_spin.setValue(current_price)
        self.new_price_spin.setPrefix("$")
        self.new_price_spin.setDecimals(2)
        self.new_price_spin.selectAll()
        self.new_price_spin.valueChanged.connect(self.update_preview)
        form.addRow("Nuevo Precio Unitario:", self.new_price_spin)
        
        layout.addLayout(form)
        
        # Preview
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setStyleSheet("background: #ecf0f1; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.preview_label)
        self.update_preview()
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        cancel_btn = QtWidgets.QPushButton("ESC - Cancelar")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setShortcut(QtCore.Qt.Key.Key_Escape)
        
        ok_btn = QtWidgets.QPushButton("ENTER - Aplicar")
        ok_btn.clicked.connect(self.accept_price)
        ok_btn.setShortcut(QtCore.Qt.Key.Key_Return)
        ok_btn.setDefault(True)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Focus on price input
        self.new_price_spin.setFocus()
        
    def update_preview(self):
        new_price = self.new_price_spin.value()
        discount_per_unit = self.base_price - new_price
        discount_total = discount_per_unit * self.qty
        discount_percent = (discount_per_unit / self.base_price * 100) if self.base_price > 0 else 0
        
        if new_price < self.base_price:
            self.preview_label.setText(
                f"💰 Descuento por Unidad: ${discount_per_unit:.2f} ({discount_percent:.1f}%)\n"
                f"📊 Descuento Total: ${discount_total:.2f}\n"
                f"✅ Nuevo Total: ${new_price * self.qty:.2f}"
            )
            self.preview_label.setStyleSheet("background: #d5f4e6; padding: 10px; border-radius: 5px; color: #27ae60;")
        elif new_price > self.base_price:
            increase = new_price - self.base_price
            self.preview_label.setText(
                f"⚠️ Incremento: ${increase:.2f} por unidad\n"
                f"Nuevo Total: ${new_price * self.qty:.2f}"
            )
            self.preview_label.setStyleSheet("background: #fadbd8; padding: 10px; border-radius: 5px; color: #c0392b;")
        else:
            self.preview_label.setText("Sin cambios")
            self.preview_label.setStyleSheet("background: #ecf0f1; padding: 10px; border-radius: 5px;")
    
    def accept_price(self):
        new_price = self.new_price_spin.value()
        
        if new_price < 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Precio inválido",
                "El precio no puede ser negativo"
            )
            return
        
        # Calculate discount per unit (can be negative for price increases)
        discount_per_unit = self.base_price - new_price
        
        self.result_data = {
            "new_price": new_price,
            "discount_per_unit": discount_per_unit,
            "discount_total": discount_per_unit * self.qty
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
