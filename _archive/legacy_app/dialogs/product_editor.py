from PyQt6 import QtCore, QtGui, QtWidgets
import logging

logger = logging.getLogger(__name__)

from app.utils.path_utils import agent_log_enabled
from app.config.constants import (
    BARCODE_PREVIEW_MIN_HEIGHT,
    COLOR_CUSTOM_BG,
    COLOR_CUSTOM_BORDER,
    COLOR_CUSTOM_TEXT,
    COLOR_INVALID_BG,
    COLOR_INVALID_BORDER,
    COLOR_INVALID_TEXT,
    COLOR_VALID_BG,
    COLOR_VALID_BORDER,
    COLOR_VALID_TEXT,
    COLOR_WARNING_BG,
    COLOR_WARNING_BORDER,
    COLOR_WARNING_TEXT,
    ERR_SKU_GENERATION_FAILED,
    GENERATE_BUTTON_MAX_WIDTH,
    MSG_SKU_GENERATED,
    SKU_INPUT_MIN_LENGTH,
    WARN_SKU_TOO_SHORT,
)


# Custom completer for multi-word search
class CustomSATCompleter(QtWidgets.QCompleter):
    """QCompleter que soporta búsqueda multi-palabra.
    
    Permite buscar 'papel hi' y encontrar 'papel higiénico'.
    """
    def __init__(self, model, parent=None):
        super().__init__(model, parent)
        self.local_completion_prefix = ""
        self.source_model = model
        
    def splitPath(self, path):
        """Divide el path en palabras para búsqueda multi-token."""
        self.local_completion_prefix = path
        return [path]
    
    def pathFromIndex(self, index):
        """Retorna el path completo desde el índice."""
        return self.source_model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)

