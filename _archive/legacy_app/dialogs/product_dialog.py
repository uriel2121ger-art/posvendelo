from PyQt6 import QtWidgets


class ProductDialog(QtWidgets.QDialog):
    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Producto")
        self.resize(400, 400)
        self.product_data = {}
        
        layout = QtWidgets.QFormLayout()
        
        self.sku = QtWidgets.QLineEdit()
        self.name = QtWidgets.QLineEdit()
        self.price = QtWidgets.QDoubleSpinBox()
        self.price.setRange(0, 99999)
        self.cost = QtWidgets.QDoubleSpinBox()
        self.cost.setRange(0, 99999)
        self.stock = QtWidgets.QSpinBox()
        self.stock.setRange(0, 99999)
        
        if product:
            self.sku.setText(product.get('sku', ''))
            self.name.setText(product.get('name', ''))
            self.price.setValue(float(product.get('price', 0)))
            self.cost.setValue(float(product.get('cost', 0)))
            self.stock.setValue(int(product.get('stock', 0)))
            
        layout.addRow("Código (SKU):", self.sku)
        layout.addRow("Nombre:", self.name)
        layout.addRow("Precio Venta:", self.price)
        layout.addRow("Costo:", self.cost)
        layout.addRow("Stock Inicial:", self.stock)
        
        btn_save = QtWidgets.QPushButton("Guardar")
        btn_save.clicked.connect(self.save)
        layout.addRow(btn_save)
        
        self.setLayout(layout)
        
    def save(self):
        self.product_data = {
            "sku": self.sku.text(),
            "name": self.name.text(),
            "price": self.price.value(),
            "cost": self.cost.value(),
            "stock": self.stock.value()
        }
        self.accept()
        
    def get_data(self):
        return self.product_data

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
