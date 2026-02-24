"""
Setup Wizard for Initial Configuration
"""
import platform
import subprocess

from PyQt6 import QtCore, QtWidgets


class SetupWizard(QtWidgets.QWizard):
    """Initial setup wizard for first-time configuration"""
    
    def __init__(self, parent=None, core=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Asistente de Configuración Inicial")
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ModernStyle)
        
        # Add pages
        self.addPage(WelcomePage())
        self.addPage(BusinessInfoPage())
        self.addPage(BranchSetupPage())  # NEW: Configuración de sucursal
        self.addPage(PrinterSetupPage())
        self.addPage(UserSetupPage(core=self.core))
        self.addPage(CompletionPage(core=self.core))
        
        self.resize(600, 500)
        self._apply_theme()
    
    def showEvent(self, event):
        """Apply theme when shown."""
        super().showEvent(event)
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply current theme colors."""
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            self.setStyleSheet(f"""
                QWizard {{
                    background: {c['bg_secondary']};
                }}
                QWizardPage {{
                    background: {c['bg_primary']};
                }}
                QLabel {{
                    color: {c['text_primary']};
                }}
                QLineEdit, QTextEdit, QComboBox {{
                    background: {c['bg_secondary']};
                    color: {c['text_primary']};
                    border: 1px solid {c['border']};
                    padding: 8px;
                    border-radius: 4px;
                }}
                QPushButton {{
                    background: {c['btn_primary']};
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {c['btn_success']};
                }}
            """)
        except Exception:
            pass

class WelcomePage(QtWidgets.QWizardPage):
    """Welcome page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Bienvenido a TITAN POS")
        self.setSubTitle("Configuración inicial del sistema")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        logo_label = QtWidgets.QLabel("🚀 TITAN POS")
        logo_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)
        
        info = QtWidgets.QLabel(
            "\nEste asistente te ayudará a configurar:\n\n"
            "• Información de tu negocio\n"
            "• Impresoras y dispositivos\n"
            "• Usuario administrador\n\n"
            "El proceso tomará solo unos minutos."
        )
        info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        layout.addStretch()

class BusinessInfoPage(QtWidgets.QWizardPage):
    """Business information page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Información del Negocio")
        self.setSubTitle("Datos que aparecerán en tickets y facturas")
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        
        # Nombre comercial
        self.business_name_edit = QtWidgets.QLineEdit()
        self.business_name_edit.setPlaceholderText("Mi Tienda")
        form.addRow("Nombre Comercial:*", self.business_name_edit)
        
        # Razón Social (fiscal)
        self.razon_social_edit = QtWidgets.QLineEdit()
        self.razon_social_edit.setPlaceholderText("EMPRESA SA DE CV (si es diferente)")
        form.addRow("Razón Social:", self.razon_social_edit)
        
        # RFC
        self.rfc_edit = QtWidgets.QLineEdit()
        self.rfc_edit.setPlaceholderText("XAXX010101000")
        self.rfc_edit.setMaxLength(13)
        form.addRow("RFC:*", self.rfc_edit)
        
        # Dirección
        self.address_edit = QtWidgets.QTextEdit()
        self.address_edit.setMaximumHeight(60)
        self.address_edit.setPlaceholderText("Calle, Colonia, CP, Ciudad")
        form.addRow("Dirección:", self.address_edit)
        
        # Teléfono
        self.phone_edit = QtWidgets.QLineEdit()
        self.phone_edit.setPlaceholderText("555-1234567")
        form.addRow("Teléfono:", self.phone_edit)
        
        layout.addLayout(form)
        
        # Nota informativa
        note = QtWidgets.QLabel(
            "💡 El Nombre Comercial aparece en los tickets. "
            "La Razón Social es para fines fiscales (CFDI)."
        )
        note.setStyleSheet("color: #888; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        layout.addStretch()
        
        self.registerField("business_name*", self.business_name_edit)
        self.registerField("razon_social", self.razon_social_edit)
        self.registerField("business_rfc*", self.rfc_edit)
        self.registerField("business_address", self.address_edit, "plainText")
        self.registerField("business_phone", self.phone_edit)

class BranchSetupPage(QtWidgets.QWizardPage):
    """Branch and terminal setup page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Configuración de Sucursal")
        self.setSubTitle("Identifica esta terminal en la red de sucursales")
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        
        # Branch ID
        self.branch_id_spin = QtWidgets.QSpinBox()
        self.branch_id_spin.setRange(1, 999)
        self.branch_id_spin.setValue(1)
        self.branch_id_spin.setToolTip("1 = Matriz, 2+ = Sucursales")
        form.addRow("ID de Sucursal:", self.branch_id_spin)
        
        # Branch Name
        self.branch_name_edit = QtWidgets.QLineEdit()
        self.branch_name_edit.setPlaceholderText("ej: Sucursal Centro")
        self.branch_name_edit.setText("Sucursal Principal")
        form.addRow("Nombre Sucursal:", self.branch_name_edit)
        
        # Terminal ID
        self.terminal_id_spin = QtWidgets.QSpinBox()
        self.terminal_id_spin.setRange(1, 99)
        self.terminal_id_spin.setValue(1)
        self.terminal_id_spin.setToolTip("Número de caja dentro de la sucursal")
        form.addRow("Número de Caja:", self.terminal_id_spin)
        
        layout.addLayout(form)
        
        # Info
        info_label = QtWidgets.QLabel(
            "\n💡 Si tienes múltiples sucursales:\n"
            "- Cada sucursal tiene un ID único (1, 2, 3...)\n"
            "- Cada caja tiene un número dentro de la sucursal\n"
            "- Esto permite identificar ventas y reportes por ubicación"
        )
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        self.registerField("branch_id", self.branch_id_spin)
        self.registerField("branch_name", self.branch_name_edit)
        self.registerField("terminal_id", self.terminal_id_spin)