class SATProxyModel(QtCore.QSortFilterProxyModel):
    """Modelo proxy que filtra por todas las palabras en la búsqueda."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter_words = []
        
    def setFilterWords(self, words):
        """Establece las palabras a buscar."""
        self.filter_words = [w.lower() for w in words if w]
        self.invalidateFilter()
        
    def filterAcceptsRow(self, source_row, source_parent):
        """Acepta filas que contengan TODAS las palabras buscadas."""
        if not self.filter_words:
            return True
            
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        text = model.data(index, QtCore.Qt.ItemDataRole.DisplayRole)
        
        if not text:
            return False
            
        text_lower = text.lower()
        # La fila se acepta si TODAS las palabras están presentes
        return all(word in text_lower for word in self.filter_words)

class ProductEditorDialog(QtWidgets.QDialog):
    def __init__(self, core, product=None, parent=None):
        super().__init__(parent)
        self.core = core
        self.product = product
        self.setWindowTitle("Editor de Producto" if product else "Nuevo Producto")
        self.resize(600, 500)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Form Layout
        form_layout = QtWidgets.QFormLayout()
        
        # 🆕 IDENTITY V2: Prefijo fijo (siempre '20' - General, oculto)
        # El selector está oculto y siempre usa el prefijo '20' (General)
        self.prefix_combo = None
        self.default_prefix = '20'  # Siempre usar General
        
        # SKU Input con botón generador
        sku_layout = QtWidgets.QHBoxLayout()
        self.sku_input = QtWidgets.QLineEdit()
        self.sku_input.setPlaceholderText("Código de barras o SKU")
        self.sku_input.textChanged.connect(self.on_sku_changed)
        sku_layout.addWidget(self.sku_input)
        
        # 🪄 Botón Generar SKU (Magic Wand)
        if not product:
            self.btn_generate_sku = QtWidgets.QPushButton("🪄 Generar")
            self.btn_generate_sku.setToolTip("Generar código de barras automático (Ctrl+G)")
            self.btn_generate_sku.clicked.connect(self.on_generate_sku_clicked)
            self.btn_generate_sku.setMaximumWidth(GENERATE_BUTTON_MAX_WIDTH)
            self.btn_generate_sku.setShortcut("Ctrl+G")
            sku_layout.addWidget(self.btn_generate_sku)
        else:
            self.btn_generate_sku = None
        
        form_layout.addRow("SKU / Código:", sku_layout)
        
        # 📊 Vista Previa del Código de Barras
        self.barcode_preview = QtWidgets.QLabel()
        self.barcode_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.barcode_preview.setStyleSheet("padding: 10px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 4px;")
        self.barcode_preview.setMinimumHeight(BARCODE_PREVIEW_MIN_HEIGHT)
        form_layout.addRow("Vista Previa:", self.barcode_preview)
        
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Nombre del producto")
        self.name_input.textChanged.connect(self._on_name_changed)
        form_layout.addRow("Nombre:", self.name_input)
        
        # Label para sugerencias automáticas
        self.auto_classify_label = QtWidgets.QLabel("")
        self.auto_classify_label.setStyleSheet("color: #27ae60; font-size: 11px; font-style: italic;")
        self.auto_classify_label.setWordWrap(True)
        self.auto_classify_label.setVisible(False)
        form_layout.addRow("", self.auto_classify_label)
        
        # Botón para aplicar clasificación automática
        self.btn_auto_classify = QtWidgets.QPushButton("🎯 Clasificar Automáticamente")
        self.btn_auto_classify.setVisible(False)
        self.btn_auto_classify.clicked.connect(self._apply_auto_classification)
        form_layout.addRow("", self.btn_auto_classify)
        
        # Timer para debounce de sugerencias
        self.suggestion_timer = QtCore.QTimer(self)
        self.suggestion_timer.setSingleShot(True)
        self.suggestion_timer.timeout.connect(self._generate_suggestion)
        self.current_suggestion = None
        
        self.price_input = QtWidgets.QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setPrefix("$")
        form_layout.addRow("Precio Venta:", self.price_input)
        
        self.wholesale_input = QtWidgets.QDoubleSpinBox()
        self.wholesale_input.setRange(0, 999999)
        self.wholesale_input.setPrefix("$")
        form_layout.addRow("Precio Mayoreo:", self.wholesale_input)
        
        self.cost_input = QtWidgets.QDoubleSpinBox()
        self.cost_input.setRange(0, 999999)
        self.cost_input.setPrefix("$")
        form_layout.addRow("Costo:", self.cost_input)
        
        self.stock_input = QtWidgets.QDoubleSpinBox()
        # CRÍTICO: No permitir stock negativo - el inventario debe ser >= 0
        # Auditoría 2026-01-30: Corregido de (-9999, 9999) a (0, 999999)
        self.stock_input.setRange(0, 999999)
        form_layout.addRow("Existencia:", self.stock_input)
        
        self.min_stock_input = QtWidgets.QDoubleSpinBox()
        self.min_stock_input.setRange(0, 9999)
        form_layout.addRow("Stock Mínimo:", self.min_stock_input)
        
        # Departamento/Categoría - ComboBox editable con categorías existentes
        self.dept_input = QtWidgets.QComboBox()
        self.dept_input.setEditable(True)
        self.dept_input.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.dept_input.lineEdit().setPlaceholderText("Selecciona o escribe una categoría...")
        
        # Cargar categorías existentes de la base de datos
        try:
            categories = self.core.db.execute_query(
                "SELECT DISTINCT department FROM products WHERE department IS NOT NULL AND department != '' ORDER BY department"
            )
            self.dept_input.addItem("")  # Opción vacía
            for cat in categories:
                dept = dict(cat).get("department", "")
                if dept:
                    self.dept_input.addItem(dept)
        except Exception as e:
            print(f"Error loading categories: {e}")
        
        form_layout.addRow("Categoría:", self.dept_input)
        
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["Unidad", "Granel", "Kit"])
        form_layout.addRow("Tipo Venta:", self.type_combo)
        
        # ─────────────────────────────────────────────────────────────
        # SAT Catalog fields (for CFDI 4.0 electronic invoicing)
        # ─────────────────────────────────────────────────────────────
        sat_group = QtWidgets.QGroupBox("📋 Catálogo SAT (Facturación)")
        sat_layout = QtWidgets.QFormLayout(sat_group)
        
        # ClaveProdServ (product/service code) with autocomplete
        sat_prod_layout = QtWidgets.QHBoxLayout()
        self.sat_clave_prod_input = QtWidgets.QLineEdit()
        self.sat_clave_prod_input.setPlaceholderText("Buscar código o descripción SAT...")
        self.sat_clave_prod_input.setMaxLength(8)
        self.sat_clave_prod_input.setText("01010101")  # Default: No existe en catálogo
        
        # Autocomplete dinámico - NO carga todo en memoria
        from app.fiscal.sat_catalog_full import get_catalog_manager
        self.sat_catalog = get_catalog_manager()
        
        # Lista de sugerencias (reemplaza el QCompleter que cargaba 52k items)
        self.sat_suggestions = QtWidgets.QListWidget()
        self.sat_suggestions.setMaximumHeight(150)
        self.sat_suggestions.setMaximumWidth(400)
        self.sat_suggestions.setVisible(False)
        self.sat_suggestions.itemClicked.connect(self._on_sat_suggestion_clicked)
        
        # Buscar solo cuando hay 2+ caracteres
        def on_text_changed(text):
            text = text.strip()
            # No buscar si es código por defecto o muy corto
            if len(text) < 2 or text.startswith("01010101"):
                self.sat_suggestions.clear()
                self.sat_suggestions.setVisible(False)
                return
            
            # Búsqueda dinámica en SQLite (rápido, solo trae 20 resultados)
            try:
                results = self.sat_catalog.search(text, limit=20)
                self.sat_suggestions.clear()
                if results:
                    for code, desc in results:
                        self.sat_suggestions.addItem(f"{code} - {desc}")
                    self.sat_suggestions.setVisible(True)
                else:
                    self.sat_suggestions.setVisible(False)
            except Exception:
                self.sat_suggestions.setVisible(False)
        
        self.sat_clave_prod_input.textChanged.connect(on_text_changed)
        
        self.sat_clave_prod_input.setToolTip(
            "Escribe para buscar en el catálogo SAT.\\n"
            "Puedes buscar por código (ej: 501) o descripción (ej: refrescos)\\n\\n"
            "01010101 = No existe en catálogo (genérico válido)\\n"
            "50161700 = Refrescos\\n"
            "50202201 = Café"
        )
        sat_prod_layout.addWidget(self.sat_clave_prod_input)
        
        # Preview label for selected code
        self.sat_code_preview = QtWidgets.QLabel("")
        self.sat_code_preview.setStyleSheet("color: #666; font-size: 11px;")
        sat_prod_layout.addWidget(self.sat_code_preview)
        
        # Hidden field to store description for saving
        self._sat_descripcion = ""
        
        sat_layout.addRow("Clave Prod/Serv:", sat_prod_layout)
        sat_layout.addRow("", self.sat_suggestions)  # Lista de sugerencias debajo
        
        # ClaveUnidad (unit code)
        self.sat_clave_unidad_combo = QtWidgets.QComboBox()
        sat_unidades = [
            ("H87", "Pieza"),
            ("KGM", "Kilogramo"),
            ("LTR", "Litro"),
            ("MTR", "Metro"),
            ("MTK", "Metro cuadrado"),
            ("XBX", "Caja"),
            ("XPK", "Paquete"),
            ("ACT", "Actividad"),
            ("E48", "Unidad de servicio"),
            ("GRM", "Gramo"),
            ("MLT", "Mililitro"),
            ("SET", "Conjunto"),
            ("PR", "Par"),
        ]
        for code, desc in sat_unidades:
            self.sat_clave_unidad_combo.addItem(f"{code} - {desc}", code)
        self.sat_clave_unidad_combo.setToolTip("Clave de unidad SAT para facturación electrónica")
        sat_layout.addRow("Clave Unidad:", self.sat_clave_unidad_combo)
        
        form_layout.addRow(sat_group)
        # ─────────────────────────────────────────────────────────────
        
        layout.addLayout(form_layout)
        
        # Buttons
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QtWidgets.QPushButton("Guardar")
        btn_save.clicked.connect(self.save_product)
        btn_save.setDefault(True)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)
        
        if self.product:
            self.load_data()
        else:
            # Modo creación: mostrar mensaje inicial
            self.barcode_preview.setText("Genera o ingresa un SKU para ver la vista previa")
   
    def on_sku_changed(self, text):
        """Actualiza vista previa al cambiar SKU."""
        if not text or len(text) < SKU_INPUT_MIN_LENGTH:
            self.barcode_preview.setText(WARN_SKU_TOO_SHORT)
            self.barcode_preview.setStyleSheet(f"padding: 10px; background: {COLOR_WARNING_BG}; border: 1px solid {COLOR_WARNING_BORDER}; color: {COLOR_WARNING_TEXT}; border-radius: 4px;")
            return
        
        # Validar si es EAN-13
        if len(text) == 13:
            try:
                is_valid = self.core.validate_ean13(text)
                if is_valid:
                    self.barcode_preview.setText(f"✓ EAN-13 Válido\n{text}")
                    self.barcode_preview.setStyleSheet(f"padding: 10px; background: {COLOR_VALID_BG}; border: 1px solid {COLOR_VALID_BORDER}; color: {COLOR_VALID_TEXT}; border-radius: 4px; font-weight: bold;")
                else:
                    self.barcode_preview.setText(f"⚠ EAN-13 Inválido (checksum incorrecto)\n{text}")
                    self.barcode_preview.setStyleSheet(f"padding: 10px; background: {COLOR_INVALID_BG}; border: 1px solid {COLOR_INVALID_BORDER}; color: {COLOR_INVALID_TEXT}; border-radius: 4px;")
            except Exception as e:
                logger.debug("Validating EAN-13 barcode: %s", e)
        else:
            # Código personalizado (no EAN-13)
            self.barcode_preview.setText(f"Código Personalizado\n{text}")
            self.barcode_preview.setStyleSheet(f"padding: 10px; background: {COLOR_CUSTOM_BG}; border: 1px solid {COLOR_CUSTOM_BORDER}; color: {COLOR_CUSTOM_TEXT}; border-radius: 4px;")
    
    def on_generate_sku_clicked(self):
        """🪄 Genera automáticamente el siguiente SKU disponible."""
        # Deshabilitar botón y mostrar loading state
        self.btn_generate_sku.setEnabled(False)
        self.btn_generate_sku.setText("⏳ Generando...")
        QtWidgets.QApplication.processEvents()  # Forzar actualización UI
        
        try:
            # Siempre usar prefijo '20' (General) - selector oculto
            prefijo = self.default_prefix  # '20' - General
            
            # Generar SKU
            nuevo_sku = self.core.generate_next_sku(prefijo)
            
            # Actualizar UI
            self.sku_input.setText(nuevo_sku)
            
            # Mensaje de éxito
            QtWidgets.QMessageBox.information(
                self,
                "SKU Generado",
                f"{MSG_SKU_GENERATED}:\n\n{nuevo_sku}\n\nPrefijo: {prefijo} (General)\nChecksum: Válido (EAN-13)"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error al Generar SKU",
                f"{ERR_SKU_GENERATION_FAILED}:\n\n{str(e)}"
            )
        finally:
            # Restaurar botón
            self.btn_generate_sku.setEnabled(True)
            self.btn_generate_sku.setText("🪄 Generar")

    def _on_sat_code_selected(self, text):
        """Handle selection from SAT code autocomplete dropdown."""
        # text format: "50161700 - Refrescos"
        if " - " in text:
            code = text.split(" - ")[0]
            desc = text.split(" - ", 1)[1]  # Use 1 to handle descriptions with dashes
            self.sat_clave_prod_input.setText(code)
            self.sat_code_preview.setText(f"✓ {desc}")
            self.sat_code_preview.setStyleSheet("color: #28a745; font-size: 11px;")
            self._sat_descripcion = desc  # Store for saving
        else:
            self.sat_clave_prod_input.setText(text)
            self._sat_descripcion = ""
        self.sat_suggestions.setVisible(False)

    def _on_sat_suggestion_clicked(self, item):
        """Handle click on SAT suggestion list item."""
        if item:
            self._on_sat_code_selected(item.text())

    def load_data(self):
        p = self.product
        self.sku_input.setText(str(p.get("sku") or ""))
        self.name_input.setText(str(p.get("name") or ""))
        self.price_input.setValue(float(p.get("price") or 0))
        self.wholesale_input.setValue(float(p.get("price_wholesale") or 0))
        self.cost_input.setValue(float(p.get("cost") or 0))
        self.stock_input.setValue(float(p.get("stock") or 0))
        self.min_stock_input.setValue(float(p.get("min_stock") or 0))
        self.dept_input.setCurrentText(str(p.get("department") or p.get("category") or ""))
        
        st = (p.get("sale_type") or "unit").lower()
        if st == "weight" or st == "granel":
            self.type_combo.setCurrentIndex(1)
        elif st == "kit":
            self.type_combo.setCurrentIndex(2)
        else:
            self.type_combo.setCurrentIndex(0)
        
        # SAT Catalog fields
        sat_code = str(p.get("sat_clave_prod_serv") or "01010101")
        sat_desc = str(p.get("sat_descripcion") or "")
        self.sat_clave_prod_input.setText(sat_code)
        self._sat_descripcion = sat_desc
        if sat_desc:
            self.sat_code_preview.setText(f"✓ {sat_desc}")
            self.sat_code_preview.setStyleSheet("color: #28a745; font-size: 11px;")
        
        # Find matching index for ClaveUnidad
        clave_unidad = str(p.get("sat_clave_unidad") or "H87")
        for i in range(self.sat_clave_unidad_combo.count()):
            if self.sat_clave_unidad_combo.itemData(i) == clave_unidad:
                self.sat_clave_unidad_combo.setCurrentIndex(i)
                break

    def save_product(self):
        sku = self.sku_input.text().strip()
        name = self.name_input.text().strip()
        price = self.price_input.value()
        
        if not sku:
            QtWidgets.QMessageBox.warning(self, "Faltan Datos", "El Código de Barras / SKU es obligatorio.")
            self.sku_input.setFocus()
            return
            
        if not name:
            QtWidgets.QMessageBox.warning(self, "Faltan Datos", "El Nombre del producto es obligatorio.")
            self.name_input.setFocus()
            return
            
        if price <= 0:
             # Warning only, some products might be free or price set later
             res = QtWidgets.QMessageBox.question(self, "Precio Cero", "El precio de venta es $0.00. ¿Desea continuar?", 
                                                  QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
             if res == QtWidgets.QMessageBox.StandardButton.No:
                 self.price_input.setFocus()
                 return
            
        sale_type_map = {0: "unit", 1: "weight", 2: "kit"}
        sale_type = sale_type_map.get(self.type_combo.currentIndex(), "unit")
        
        # CRITICAL DEBUG: Log price when saving product
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str  # FIX: agent_log_enabled ya importado arriba
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"PRODUCT_EDITOR","location":"product_editor.py:save_product","message":"Saving product price","data":{"price":price,"sku":sku,"name":name,"is_edit":bool(self.product),"product_id":self.product.get("id") if self.product else None},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for product save: %s", e)
        # #endregion
        data = {
            "sku": sku,
            "name": name,
            "price": price,
            "price_wholesale": self.wholesale_input.value(),
            "cost": self.cost_input.value(),
            "stock": self.stock_input.value(),
            "min_stock": self.min_stock_input.value(),
            "department": self.dept_input.currentText().strip(),
            "sale_type": sale_type,
            "sat_clave_prod_serv": self.sat_clave_prod_input.text().strip() or "01010101",
            "sat_clave_unidad": self.sat_clave_unidad_combo.currentData() or "H87",
            "sat_descripcion": self._sat_descripcion or ""
        }
        
        try:
            if self.product:
                self.core.update_product(self.product["id"], data)
            else:
                self.core.create_product(data)
            self.accept()
        except Exception as e:
            err_msg = str(e)
            if "UNIQUE constraint failed" in err_msg:
                if "sku" in err_msg:
                    QtWidgets.QMessageBox.warning(self, "Código Duplicado", f"El código '{sku}' ya existe en otro producto.\nPor favor use uno diferente.")
                    self.sku_input.selectAll()
                    self.sku_input.setFocus()
                else:
                    QtWidgets.QMessageBox.warning(self, "Error de Duplicado", f"Error de restricción única: {err_msg}")
            else:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo guardar: {err_msg}")

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
    
    def _on_name_changed(self, text: str):
        """Se ejecuta cuando cambia el nombre del producto."""
        # Solo sugerir si no hay producto (modo creación) o si el nombre cambió
        if not self.product or text != self.product.get("name", ""):
            # Reiniciar timer (debounce)
            self.suggestion_timer.stop()
            if text.strip():
                self.suggestion_timer.start(500)  # Esperar 500ms después de que el usuario deje de escribir
            else:
                self._hide_suggestion()
    
    def _generate_suggestion(self):
        """Genera sugerencia de clasificación automática."""
        name = self.name_input.text().strip()
        if not name:
            self._hide_suggestion()
            return
        
        try:
            # Lazy load classifier
            if not hasattr(self, 'classifier') or self.classifier is None:
                from app.services.product_classifier import ProductClassifier
                self.classifier = ProductClassifier()
            
            # Obtener departamento actual si existe
            current_dept = None
            if self.dept_input.currentText():
                current_dept = self.dept_input.currentText()
            
            # Clasificar
            result = self.classifier.classify(name, existing_department=current_dept)
            
            # Guardar sugerencia
            self.current_suggestion = result
            
            # Mostrar sugerencia
            if result.confidence >= 0.5:
                confidence_color = "#27ae60" if result.confidence >= 0.8 else "#f39c12"
                self.auto_classify_label.setText(
                    f"💡 Sugerencia: {result.department} | "
                    f"SAT: {result.sat_clave_prod_serv} ({result.sat_clave_unidad}) | "
                    f"Confianza: <span style='color: {confidence_color}; font-weight: bold;'>{result.confidence:.0%}</span>"
                )
                self.auto_classify_label.setVisible(True)
                self.btn_auto_classify.setVisible(True)
            else:
                self.auto_classify_label.setText(
                    f"⚠️ Confianza baja ({result.confidence:.0%}). Revisar manualmente."
                )
                self.auto_classify_label.setStyleSheet("color: #e74c3c; font-size: 11px; font-style: italic;")
                self.auto_classify_label.setVisible(True)
                self.btn_auto_classify.setVisible(False)
                
        except Exception as e:
            logger.error(f"Error generando sugerencia: {e}")
            self._hide_suggestion()
    
    def _hide_suggestion(self):
        """Oculta la sugerencia automática."""
        self.auto_classify_label.setVisible(False)
        self.btn_auto_classify.setVisible(False)
        self.current_suggestion = None
    
    def _apply_auto_classification(self):
        """Aplica la clasificación automática sugerida."""
        if not self.current_suggestion:
            return
        
        result = self.current_suggestion
        
        # Aplicar departamento
        dept_index = self.dept_input.findText(result.department)
        if dept_index >= 0:
            self.dept_input.setCurrentIndex(dept_index)
        else:
            # Agregar si no existe
            self.dept_input.addItem(result.department)
            self.dept_input.setCurrentText(result.department)
        
        # Aplicar código SAT
        self.sat_clave_prod_input.setText(result.sat_clave_prod_serv)
        
        # Aplicar unidad SAT
        unidad_index = self.sat_clave_unidad_combo.findData(result.sat_clave_unidad)
        if unidad_index >= 0:
            self.sat_clave_unidad_combo.setCurrentIndex(unidad_index)
        
        # Ocultar sugerencia después de aplicar
        self._hide_suggestion()
        
        # Mostrar confirmación
        QtWidgets.QMessageBox.information(
            self,
            "Clasificación Aplicada",
            f"Se aplicó la clasificación:\n"
            f"Departamento: {result.department}\n"
            f"Código SAT: {result.sat_clave_prod_serv} ({result.sat_clave_unidad})"
        )

    def closeEvent(self, event):
        """Cleanup timers on close."""
        if hasattr(self, 'suggestion_timer') and self.suggestion_timer:
            self.suggestion_timer.stop()
        super().closeEvent(event)