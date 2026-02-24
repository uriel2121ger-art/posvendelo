from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class PriceCheckerDialog(QDialog):
    def __init__(self, core, branch_id=None, on_add=None, parent=None):
        super().__init__(parent)
        self.core = core
        self.branch_id = branch_id
        self.on_add = on_add
        self.setWindowTitle("Verificador de Precios")
        self.resize(500, 400)
        
        layout = QVBoxLayout()
        
        self.search_line = QtWidgets.QLineEdit()
        self.search_line.setPlaceholderText("Escanea o escribe código...")
        # self.search_line.returnPressed.connect(self.do_search) # Removed to avoid conflict with scanner
        self.search_line.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.search_line)
        
        self.info_label = QLabel("Escanea un producto")
        self.info_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #555;")
        self.info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        
        self.price_label = QLabel("$0.00")
        self.price_label.setStyleSheet("font-size: 48px; font-weight: bold; color: #2ecc71;")
        self.price_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.price_label)
        
        self.stock_label = QLabel("")
        self.stock_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stock_label)
        
        self.btn_add = QPushButton("Agregar al Carrito (Espacio)")
        self.btn_add.setStyleSheet("")  # Styled in showEvent
        self.btn_add.clicked.connect(self.add_to_cart)
        self.btn_add.setEnabled(False)
        layout.addWidget(self.btn_add)
        
        # Shortcut for adding
        self.add_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Space), self)
        self.add_shortcut.activated.connect(self.add_to_cart)
        
        btn_close = QPushButton("Cerrar (Esc)")
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
        self.current_product = None
        self.search_line.setFocus()
        self.search_line.installEventFilter(self) # Install event filter
        
        # Timer for scanner input
        self.scan_timer = QtCore.QTimer(self)
        self.scan_timer.setSingleShot(True)
        self.scan_timer.setInterval(600) # 600ms delay to allow manual typing
        self.scan_timer.timeout.connect(self.do_search)

    def on_text_changed(self, text):
        if not text: return
        # Reset timer on each keystroke
        self.scan_timer.start()

    def eventFilter(self, source, event):
        if source == self.search_line and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() == QtCore.Qt.Key.Key_Space:
                if self.current_product and self.btn_add.isEnabled():
                    self.add_to_cart()
                    return True # Consume event
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        # Intercept Enter to prevent closing dialog or triggering default button
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            # If search line has focus, let the timer handle it or force search
            if self.search_line.hasFocus():
                self.scan_timer.stop()
                self.do_search()
            return
            
        # Intercept Space to add to cart if product is ready (fallback)
        if event.key() == QtCore.Qt.Key.Key_Space:
            if self.current_product and self.btn_add.isEnabled():
                self.add_to_cart()
                return
                
        super().keyPressEvent(event)

    def do_search(self):
        code = self.search_line.text().strip()
        if not code: return
        
        product = self.core.get_product_by_sku_or_barcode(code)
        if product:
            self.current_product = dict(product)
            self.info_label.setText(self.current_product.get("name", "Sin nombre"))
            price = float(self.current_product.get("price", 0))
            self.price_label.setText(f"${price:.2f}")
            
            stock = self.current_product.get("stock", 0)
            self.stock_label.setText(f"Existencia: {stock}")
            
            self.btn_add.setEnabled(True)
            # self.search_line.selectAll() # Removed to prevent selection issues
        else:
            self.current_product = None
            self.info_label.setText("Producto no encontrado")
            self.price_label.setText("$0.00")
            self.stock_label.setText("")
            self.btn_add.setEnabled(False)
            # self.search_line.clear() # Don't clear, let user correct
            # self.search_line.selectAll() # Optional: select all to overwrite easily

    def add_to_cart(self):
        if self.current_product and self.on_add:
            self.on_add(self.current_product)
            self.search_line.clear()
            self.search_line.setFocus()
            self.info_label.setText("Producto agregado. Escanea otro.")
            self.price_label.setText("$0.00")
            self.stock_label.setText("")
            self.btn_add.setEnabled(False)
            self.current_product = None

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

    def closeEvent(self, event):
        """Cleanup timers on close."""
        if hasattr(self, 'scan_timer') and self.scan_timer:
            self.scan_timer.stop()
        super().closeEvent(event)

