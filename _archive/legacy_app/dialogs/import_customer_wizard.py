import csv

from PyQt6 import QtCore, QtGui, QtWidgets

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

class ImportCustomerWizardDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de Importación de Clientes")
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
        
        self.update_check = QtWidgets.QCheckBox("Actualizar clientes existentes (basado en RFC/Nombre)")
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
        
        # Campos de Cliente - COMPLETOS para coincidir con exportación
        self.required_fields = [
            ("full_name", "Nombre Completo (Obligatorio)")
        ]
        self.optional_fields = [
            ("first_name", "Nombre"),
            ("last_name", "Apellido"),
            ("phone", "Teléfono"),
            ("email", "Email"),
            ("email_fiscal", "Email Fiscal"),
            ("rfc", "RFC"),
            ("razon_social", "Razón Social"),
            ("regimen_fiscal", "Régimen Fiscal"),
            ("domicilio1", "Domicilio 1"),
            ("domicilio2", "Domicilio 2"),
            ("colonia", "Colonia"),
            ("municipio", "Municipio"),
            ("estado", "Estado"),
            ("pais", "País"),
            ("codigo_postal", "Código Postal"),
            ("vip", "VIP"),
            ("credit_authorized", "Crédito Autorizado"),
            ("credit_limit", "Límite de Crédito"),
            ("credit_balance", "Saldo de Crédito"),
            ("points", "Puntos"),
            ("wallet_balance", "Saldo Monedero"),
            ("notes", "Notas")
        ]
        
        self.all_fields = self.required_fields + self.optional_fields
        self.mapping_table.setRowCount(len(self.all_fields))
        
        for i, (key, label) in enumerate(self.all_fields):
            item = QtWidgets.QTableWidgetItem(label)
            if key in ["full_name"]:
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
        btn_layout = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_import = QtWidgets.QPushButton("Importar Clientes")
        self.btn_import.clicked.connect(self.accept)
        self.btn_import.setEnabled(False)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_import)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def browse_file(self):
        filters = "Archivos CSV/Excel (*.csv *.xlsx)"
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Seleccionar Archivo", "", filters)
        if path:
            self.file_path = path
            self.path_input.setText(path)
            self.load_headers()
            
    def load_headers(self):
        if not self.file_path:
            return
            
        row_idx = self.header_spin.value() - 1
        headers = []
        
        try:
            if self.file_path.lower().endswith('.xlsx'):
                if not HAS_OPENPYXL:
                    QtWidgets.QMessageBox.warning(self, "Error", "Se requiere la librería 'openpyxl' para leer Excel.")
                    return
                
                # Validar archivo antes de leer
                import zipfile
                import os
                
                if not os.path.exists(self.file_path):
                    raise FileNotFoundError(f"El archivo no existe: {self.file_path}")
                
                if os.path.getsize(self.file_path) == 0:
                    raise ValueError("El archivo está vacío")
                
                # Validar que .xlsx sea un ZIP válido
                try:
                    with zipfile.ZipFile(self.file_path, 'r') as zip_ref:
                        zip_files = zip_ref.namelist()
                        if not any('xl/workbook.xml' in f or '[Content_Types].xml' in f for f in zip_files):
                            raise ValueError("El archivo no parece ser un Excel válido")
                except zipfile.BadZipFile:
                    raise ValueError(
                        "El archivo Excel está corrupto o no es válido.\n\n"
                        "Error: Bad magic number for central directory\n\n"
                        "Solución:\n"
                        "1. Abre el archivo en Excel\n"
                        "2. Guarda el archivo nuevamente (Ctrl+S)\n"
                        "3. Intenta importar de nuevo"
                    )
                
                try:
                    wb = openpyxl.load_workbook(self.file_path, read_only=True, data_only=True)
                    ws = wb.active
                    # Leer solo la fila de encabezados
                    for i, row in enumerate(ws.iter_rows(values_only=True)):
                        if i == row_idx:
                            headers = [str(cell) if cell is not None else f"Columna {j+1}" for j, cell in enumerate(row)]
                            break
                    wb.close()
                except zipfile.BadZipFile:
                    raise ValueError(
                        "El archivo Excel está corrupto.\n\n"
                        "Por favor, abre el archivo en Excel y guárdalo nuevamente."
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "Bad magic number" in error_msg or "BadZipFile" in error_msg:
                        raise ValueError(
                            "El archivo Excel está corrupto o no es válido.\n\n"
                            "Solución: Abre el archivo en Excel y guárdalo nuevamente."
                        )
                    raise
            else:
                # CSV
                encodings = ['utf-8-sig', 'utf-8', 'latin-1']
                content = None
                for encoding in encodings:
                    try:
                        with open(self.file_path, 'r', encoding=encoding) as f:
                            content = f.readlines()
                        break
                    except UnicodeDecodeError:
                        continue
                
                if content and len(content) > row_idx:
                    line = content[row_idx].strip()
                    if ';' in line and line.count(';') > line.count(','):
                        headers = line.split(';')
                    else:
                        headers = line.split(',')
                        
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
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo leer el archivo: {error_msg}")
            return
            
        self.headers = [h.strip() for h in headers]
        self._update_combos()
        
    def _update_combos(self):
        for i in range(self.mapping_table.rowCount()):
            combo = self.mapping_table.cellWidget(i, 1)
            current_idx = combo.currentIndex()
            combo.clear()
            combo.addItem("--- Ignorar ---", -1)
            
            # Agregar headers detectados
            for col_idx, h in enumerate(self.headers):
                combo.addItem(f"{col_idx+1}. {h}", col_idx)
                
            # Auto-match inteligente
            field_key = self.all_fields[i][0]
            best_match = -1
            
            # Diccionario de sinónimos - COMPLETO
            synonyms = {
                "full_name": ["nombre completo", "nombre", "cliente", "name", "full name"],
                "first_name": ["nombre", "first name", "primer nombre"],
                "last_name": ["apellido", "last name", "apellidos"],
                "rfc": ["rfc", "tax id", "nit"],
                "email": ["email", "correo", "e-mail", "mail"],
                "email_fiscal": ["email fiscal", "correo fiscal", "e-mail fiscal"],
                "phone": ["telefono", "teléfono", "celular", "phone", "movil", "móvil"],
                "credit_limit": ["limite", "límite de crédito", "credit limit", "credito"],
                "credit_balance": ["saldo de crédito", "saldo credito", "adeudo", "deuda"],
                "credit_authorized": ["crédito autorizado", "credito autorizado", "autorizado"],
                "razon_social": ["razón social", "razon social", "empresa", "company"],
                "regimen_fiscal": ["regimen", "régimen", "fiscal", "regimen fiscal"],
                "domicilio1": ["direccion", "dirección", "calle", "domicilio 1", "address"],
                "domicilio2": ["domicilio 2", "direccion 2", "dirección 2"],
                "colonia": ["colonia", "col", "neighborhood"],
                "municipio": ["municipio", "ciudad", "city"],
                "estado": ["estado", "state", "provincia"],
                "pais": ["país", "pais", "country"],
                "codigo_postal": ["cp", "c.p.", "zip", "postal", "código postal", "codigo postal"],
                "vip": ["vip", "cliente vip", "preferente"],
                "points": ["puntos", "points", "loyalty"],
                "wallet_balance": ["saldo monedero", "monedero", "wallet", "cashback"],
                "notes": ["notas", "comentarios", "observaciones", "notes"]
            }
            
            candidates = synonyms.get(field_key, [])
            
            for col_idx, h in enumerate(self.headers):
                h_lower = h.lower()
                if h_lower == field_key:
                    best_match = col_idx
                    break
                for syn in candidates:
                    if syn in h_lower:
                        best_match = col_idx
                        break
                if best_match != -1:
                    break
            
            if best_match != -1:
                combo.setCurrentIndex(best_match + 1) # +1 por el item "Ignorar"
            elif current_idx > 0 and current_idx < combo.count():
                combo.setCurrentIndex(current_idx) # Mantener selección previa si es válida
                
        self.btn_import.setEnabled(True)

    def get_data(self):
        """Retorna (file_path, mapping_dict, update_existing, header_row_idx)"""
        mapping = {}
        for i in range(self.mapping_table.rowCount()):
            combo = self.mapping_table.cellWidget(i, 1)
            col_idx = combo.currentData()
            if col_idx != -1:
                field_key = self.all_fields[i][0]
                mapping[field_key] = col_idx
                
        return self.file_path, mapping, self.update_check.isChecked(), self.header_spin.value() - 1

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
