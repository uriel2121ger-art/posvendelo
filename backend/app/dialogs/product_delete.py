from PyQt6 import QtWidgets


class ProductDeleteDialog(QtWidgets.QDialog):
    def __init__(self, core, product_id, parent=None):
        super().__init__(parent)
        self.core = core
        self.product_id = product_id
        self.setWindowTitle("Eliminar Producto")
        self.resize(350, 150)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Get product info for confirmation
        product = self.core.get_product_by_id(product_id)
        name = product["name"] if product else "Desconocido"
        sku = product["sku"] if product else "???"
        
        layout.addWidget(QtWidgets.QLabel(f"¿Estás seguro de que deseas eliminar este producto?"))
        
        info_lbl = QtWidgets.QLabel(f"<b>{name}</b><br>SKU: {sku}")
        info_lbl.setStyleSheet("font-size: 14px; margin: 10px;")
        layout.addWidget(info_lbl)
        
        warn_lbl = QtWidgets.QLabel("Esta acción no se puede deshacer (se marcará como inactivo).")
        warn_lbl.setStyleSheet("color: red; font-style: italic;")
        layout.addWidget(warn_lbl)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_delete = QtWidgets.QPushButton("Eliminar")
        btn_delete.setStyleSheet("")  # Styled in showEvent
        btn_delete.clicked.connect(self.confirm_delete)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_delete)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)

    def confirm_delete(self):
        try:
            # Usar engine.delete_product() para consistencia con ProductsTab
            result = self.core.engine.delete_product(self.product_id)
            if result:
                QtWidgets.QMessageBox.information(self, "Eliminado", "Producto eliminado correctamente.")
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "No se pudo eliminar el producto.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo eliminar: {e}")

    def showEvent(self, event):
        """Apply theme colors"""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            # Apply theme to buttons
            for btn in self.findChildren(QtWidgets.QPushButton):
                text = btn.text().lower()
                if any(word in text for word in ['guardar', 'save', 'crear', 'create']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['eliminar', 'delete', 'cancelar', 'cancel', 'confirmar']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['restaurar', 'restore']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['agregar', 'add']):
                    btn.setStyleSheet(f"background: {c['btn_primary']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception as e:
            pass  # Silently fail if theme_manager not available

