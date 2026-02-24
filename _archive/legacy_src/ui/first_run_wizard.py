import json
import os
import sys

from PyQt6 import QtCore, QtGui, QtPrintSupport, QtWidgets


class FirstRunWizard(QtWidgets.QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bienvenido a TITAN POS - Configuración Inicial")
        self.setFixedSize(600, 450)
        # Use ClassicStyle for uniform background (no separate header)
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ClassicStyle)
        
        # Import theme colors
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors("Light")  # Default to Light for setup
        except ImportError:
            # Fallback colors if theme_manager not available
            c = {
                'bg_primary': '#f5f5f5',
                'text_primary': '#333',
                'border': '#e0e0e0',
                'btn_primary': '#3498db',
                'input_bg': '#ffffff'
            }
        
        # Estilo con colores dinámicos
        self.setStyleSheet(f"""
            QWizard {{ 
                background-color: {c['bg_primary']}; 
            }}
            QWizardPage {{ 
                background-color: {c['bg_primary']}; 
            }}
            QLabel {{ 
                font-size: 14px; 
                color: {c['text_primary']}; 
            }}
            QLineEdit {{ 
                padding: 8px; 
                border: 1px solid {c['border']}; 
                border-radius: 4px; 
                font-size: 14px; 
                background: {c['input_bg']}; 
                color: {c['text_primary']}; 
            }}
            QComboBox {{ 
                padding: 8px; 
                border: 1px solid {c['border']}; 
                border-radius: 4px; 
                font-size: 14px; 
                background: {c['input_bg']}; 
                color: {c['text_primary']}; 
            }}
            QComboBox::drop-down {{ 
                border: none; 
            }}
            QComboBox QAbstractItemView {{ 
                background: {c['input_bg']}; 
                color: {c['text_primary']}; 
                selection-background-color: {c['btn_primary']}; 
            }}
            QPushButton {{ 
                padding: 8px 16px; 
                background-color: {c['btn_primary']}; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                font-weight: bold; 
            }}
            QPushButton:hover {{ 
                background-color: {c.get('accent', '#2980b9')}; 
            }}
            QPushButton:disabled {{ 
                background-color: {c['border']}; 
                color: {c.get('text_secondary', '#999')}; 
            }}
            QDateEdit {{
                padding: 8px;
                border: 1px solid {c['border']};
                border-radius: 4px;
                background: {c['input_bg']};
                color: {c['text_primary']};
            }}
            QSpinBox {{
                padding: 8px;
                border: 1px solid {c['border']};
                border-radius: 4px;
                background: {c['input_bg']};
                color: {c['text_primary']};
            }}
            QMessageBox {{
                background-color: {c['bg_primary']};
            }}
            QMessageBox QLabel {{
                color: {c['text_primary']};
                font-size: 14px;
            }}
            QMessageBox QPushButton {{
                min-width: 80px;
            }}
        """)

        # Agregar Páginas
        self.addPage(WelcomePage())
        self.addPage(BusinessInfoPage())
        self.addPage(HardwarePage())
        self.addPage(AdminUserPage())
        self.addPage(FinishPage())
        
    def accept(self):
        # Sobrescribir accept para evitar cierre prematuro si hay validaciones extra
        super().accept()

class WelcomePage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("👋 ¡Hola!")
        self.setSubTitle("Gracias por elegir TITAN POS. Vamos a configurar tu tienda en menos de 1 minuto.")
        
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("Este asistente te ayudará a:\n\n1. Ponerle nombre a tu negocio.\n2. Configurar tu impresora de tickets.\n3. Crear tu cuenta de administrador.\n\nPresiona 'Next' para comenzar.")
        label.setWordWrap(True)
        # Explicitly set text color to ensure visibility
        label.setStyleSheet("color: #333333; font-size: 14px; line-height: 1.6;")
        layout.addWidget(label)
        self.setLayout(layout)

class BusinessInfoPage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("🏢 Datos del Negocio")
        self.setSubTitle("Esta información aparecerá en tus tickets.")
        
        layout = QtWidgets.QVBoxLayout()
        
        layout.addWidget(QtWidgets.QLabel("Nombre de la Tienda:"))
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Ej. Abarrotes La Esperanza")
        self.registerField("shop_name*", self.name_input) # * = Obligatorio
        layout.addWidget(self.name_input)
        
        layout.addWidget(QtWidgets.QLabel("Dirección:"))
        self.addr_input = QtWidgets.QLineEdit()
        self.registerField("shop_address", self.addr_input)
        layout.addWidget(self.addr_input)
        
        layout.addWidget(QtWidgets.QLabel("Teléfono (Opcional):"))
        self.phone_input = QtWidgets.QLineEdit()
        self.registerField("shop_phone", self.phone_input)
        layout.addWidget(self.phone_input)
        
        layout.addWidget(QtWidgets.QLabel("RFC (Opcional):"))
        self.rfc_input = QtWidgets.QLineEdit()
        self.registerField("shop_rfc", self.rfc_input)
        layout.addWidget(self.rfc_input)
        
        self.setLayout(layout)

