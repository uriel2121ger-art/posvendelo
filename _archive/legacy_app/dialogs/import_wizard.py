import csv

from PyQt6 import QtCore, QtGui, QtWidgets

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

class ImportWizardDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de Importación de Productos")
        self.resize(800, 600)
        
        self.file_path = ""
        self.headers = []
        self.column_mapping = {}
        
        # Layout Principal
        layout = QtWidgets.QVBoxLayout()
        
        # --- SECCIÓN 1: SELECCIÓN DE ARCHIVO ---
        file_group = QtWidgets.QGroupBox("1. Seleccionar Archivo")
        file_layout = QtWidgets.QHBoxLayout()
        
        self.path_input = QtWidgets.QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("Selecciona un archivo CSV o Excel (.xlsx)...")
        
        btn_browse = QtWidgets.QPushButton("Examinar...")
        btn_browse.clicked.connect(self.browse_file)
        
        file_layout.addWidget(self.path_input)
        file_layout.addWidget(btn_browse)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # --- SECCIÓN 2: CONFIGURACIÓN DE LECTURA ---
        config_group = QtWidgets.QGroupBox("2. Configuración")
        config_layout = QtWidgets.QHBoxLayout()
        
        config_layout.addWidget(QtWidgets.QLabel("Fila de Encabezados:"))
        self.header_spin = QtWidgets.QSpinBox()
        self.header_spin.setRange(1, 100)
        self.header_spin.setValue(1)
        self.header_spin.valueChanged.connect(self.load_headers)
        config_layout.addWidget(self.header_spin)
        
        self.update_check = QtWidgets.QCheckBox("Actualizar productos existentes (si coincide SKU)")
        self.update_check.setChecked(True)
        config_layout.addWidget(self.update_check)
        
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        
        # --- SECCIÓN 3: MAPEO DE COLUMNAS ---
        mapping_group = QtWidgets.QGroupBox("3. Mapeo de Columnas")
        mapping_layout = QtWidgets.QVBoxLayout()
        
        self.mapping_table = QtWidgets.QTableWidget()
        self.mapping_table.setColumnCount(2)
        self.mapping_table.setHorizontalHeaderLabels(["Campo en Sistema", "Columna en Archivo"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.mapping_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        
        # Campos requeridos y opcionales
        self.required_fields = [
            ("sku", "SKU / Código (Obligatorio)"),
            ("name", "Nombre / Descripción (Obligatorio)")
        ]
        self.optional_fields = [
            ("price", "Precio Venta"),
            ("price_wholesale", "Precio Mayoreo"),
            ("cost", "Costo"),
            ("stock", "Existencia"),
            ("min_stock", "Stock Mínimo"),
            ("department", "Departamento / Categoría"),
            ("provider", "Proveedor"),
            ("barcode", "Código de Barras Alterno"),
            ("tax_rate", "Impuesto/IVA (0.16 = 16%)"),
            ("sale_type", "Tipo Venta (Unidad/Granel/Kit)"),
            ("sat_clave_prod_serv", "🏛️ Código SAT Producto/Servicio"),
            ("sat_clave_unidad", "📏 Código SAT Unidad de Medida")
        ]
        
        self.all_fields = self.required_fields + self.optional_fields
        self.mapping_table.setRowCount(len(self.all_fields))
        
        for i, (key, label) in enumerate(self.all_fields):
            item = QtWidgets.QTableWidgetItem(label)
            if key in ["sku", "name"]:
                item.setFont(QtGui.QFont("Arial", weight=QtGui.QFont.Weight.Bold))
                item.setForeground(QtGui.QColor("red"))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.mapping_table.setItem(i, 0, item)
            
            # Combo placeholder
            combo = QtWidgets.QComboBox()
            combo.addItem("--- Ignorar ---", -1)
            self.mapping_table.setCellWidget(i, 1, combo)
            
        mapping_layout.addWidget(self.mapping_table)
        mapping_group.setLayout(mapping_layout)
        layout.addWidget(mapping_group)
        
        # --- BOTONES ---
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_import = QtWidgets.QPushButton("Importar Datos")
        self.btn_import.clicked.connect(self.validate_and_accept)
        self.btn_import.setEnabled(False)
        # Style applied in show event with theme colors
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_import)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)

    def browse_file(self):
        filters = "Archivos de Datos (*.csv *.xlsx *.xls)"
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar Archivo", "", filters)
        if path:
            self.file_path = path
            self.path_input.setText(path)
            self.load_headers()

    def load_headers(self):
        if not self.file_path:
            return
            
        header_row = self.header_spin.value() - 1
        headers = []
        
        try:
            if self.file_path.endswith('.csv'):
                with open(self.file_path, mode='r', encoding='utf-8-sig', errors='replace') as f:
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        if i == header_row:
                            headers = row
                            break
            elif self.file_path.endswith(('.xlsx', '.xls')):
                if not HAS_OPENPYXL:
                    QtWidgets.QMessageBox.warning(self, "Error", "Se requiere la librería 'openpyxl' para leer Excel.")
                    return
                
                # Validar que el archivo sea realmente un Excel válido
                import zipfile
                import os
                
                # Verificar que el archivo existe y no está vacío
                if not os.path.exists(self.file_path):
                    raise FileNotFoundError(f"El archivo no existe: {self.file_path}")
                
                if os.path.getsize(self.file_path) == 0:
                    raise ValueError("El archivo está vacío")
                
                # Para .xlsx, verificar que sea un ZIP válido (los .xlsx son ZIPs)
                if self.file_path.endswith('.xlsx'):
                    try:
                        with zipfile.ZipFile(self.file_path, 'r') as zip_ref:
                            # Verificar que tenga la estructura básica de Excel
                            required_files = ['[Content_Types].xml', 'xl/workbook.xml']
                            zip_files = zip_ref.namelist()
                            if not any(f in zip_files for f in required_files):
                                raise ValueError("El archivo no parece ser un Excel válido (.xlsx)")
                    except zipfile.BadZipFile:
                        raise ValueError(
                            "El archivo está corrupto o no es un archivo Excel válido.\n\n"
                            "Posibles causas:\n"
                            "- El archivo está dañado\n"
                            "- El archivo no es realmente un .xlsx\n"
                            "- El archivo fue descargado incorrectamente\n\n"
                            "Intenta guardar el archivo nuevamente desde Excel."
                        )
                    except Exception as e:
                        if "Bad magic number" in str(e) or "BadZipFile" in str(type(e).__name__):
                            raise ValueError(
                                "El archivo Excel está corrupto o no es válido.\n\n"
                                "Error: Bad magic number for central directory\n\n"
                                "Solución: Abre el archivo en Excel y guárdalo nuevamente."
                            )
                        raise
                
                # Intentar cargar el workbook
                try:
                    wb = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
                    ws = wb.active
                    for i, row in enumerate(ws.iter_rows(values_only=True)):
                        if i == header_row:
                            headers = [str(cell) if cell is not None else "" for cell in row]
                            break
                    wb.close()
                except zipfile.BadZipFile as e:
                    raise ValueError(
                        f"El archivo Excel está corrupto: {e}\n\n"
                        "Por favor, abre el archivo en Excel y guárdalo nuevamente."
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "Bad magic number" in error_msg or "BadZipFile" in error_msg:
                        raise ValueError(
                            "El archivo Excel está corrupto o no es válido.\n\n"
                            "Error: Bad magic number for central directory\n\n"
                            "Solución:\n"
                            "1. Abre el archivo en Excel\n"
                            "2. Guarda el archivo nuevamente (Ctrl+S)\n"
                            "3. Intenta importar de nuevo"
                        )
                    raise
        except FileNotFoundError as e:
            QtWidgets.QMessageBox.critical(self, "Archivo No Encontrado", str(e))
            return
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Error de Validación", str(e))
            return
        except Exception as e:
            error_msg = str(e)
            if "Bad magic number" in error_msg or "BadZipFile" in error_msg or "corrupt" in error_msg.lower():
                QtWidgets.QMessageBox.critical(
                    self, 
                    "Archivo Corrupto", 
                    f"El archivo Excel está corrupto o no es válido.\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Solución:\n"
                    f"1. Abre el archivo en Excel\n"
                    f"2. Guarda el archivo nuevamente\n"
                    f"3. Intenta importar de nuevo"
                )
            else:
                QtWidgets.QMessageBox.critical(self, "Error de Lectura", f"No se pudo leer el archivo: {error_msg}")
            return

        self.headers = headers
        self.populate_combos()

    def populate_combos(self):
        # Llenar los comboboxes con los headers encontrados
        # Intentar auto-mapeo inteligente
        
        for row in range(self.mapping_table.rowCount()):
            combo = self.mapping_table.cellWidget(row, 1)
            if not isinstance(combo, QtWidgets.QComboBox):
                continue
                
            current_idx = combo.currentIndex()
            combo.clear()
            combo.addItem("--- Ignorar ---", -1)
            
            for i, h in enumerate(self.headers):
                combo.addItem(f"{i+1}. {h}", i)
            
            # Auto-select logic
            field_key = self.all_fields[row][0]
            best_match = -1
            
            # Simple heuristic
            for i, h in enumerate(self.headers):
                h_lower = h.lower()
                if field_key == "sku" and ("sku" in h_lower or "codigo" in h_lower or "código" in h_lower):
                    best_match = i
                    break
                if field_key == "name" and ("nombre" in h_lower or "descripcion" in h_lower or "descripción" in h_lower):
                    best_match = i
                    break
                if field_key == "price" and ("precio" in h_lower and "venta" in h_lower):
                    best_match = i
                    break
                if field_key == "price" and best_match == -1 and ("precio" in h_lower):
                    best_match = i
                if field_key == "cost" and ("costo" in h_lower):
                    best_match = i
                    break
                if field_key == "stock" and ("existencia" in h_lower or "stock" in h_lower):
                    best_match = i
                    break
                if field_key == "min_stock" and ("min" in h_lower):
                    best_match = i
                    break
                if field_key == "department" and ("depto" in h_lower or "categor" in h_lower):
                    best_match = i
                    break
                if field_key == "sat_clave_prod_serv" and ("sat" in h_lower and ("prod" in h_lower or "clave" in h_lower or "servicio" in h_lower)):
                    best_match = i
                    break
                if field_key == "sat_clave_unidad" and ("sat" in h_lower and "unidad" in h_lower):
                    best_match = i
                    break
            
            if best_match != -1:
                combo.setCurrentIndex(best_match + 1) # +1 because of "Ignorar"
            
        self.btn_import.setEnabled(True)

    def validate_and_accept(self):
        mapping = {}
        
        # Validar campos requeridos
        for i, (key, label) in enumerate(self.required_fields):
            combo = self.mapping_table.cellWidget(i, 1)
            idx = combo.currentData()
            if idx == -1 or idx is None:
                QtWidgets.QMessageBox.warning(self, "Faltan Datos", f"El campo '{label}' es obligatorio y debe ser mapeado.")
                return
            mapping[key] = idx
            
        # Campos opcionales
        for i, (key, label) in enumerate(self.optional_fields):
            row_idx = len(self.required_fields) + i
            combo = self.mapping_table.cellWidget(row_idx, 1)
            idx = combo.currentData()
            if idx != -1 and idx is None: # Should not happen but safety check
                 idx = -1
            
            if idx != -1:
                mapping[key] = idx
                
        self.column_mapping = mapping
        self.accept()

    def get_data(self):
        # path, mapping, update_existing, header_row_idx
        return (
            self.file_path,
            self.column_mapping,
            self.update_check.isChecked(),
            self.header_spin.value() - 1
        )
    
    def showEvent(self, event):
        """Apply theme colors on show"""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            self.btn_import.setStyleSheet(f"""
                background-color: {c['btn_success']};
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            """)
        except Exception:
            pass  # Fallback if theme_manager not available