class PrinterSetupPage(QtWidgets.QWizardPage):
    """Printer setup page"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Configuración de Impresora")
        self.setSubTitle("Configura tu impresora de tickets")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        form = QtWidgets.QFormLayout()
        
        # Printer combo with detection
        printer_layout = QtWidgets.QHBoxLayout()
        self.printer_combo = QtWidgets.QComboBox()
        self.printer_combo.setMinimumWidth(250)
        printer_layout.addWidget(self.printer_combo)
        
        refresh_btn = QtWidgets.QPushButton("🔄")
        refresh_btn.setMaximumWidth(40)
        refresh_btn.setToolTip("Detectar impresoras")
        refresh_btn.clicked.connect(self._detect_printers)
        printer_layout.addWidget(refresh_btn)
        
        form.addRow("Impresora:", printer_layout)
        
        # Manual entry
        self.manual_entry = QtWidgets.QLineEdit()
        self.manual_entry.setPlaceholderText("O escribe el nombre manualmente...")
        form.addRow("Manual:", self.manual_entry)
        
        self.auto_print_check = QtWidgets.QCheckBox("Imprimir automáticamente después de vender")
        form.addRow("", self.auto_print_check)
        
        self.open_drawer_check = QtWidgets.QCheckBox("Abrir cajón al imprimir")
        self.open_drawer_check.setChecked(True)
        form.addRow("", self.open_drawer_check)
        
        layout.addLayout(form)
        
        # Test button
        test_btn = QtWidgets.QPushButton("🖨️ Imprimir Prueba")
        test_btn.clicked.connect(self.print_test)
        layout.addWidget(test_btn)
        
        layout.addStretch()
        
        self.registerField("printer_name", self.printer_combo, "currentText")
        self.registerField("auto_print", self.auto_print_check)
        self.registerField("open_drawer", self.open_drawer_check)
        
        # Detect printers on init
        self._detect_printers()
    
    def _detect_printers(self):
        """Detect installed CUPS printers."""
        self.printer_combo.clear()
        printers = []
        
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["lpstat", "-a"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split()
                            if parts:
                                printers.append(parts[0])
        except Exception:
            pass
        
        if printers:
            self.printer_combo.addItems(printers)
        else:
            self.printer_combo.addItems([
                "No se detectaron impresoras",
                "Ingresa el nombre manualmente"
            ])

    def print_test(self):
        """Print test page using CUPS"""
        from app.utils import ticket_engine
        
        printer_name = self.printer_combo.currentText()
        
        if printer_name == "Ninguna (configurar después)":
            QtWidgets.QMessageBox.warning(
                self, "Impresora", 
                "Selecciona una impresora para hacer la prueba."
            )
            return
        
        try:
            ticket_engine.print_test_ticket(printer_name)
            QtWidgets.QMessageBox.information(
                self, "Prueba", 
                f"Ticket de prueba enviado a '{printer_name}'.\n"
                "Verifica que la impresora lo haya recibido."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", 
                f"Error al imprimir: {e}"
            )

class UserSetupPage(QtWidgets.QWizardPage):
    """User setup page"""
    
    def __init__(self, core=None):
        super().__init__()
        self.core = core
        self.setTitle("Usuario Administrador")
        self.setSubTitle("Crea tu usuario administrador")
        
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        
        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setPlaceholderText("admin")
        form.addRow("Usuario:*", self.username_edit)
        
        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        form.addRow("Contraseña:*", self.password_edit)
        
        self.password_confirm_edit = QtWidgets.QLineEdit()
        self.password_confirm_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        form.addRow("Confirmar:*", self.password_confirm_edit)
        
        layout.addLayout(form)
        layout.addStretch()
        
        self.registerField("admin_username*", self.username_edit)
        self.registerField("admin_password*", self.password_edit)
        self.registerField("admin_password_confirm*", self.password_confirm_edit)
    
    def validatePage(self):
        """Validate passwords match"""
        if self.password_edit.text() != self.password_confirm_edit.text():
            QtWidgets.QMessageBox.warning(
                self, "Error", "Las contraseñas no coinciden"
            )
            return False
        if len(self.password_edit.text()) < 4:
            QtWidgets.QMessageBox.warning(
                self, "Error", "La contraseña debe tener al menos 4 caracteres"
            )
            return False
        return True

class CompletionPage(QtWidgets.QWizardPage):
    """Completion page"""
    
    def __init__(self, core=None):
        super().__init__()
        self.core = core
        self.setTitle("¡Configuración Completa!")
        self.setSubTitle("TITAN POS está listo para usar")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        success = QtWidgets.QLabel("✅ Configuración completada exitosamente")
        success.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        success.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(success)
        
        info = QtWidgets.QLabel(
            "\nYa puedes comenzar a usar TITAN POS:\n\n"
            "• Abre un turno\n"
            "• Realiza tu primera venta\n"
            "• Explora todas las funciones\n\n"
            "¡Éxito!"
        )
        info.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        layout.addStretch()
        
        self.setFinalPage(True)
    
    def initializePage(self):
        """Save configuration and create admin user"""
        if not self.core:
            return
        
        try:
            # Save business info
            self.core.set_config('business_name', self.field("business_name") or '')
            self.core.set_config('business_razon_social', self.field("razon_social") or '')
            self.core.set_config('business_rfc', self.field("business_rfc") or '')
            self.core.set_config('business_address', self.field("business_address") or '')
            self.core.set_config('business_phone', self.field("business_phone") or '')
            
            # Save printer config
            printer_name = self.field("printer_name") or ''
            self.core.set_config('printer_name', printer_name)
            self.core.set_config('auto_print', str(self.field("auto_print")))
            self.core.set_config('open_drawer', str(self.field("open_drawer")))
            
            # Create admin user
            admin_username = self.field("admin_username")
            admin_password = self.field("admin_password")
            
            if admin_username and admin_password:
                try:
                    # Check if user already exists
                    existing = self.core.db.execute_query(
                        "SELECT id FROM users WHERE username = %s", 
                        (admin_username,)
                    )
                    if not existing:
                        self.core.create_user({
                            'username': admin_username,
                            'password': admin_password,
                            'role': 'admin',
                            'name': 'Administrador',
                            'is_active': 1
                        })
                except Exception as e:
                    print(f"Error creating admin user: {e}")
            
            # Save to config.json too
            cfg = self.core.read_local_config()
            cfg['store_name'] = self.field("business_name") or ''
            cfg['store_razon_social'] = self.field("razon_social") or ''
            cfg['store_rfc'] = self.field("business_rfc") or ''
            cfg['store_address'] = self.field("business_address") or ''
            cfg['store_phone'] = self.field("business_phone") or ''
            cfg['printer_name'] = printer_name
            
            # Save branch configuration
            cfg['branch_id'] = self.field("branch_id") or 1
            cfg['branch_name'] = self.field("branch_name") or 'Sucursal Principal'
            cfg['terminal_id'] = self.field("terminal_id") or 1
            
            cfg['setup_complete'] = True
            cfg['setup_completed'] = True  # Ambos por compatibilidad
            self.core.write_local_config(cfg)
            
            # Mark setup complete in DB
            self.core.set_config('setup_complete', 'true')
            
        except Exception as e:
            print(f"Error saving setup configuration: {e}")
