"""
Settings Dialog - Unified configuration
"""
from PyQt6 import QtCore, QtWidgets


class SettingsDialog(QtWidgets.QDialog):
    """Unified settings dialog for common configurations"""
    
    def __init__(self, parent=None, core=None):
        super().__init__(parent)
        self.core = core
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the UI"""
        self.setWindowTitle("Configuración Rápida")
        self.setMinimumSize(500, 400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Tab widget
        tabs = QtWidgets.QTabWidget()
        
        # Business tab
        business_tab = self.create_business_tab()
        tabs.addTab(business_tab, "Negocio")
        
        # Printer tab
        printer_tab = self.create_printer_tab()
        tabs.addTab(printer_tab, "Impresora")
        
        # Tax tab
        tax_tab = self.create_tax_tab()
        tabs.addTab(tax_tab, "Impuestos")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_business_tab(self):
        """Create business info tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        self.business_name_edit = QtWidgets.QLineEdit()
        layout.addRow("Nombre del Negocio:", self.business_name_edit)
        
        self.rfc_edit = QtWidgets.QLineEdit()
        layout.addRow("RFC:", self.rfc_edit)
        
        self.address_edit = QtWidgets.QTextEdit()
        self.address_edit.setMaximumHeight(60)
        layout.addRow("Dirección:", self.address_edit)
        
        self.phone_edit = QtWidgets.QLineEdit()
        layout.addRow("Teléfono:", self.phone_edit)
        
        return widget
    
    def create_printer_tab(self):
        """Create printer settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        self.printer_name_edit = QtWidgets.QLineEdit()
        self.printer_name_edit.setPlaceholderText("EPSON-TM-T20")
        layout.addRow("Impresora:", self.printer_name_edit)
        
        self.print_auto_check = QtWidgets.QCheckBox("Imprimir automáticamente")
        layout.addRow("", self.print_auto_check)
        
        self.open_drawer_check = QtWidgets.QCheckBox("Abrir cajón al imprimir")
        layout.addRow("", self.open_drawer_check)
        
        return widget
    
    def create_tax_tab(self):
        """Create tax settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        self.tax_rate_spin = QtWidgets.QDoubleSpinBox()
        self.tax_rate_spin.setRange(0, 1)
        self.tax_rate_spin.setSingleStep(0.01)
        self.tax_rate_spin.setValue(0.16)
        self.tax_rate_spin.setSuffix(" (16%)")
        layout.addRow("IVA:", self.tax_rate_spin)
        
        self.include_tax_check = QtWidgets.QCheckBox("Precios incluyen IVA")
        layout.addRow("", self.include_tax_check)
        
        return widget
    
    def load_settings(self):
        """Load settings from core"""
        if not self.core:
            return
        
        # Load from config
        self.business_name_edit.setText(
            self.core.get_config('business_name', ''))
        self.rfc_edit.setText(
            self.core.get_config('business_rfc', ''))
        self.address_edit.setPlainText(
            self.core.get_config('business_address', ''))
        self.phone_edit.setText(
            self.core.get_config('business_phone', ''))
        
        self.printer_name_edit.setText(
            self.core.get_config('printer_name', 'EPSON-TM-T20'))
        self.print_auto_check.setChecked(
            self.core.get_config('print_auto', 'true') == 'true')
        self.open_drawer_check.setChecked(
            self.core.get_config('open_drawer', 'true') == 'true')
        
        tax_rate = float(self.core.get_config('tax_rate', '0.16'))
        self.tax_rate_spin.setValue(tax_rate)
        self.include_tax_check.setChecked(
            self.core.get_config('tax_included', 'false') == 'true')
    
    def save_settings(self):
        """Save settings to core"""
        if not self.core:
            self.accept()
            return
        
        # Save business info
        self.core.set_config('business_name', self.business_name_edit.text())
        self.core.set_config('business_rfc', self.rfc_edit.text())
        self.core.set_config('business_address', self.address_edit.toPlainText())
        self.core.set_config('business_phone', self.phone_edit.text())
        
        # Save printer
        self.core.set_config('printer_name', self.printer_name_edit.text())
        self.core.set_config('print_auto', 'true' if self.print_auto_check.isChecked() else 'false')
        self.core.set_config('open_drawer', 'true' if self.open_drawer_check.isChecked() else 'false')
        
        # Save tax
        self.core.set_config('tax_rate', str(self.tax_rate_spin.value()))
        self.core.set_config('tax_included', 'true' if self.include_tax_check.isChecked() else 'false')
        
        QtWidgets.QMessageBox.information(self, "Éxito", "Configuración guardada")
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
