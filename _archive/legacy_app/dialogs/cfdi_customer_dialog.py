"""
CFDI Customer Dialog
Dialog for capturing customer fiscal information for invoice generation
"""

from PyQt6 import QtCore, QtWidgets


class CFDICustomerDialog(QtWidgets.QDialog):
    """Dialog to capture customer information for CFDI generation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Datos del Cliente para Factura")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._init_ui()
        self._load_defaults()
    
    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        header = QtWidgets.QLabel("Ingrese los datos fiscales del cliente:")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Form
        form_layout = QtWidgets.QFormLayout()
        form_layout.setSpacing(10)
        
        # RFC (required)
        self.rfc_input = QtWidgets.QLineEdit()
        self.rfc_input.setPlaceholderText("Ej: ABC123456789")
        self.rfc_input.setMaxLength(13)
        self.rfc_input.textChanged.connect(lambda: self.rfc_input.setText(self.rfc_input.text().upper()))
        self.rfc_input.setToolTip("RFC de 12 o 13 caracteres\n\nNota: 'XAXX010101000' solo para facturas globales")
        
        rfc_label = QtWidgets.QLabel("RFC: *")
        rfc_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow(rfc_label, self.rfc_input)
        
        # Nombre/Razón Social
        self.nombre_input = QtWidgets.QLineEdit()
        self.nombre_input.setPlaceholderText("Nombre o Razón Social")
        self.nombre_input.setToolTip("Nombre completo o razón social del cliente")
        form_layout.addRow("Nombre/Razón Social:", self.nombre_input)
        
        # Régimen Fiscal
        self.regimen_combo = QtWidgets.QComboBox()
        self.regimen_combo.addItems([
            "616 - Sin obligaciones fiscales",
            "601 - General de Ley PM",
            "603 - Personas Morales con fines no lucrativos",
            "605 - Sueldos y salarios",
            "606 - Arrendamiento",
            "612 - Personas Físicas con Actividades Empresariales",
            "620 - Coordinado",
            "621 - Incorporación Fiscal",
            "625 - Régimen de Actividades Agrícolas",
            "626 - Régimen Simplificado de Confianza (RESICO)"
        ])
        self.regimen_combo.setToolTip("Régimen fiscal del cliente")
        form_layout.addRow("Régimen Fiscal:", self.regimen_combo)
        
        # Uso CFDI
        self.uso_combo = QtWidgets.QComboBox()
        self.uso_combo.addItems([
            "G03 - Gastos en general",
            "G01 - Adquisición de mercancías",
            "G02 - Devoluciones, descuentos o bonificaciones",
            "I01 - Construcciones",
            "I02 - Mobiliario y equipo de oficina",
            "I03 - Equipo de transporte",
            "I04 - Equipo de cómputo",
            "I05 - Dados, troqueles, moldes",
            "I06 - Comunicaciones telefónicas",
            "I07 - Comunicaciones satelitales",
            "I08 - Otra maquinaria y equipo",
            "D01 - Honorarios médicos",
            "D02 - Gastos médicos por incapacidad",
            "D03 - Gastos funerales",
            "D04 - Donativos",
            "D05 - Intereses reales por préstamos hipotecarios",
            "D06 - Aportaciones voluntarias al SAR",
            "D07 - Primas por seguros de gastos médicos",
            "D08 - Gastos de transportación escolar obligatoria",
            "D09 - Depósitos en cuentas para el ahorro",
            "D10 - Pagos por servicios educativos",
            "S01 - Sin efectos fiscales",
            "CP01 - Pagos",
            "CN01 - Nómina"
        ])
        self.uso_combo.setToolTip("Uso que el cliente dará al CFDI")
        form_layout.addRow("Uso CFDI:", self.uso_combo)
        
        # Forma de Pago SAT
        self.forma_pago_combo = QtWidgets.QComboBox()
        self.forma_pago_combo.addItems([
            "01 - Efectivo",
            "02 - Cheque nominativo",
            "03 - Transferencia electrónica",
            "04 - Tarjeta de crédito",
            "28 - Tarjeta de débito",
            "99 - Por definir (solo PPD)"
        ])
        self.forma_pago_combo.setToolTip("Forma de pago según catálogo SAT")
        form_layout.addRow("Forma de Pago:", self.forma_pago_combo)
        
        # Código Postal
        self.cp_input = QtWidgets.QLineEdit()
        self.cp_input.setPlaceholderText("64000")
        self.cp_input.setMaxLength(5)
        self.cp_input.setToolTip("Código postal del domicilio fiscal del cliente")
        form_layout.addRow("Código Postal:", self.cp_input)
        
        layout.addLayout(form_layout)
        
        # Info note
        note = QtWidgets.QLabel("* Campos requeridos")
        note.setStyleSheet("color: #666; font-size: 11px; font-style: italic;")
        layout.addWidget(note)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)
        
        btn_generate = QtWidgets.QPushButton("✅ Generar Factura")
        btn_generate.setDefault(True)
        btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        btn_generate.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(btn_generate)
        
        layout.addLayout(button_layout)
    
    def _load_defaults(self):
        """Load default values."""
        self.rfc_input.setText("XAXX010101000")
        self.nombre_input.setText("PUBLICO EN GENERAL")
        self.cp_input.setText("00000")
    
    def _validate_and_accept(self):
        """Validate input before accepting."""
        rfc = self.rfc_input.text().strip()
        
        if not rfc:
            QtWidgets.QMessageBox.warning(
                self,
                "Campo requerido",
                "El RFC es obligatorio"
            )
            self.rfc_input.setFocus()
            return
        
        # CRITICAL FIX: RFC "XAXX010101000" is ONLY for global invoices
        RFC_PUBLICO_GENERAL = 'XAXX010101000'
        if rfc.upper() == RFC_PUBLICO_GENERAL:
            QtWidgets.QMessageBox.warning(
                self,
                "RFC no válido para factura individual",
                "El RFC 'XAXX010101000' (Público en General) solo puede usarse en facturas globales.\n\n"
                "Para facturas individuales, debe proporcionar el RFC del cliente.\n\n"
                "Use el Dashboard de Facturación Global en Settings → Facturación para generar facturas con este RFC."
            )
            self.rfc_input.setFocus()
            return
        
        if len(rfc) < 12 or len(rfc) > 13:
            QtWidgets.QMessageBox.warning(
                self,
                "RFC inválido",
                "El RFC debe tener 12 o 13 caracteres"
            )
            self.rfc_input.setFocus()
            return
        
        self.accept()
    
    def get_customer_data(self):
        """Get customer fiscal data from form."""
        # Extract regime code (first 3 digits)
        regimen_text = self.regimen_combo.currentText()
        regimen_code = regimen_text.split(' -')[0].strip()
        
        # Extract uso code
        uso_text = self.uso_combo.currentText()
        uso_code = uso_text.split(' -')[0].strip()
        
        # Extract forma pago code
        forma_pago_text = self.forma_pago_combo.currentText()
        forma_pago_code = forma_pago_text.split(' -')[0].strip()
        
        return {
            'rfc': self.rfc_input.text().strip().upper(),
            'nombre': self.nombre_input.text().strip() or "PUBLICO EN GENERAL",
            'regimen': regimen_code,
            'uso_cfdi': uso_code,
            'forma_pago': forma_pago_code,
            'codigo_postal': self.cp_input.text().strip() or "00000"
        }

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