class HardwarePage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("🖨️ Hardware")
        self.setSubTitle("Selecciona tu impresora de tickets.")
        
        layout = QtWidgets.QVBoxLayout()
        
        layout.addWidget(QtWidgets.QLabel("Impresora Detectada:"))
        self.printer_combo = QtWidgets.QComboBox()
        
        # Detectar impresoras reales
        printers = QtPrintSupport.QPrinterInfo.availablePrinterNames()
        if not printers:
            printers = ["No se detectaron impresoras", "Guardar PDF"]
            
        self.printer_combo.addItems(printers)
        
        # Seleccionar default si existe
        default_printer = QtPrintSupport.QPrinterInfo.defaultPrinterName()
        if default_printer in printers:
            self.printer_combo.setCurrentText(default_printer)
            
        self.registerField("printer_name", self.printer_combo)
        layout.addWidget(self.printer_combo)
        
        layout.addSpacing(20)
        test_btn = QtWidgets.QPushButton("Probar Impresión")
        test_btn.clicked.connect(self.test_print)
        layout.addWidget(test_btn)
        
        self.setLayout(layout)
        
    def test_print(self):
        printer_name = self.printer_combo.currentText()
        if not printer_name or "No se detectaron" in printer_name:
            QtWidgets.QMessageBox.warning(self, "Error", "Selecciona una impresora válida primero")
            return
        
        # Real printer test using subprocess (same as printer_wizard.py)
        try:
            from datetime import datetime
            import subprocess

            # Create test ticket content
            test_content = f"""
{"=" * 40}
     TITAN POS - PRUEBA DE IMPRESORA
{"=" * 40}

Impresora: {printer_name}
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

{"*" * 40}
     PRUEBA EXITOSA
{"*" * 40}

Si puedes leer este texto,
la impresora está configurada
correctamente.

"""
            
            # Send to printer using lp command (Linux/CUPS)
            result = subprocess.run(
                ["lp", "-d", printer_name, "-o", "raw", "-"],
                input=test_content.encode('latin-1', errors='replace'),
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.decode('utf-8', errors='ignore').strip()
                QtWidgets.QMessageBox.information(
                    self, 
                    "✓ Prueba Enviada", 
                    f"Ticket enviado a: {printer_name}\n\n{output if output else 'Imprimiendo...'}\n\nVerifica la impresora."
                )
            else:
                error = result.stderr.decode('utf-8', errors='ignore').strip()
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"No se pudo imprimir:\n{error}\n\nVerifica que '{printer_name}' esté configurada en CUPS."
                )
        except subprocess.TimeoutExpired:
            QtWidgets.QMessageBox.critical(self, "Error", "Timeout: La impresora no responde")
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "Error", "Comando 'lp' no encontrado.\n¿CUPS instalado%s")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error: {str(e)}")

class AdminUserPage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("👤 Tu Cuenta")
        self.setSubTitle("Crea el usuario Administrador (Dueño).")
        
        layout = QtWidgets.QVBoxLayout()
        
        layout.addWidget(QtWidgets.QLabel("Nombre:"))
        self.admin_name = QtWidgets.QLineEdit()
        self.registerField("admin_name*", self.admin_name)
        layout.addWidget(self.admin_name)
        
        layout.addWidget(QtWidgets.QLabel("PIN de Acceso (4 dígitos):"))
        self.pin = QtWidgets.QLineEdit()
        self.pin.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.pin.setMaxLength(4)
        self.pin.setValidator(QtGui.QIntValidator())
        self.registerField("admin_pin*", self.pin)
        layout.addWidget(self.pin)
        
        self.setLayout(layout)

class FinishPage(QtWidgets.QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("🚀 ¡Todo Listo!")
        self.setSubTitle("Tu sistema está configurado.")
        
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("Presiona 'Finish' para abrir TITAN POS y empezar a vender.\n\n¡Mucho éxito!")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)

def run_wizard(config_path="config.json"):
    # Verificar si ya existe una instancia de QApplication
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)
        
    wizard = FirstRunWizard()
    if wizard.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        # Guardar Configuración
        config = {
            "shop_name": wizard.field("shop_name"),
            "shop_address": wizard.field("shop_address"),
            "shop_phone": wizard.field("shop_phone"),
            "shop_rfc": wizard.field("shop_rfc"),
            "printer": wizard.field("printer_name"),
            "admin_name": wizard.field("admin_name"),
            "admin_pin": wizard.field("admin_pin"),
            "setup_complete": True,
            "theme": "Light"
        }
        
        # Asegurar que el directorio existe
        try:
            os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        except OSError:
            pass
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
            
        return True
    return False

if __name__ == "__main__":
    run_wizard()
