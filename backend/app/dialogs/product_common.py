from PyQt6 import QtCore, QtGui, QtWidgets


class CommonProductDialog(QtWidgets.QDialog):
    """Dialog para venta de productos comunes (sin registro en catálogo)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Artículo Común (Ctrl+P)")
        self.resize(450, 350)
        self.result_data = None
        
        layout = QtWidgets.QVBoxLayout()
        
        # Info header
        info = QtWidgets.QLabel("⚠️ Use esta función solo para productos de bajo valor")
        info.setStyleSheet("color: #e67e22; font-weight: bold; padding: 10px;")
        layout.addWidget(info)
        
        # Form
        form = QtWidgets.QFormLayout()
        
        # Description
        self.description_edit = QtWidgets.QLineEdit()
        self.description_edit.setPlaceholderText("Ejemplo: Chicle, Dulce, etc.")
        form.addRow("Descripción*:", self.description_edit)
        
        # Quantity
        self.qty_spin = QtWidgets.QDoubleSpinBox()
        self.qty_spin.setRange(0.01, 9999)
        self.qty_spin.setValue(1.0)
        self.qty_spin.setDecimals(2)
        form.addRow("Cantidad*:", self.qty_spin)
        
        # Unit Price
        self.price_spin = QtWidgets.QDoubleSpinBox()
        self.price_spin.setRange(0.01, 999999)
        self.price_spin.setPrefix("$")
        self.price_spin.setDecimals(2)
        form.addRow("Precio Unitario*:", self.price_spin)
        
        layout.addLayout(form)
        
        # Tax options (for invoicing)
        tax_group = QtWidgets.QGroupBox("Impuestos (para facturación)")
        tax_layout = QtWidgets.QVBoxLayout()
        
        self.iva_check = QtWidgets.QCheckBox("IVA 16%")
        self.iva_check.setChecked(True)
        tax_layout.addWidget(self.iva_check)
        
        self.ieps_check = QtWidgets.QCheckBox("IEPS")
        tax_layout.addWidget(self.ieps_check)
        
        tax_group.setLayout(tax_layout)
        layout.addWidget(tax_group)
        
        # SAT Code field with autocomplete
        sat_group = QtWidgets.QGroupBox("Clave SAT (para facturación)")
        sat_layout = QtWidgets.QVBoxLayout()
        
        self.sat_code_input = QtWidgets.QLineEdit()
        self.sat_code_input.setPlaceholderText("Buscar clave SAT... (ej: 53131600)")
        
        # Búsqueda dinámica SAT (NO carga todo en memoria)
        self.sat_suggestions = QtWidgets.QListWidget()
        self.sat_suggestions.setMaximumHeight(150)
        self.sat_suggestions.setVisible(False)
        self.sat_suggestions.itemClicked.connect(self._select_sat_suggestion)
        
        # Conectar búsqueda al escribir
        self.sat_code_input.textChanged.connect(self._search_sat_codes)
        
        # Set default for common products
        self.sat_code_input.setText("01010101 - No existe en el catálogo")
        
        sat_layout.addWidget(self.sat_code_input)
        sat_layout.addWidget(self.sat_suggestions)  # Lista de sugerencias
        sat_group.setLayout(sat_layout)
        layout.addWidget(sat_group)
        
        # SAT Configuration hint
        sat_hint = QtWidgets.QLabel(
            "💡 Clave por defecto: 01010101 (productos sin clasificación)"
        )
        sat_hint.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 5px;")
        layout.addWidget(sat_hint)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        cancel_btn = QtWidgets.QPushButton("ESC - Cancelar")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setShortcut(QtCore.Qt.Key.Key_Escape)
        
        ok_btn = QtWidgets.QPushButton("ENTER - Agregar a Venta")
        ok_btn.clicked.connect(self.validate_and_accept)
        ok_btn.setShortcut(QtCore.Qt.Key.Key_Return)
        ok_btn.setDefault(True)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Focus on description
        self.description_edit.setFocus()
        
    def validate_and_accept(self):
        description = self.description_edit.text().strip()
        if not description:
            QtWidgets.QMessageBox.warning(
                self,
                "Campo requerido",
                "La descripción del producto es obligatoria"
            )
            self.description_edit.setFocus()
            return
            
        if self.price_spin.value() <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Precio inválido",
                "El precio debe ser mayor a cero"
            )
            self.price_spin.setFocus()
            return
            
        # Extract SAT code (first 8 digits)
        sat_text = self.sat_code_input.text().strip()
        sat_code = sat_text.split(" ")[0] if sat_text else "01010101"
        
        # Build result data
        self.result_data = {
            "description": description,
            "qty": self.qty_spin.value(),
            "price": self.price_spin.value(),
            "iva": self.iva_check.isChecked(),
            "ieps": self.ieps_check.isChecked(),
            "is_common": True,  # Flag to identify common products
            "product_id": None,  # No product ID from catalog
            "name": description,  # For compatibility with cart structure
            "sat_clave_prod_serv": sat_code,  # SAT catalog code for invoicing
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

    def _search_sat_codes(self, text: str):
        """Busca códigos SAT dinámicamente en SQLite (sin cargar todo en memoria)."""
        # Limpiar si el texto es muy corto o es el valor default
        if len(text) < 3 or text.startswith("01010101"):
            self.sat_suggestions.clear()
            self.sat_suggestions.setVisible(False)
            return
        
        try:
            from app.fiscal.sat_catalog_full import get_catalog_manager
            catalog = get_catalog_manager()
            results = catalog.search(text, limit=15)  # Solo 15 resultados
            
            self.sat_suggestions.clear()
            if results:
                for code, desc in results:
                    self.sat_suggestions.addItem(f"{code} - {desc}")
                self.sat_suggestions.setVisible(True)
            else:
                self.sat_suggestions.setVisible(False)
        except Exception:
            self.sat_suggestions.setVisible(False)

    def _select_sat_suggestion(self, item):
        """Selecciona una sugerencia de la lista."""
        if item:
            self.sat_code_input.setText(item.text())
            self.sat_suggestions.setVisible(False)
