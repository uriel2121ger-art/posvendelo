from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import platform
import subprocess

from PyQt6 import QtCore, QtGui, QtWidgets

from app.utils import ticket_engine
from app.utils.theme_manager import theme_manager


class PrinterWizardDialog(QtWidgets.QDialog):
    """
    Multi-step wizard for printer configuration.
    Steps: Detection -> Test -> Paper Width -> Cash Drawer -> Summary
    """

    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.cfg = self.core.get_app_config() or {}
        
        # Initialize with defaults first
        self.selected_printer = ""
        self.paper_width = "80mm"
        self.drawer_enabled = False
        self.drawer_sequence = "\\x1B\\x70\\x00\\x19\\xFA"
        
        # Load current settings BEFORE creating UI
        # This way the widgets will be created with correct values
        self._load_current_settings()
        
        self.setWindowTitle("Asistente de Configuración de Impresora")
        self.setMinimumSize(600, 450)
        self.setModal(True)
        
        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("🖨️ Configuración de Impresora de Tickets")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Stacked widget for steps
        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._create_step1_detection())
        self.stack.addWidget(self._create_step2_test())
        self.stack.addWidget(self._create_step3_paper())
        self.stack.addWidget(self._create_step4_drawer())
        self.stack.addWidget(self._create_step5_summary())
        layout.addWidget(self.stack)
        
        # Navigation buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_back = QtWidgets.QPushButton("← Atrás")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_back.setEnabled(False)
        
        self.btn_next = QtWidgets.QPushButton("Siguiente →")
        self.btn_next.clicked.connect(self._go_next)
        
        self.btn_finish = QtWidgets.QPushButton("✓ Finalizar")
        self.btn_finish.clicked.connect(self._finish)
        self.btn_finish.setVisible(False)
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_next)
        btn_layout.addWidget(self.btn_finish)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _create_step1_detection(self):
        """Step 1: Printer detection"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        lbl = QtWidgets.QLabel("Paso 1/5: Selección de Impresora")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        info = QtWidgets.QLabel(
            "Selecciona la impresora de tickets instalada en tu sistema.\n"
            "Si no aparece, asegúrate de instalarla primero en tu sistema operativo."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Printer list
        list_layout = QtWidgets.QHBoxLayout()
        self.printer_list = QtWidgets.QListWidget()
        self.printer_list.itemClicked.connect(self._on_printer_selected)
        list_layout.addWidget(self.printer_list)
        
        # Refresh button
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar\nLista")
        btn_refresh.clicked.connect(self._detect_printers)
        btn_refresh.setFixedWidth(100)
        list_layout.addWidget(btn_refresh)
        
        layout.addLayout(list_layout)
        
        # Manual entry
        manual_layout = QtWidgets.QHBoxLayout()
        manual_layout.addWidget(QtWidgets.QLabel("O ingresa manualmente:"))
        self.manual_printer = QtWidgets.QLineEdit()
        self.manual_printer.setPlaceholderText("Nombre de impresora")
        self.manual_printer.textChanged.connect(lambda: self._on_manual_entry())
        manual_layout.addWidget(self.manual_printer)
        layout.addLayout(manual_layout)
        
        layout.addStretch()
        
        # Auto-detect on creation
        QtCore.QTimer.singleShot(100, self._detect_printers)
        
        return widget

    def _create_step2_test(self):
        """Step 2: Test printing"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        lbl = QtWidgets.QLabel("Paso 2/5: Prueba de Comunicación")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        self.test_status = QtWidgets.QLabel(
            f"Impresora seleccionada: <b>{self.selected_printer or 'Ninguna'}</b>\n\n"
            "Envía una prueba de impresión para verificar la comunicación."
        )
        self.test_status.setWordWrap(True)
        layout.addWidget(self.test_status)
        
        btn_test = QtWidgets.QPushButton("📄 Enviar Ticket de Prueba")
        btn_test.clicked.connect(self._send_test_print)
        btn_test.setStyleSheet("padding: 10px; font-weight: bold;")
        layout.addWidget(btn_test)
        
        self.test_result = QtWidgets.QLabel("")
        self.test_result.setWordWrap(True)
        layout.addWidget(self.test_result)
        
        layout.addStretch()
        return widget

    def _create_step3_paper(self):
        """Step 3: Paper width"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        lbl = QtWidgets.QLabel("Paso 3/5: Ancho del Papel")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        info = QtWidgets.QLabel(
            "Selecciona el ancho del papel de tu impresora térmica.\n"
            "Esto afecta el formato y tamaño de los tickets."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Radio buttons with visual cards
        self.radio_58 = QtWidgets.QRadioButton()
        self.radio_80 = QtWidgets.QRadioButton()
        
        # Create button group to make radio buttons mutually exclusive
        self.paper_group = QtWidgets.QButtonGroup()
        self.paper_group.addButton(self.radio_58)
        self.paper_group.addButton(self.radio_80)
        
        card_layout = QtWidgets.QHBoxLayout()
        
        # 58mm card
        card_58 = self._create_paper_card("58mm", "Papel angosto\nIdeal para tickets compactos", self.radio_58)
        card_layout.addWidget(card_58)
        
        # 80mm card
        card_80 = self._create_paper_card("80mm", "Papel estándar\nMayor espacio para información", self.radio_80)
        card_layout.addWidget(card_80)
        
        layout.addLayout(card_layout)
        
        # Auto-print option
        layout.addSpacing(20)
        self.auto_print_check = QtWidgets.QCheckBox("Imprimir automáticamente al cobrar")
        self.auto_print_check.setChecked(self.cfg.get("auto_print_tickets", False))
        layout.addWidget(self.auto_print_check)
        
        layout.addStretch()
        
        # Default selection
        if self.paper_width == "58mm":
            self.radio_58.setChecked(True)
        else:
            self.radio_80.setChecked(True)
        
        return widget

    def _create_step4_drawer(self):
        """Step 4: Cash drawer"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        lbl = QtWidgets.QLabel("Paso 4/5: Cajón de Dinero")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        info = QtWidgets.QLabel(
            "Si tienes un cajón de dinero conectado a la impresora,\n"
            "configúralo aquí para abrirlo automáticamente al cobrar."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        self.drawer_check = QtWidgets.QCheckBox("Tengo cajón de dinero conectado")
        self.drawer_check.setChecked(self.drawer_enabled)
        self.drawer_check.toggled.connect(self._on_drawer_toggled)
        layout.addWidget(self.drawer_check)
        
        # Drawer settings (initially hidden if disabled)
        self.drawer_group = QtWidgets.QGroupBox("Configuración del Cajón")
        drawer_layout = QtWidgets.QFormLayout(self.drawer_group)
        
        self.drawer_seq_input = QtWidgets.QLineEdit(self.drawer_sequence)
        self.drawer_seq_input.setPlaceholderText("\\x1B\\x70\\x00\\x19\\xFA")
        drawer_layout.addRow("Secuencia de pulso:", self.drawer_seq_input)
        
        drawer_info = QtWidgets.QLabel(
            "<small>La secuencia por defecto funciona con la mayoría de cajones.\n"
            "Solo modifica si sabes lo que haces.</small>"
        )
        drawer_info.setWordWrap(True)
        drawer_layout.addRow("", drawer_info)
        
        btn_test_drawer = QtWidgets.QPushButton("🔓 Probar Apertura del Cajón")
        btn_test_drawer.clicked.connect(self._test_drawer_open)
        drawer_layout.addRow("", btn_test_drawer)
        
        self.drawer_test_result = QtWidgets.QLabel("")
        drawer_layout.addRow("", self.drawer_test_result)
        
        layout.addWidget(self.drawer_group)
        self.drawer_group.setVisible(self.drawer_enabled)
        
        layout.addStretch()
        return widget

    def _create_step5_summary(self):
        """Step 5: Summary and confirmation"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        lbl = QtWidgets.QLabel("Paso 5/5: Resumen de Configuración")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        info = QtWidgets.QLabel("Revisa la configuración antes de guardar:")
        layout.addWidget(info)
        
        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(250)
        layout.addWidget(self.summary_text)
        
        success = QtWidgets.QLabel(
            "✓ Al hacer clic en <b>Finalizar</b>, la configuración se guardará\n"
            "  y estará lista para usar en el punto de venta."
        )
        success.setStyleSheet("color: #27ae60; margin-top: 10px;")
        success.setWordWrap(True)
        layout.addWidget(success)
        
        layout.addStretch()
        return widget

    def _create_paper_card(self, size, description, radio_button):
        """Create a visual card for paper size selection"""
        card = QtWidgets.QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
            }
            QWidget:hover {
                border-color: #3498db;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        
        # Radio button and title
        header = QtWidgets.QHBoxLayout()
        header.addWidget(radio_button)
        
        title_lbl = QtWidgets.QLabel(f"<b>{size}</b>")
        title_lbl.setStyleSheet("font-size: 16px;")
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)
        
        # Description
        desc_lbl = QtWidgets.QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #6c757d; margin-top: 5px;")
        layout.addWidget(desc_lbl)
        
        # Make card clickable
        card.mousePressEvent = lambda e: radio_button.setChecked(True)
        
        return card

    def _load_current_settings(self):
        """Load current settings from config"""
        self.selected_printer = self.cfg.get("printer_name", "")
        self.paper_width = self.cfg.get("ticket_paper_width", "80mm")
        self.drawer_enabled = self.cfg.get("cash_drawer_enabled", False)
        self.drawer_sequence = self.cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")

    def _detect_printers(self):
        """Auto-detect installed printers"""
        self.printer_list.clear()
        
        printers = []
        system = platform.system()
        
        try:
            if system == "Linux":
                # Try multiple methods to detect printers
                # Method 1: lpstat -a (most reliable)
                try:
                    result = subprocess.run(
                        ["lpstat", "-a"], 
                        capture_output=True, 
                        text=True, 
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        for line in result.stdout.split("\n"):
                            line = line.strip()
                            if line:
                                # Format: "PRINTER_NAME accepting/aceptando ..."
                                # Just take the first word which is always the printer name
                                parts = line.split()
                                if parts:
                                    printer_name = parts[0]
                                    if printer_name not in printers:
                                        printers.append(printer_name)
                except Exception:
                    pass
                
                # Method 2: lpstat -p (fallback)
                if not printers:
                    try:
                        result = subprocess.run(
                            ["lpstat", "-p"], 
                            capture_output=True, 
                            text=True, 
                            timeout=5
                        )
                        if result.returncode == 0:
                            for line in result.stdout.split("\n"):
                                line = line.strip()
                                # Handle both English "printer" and Spanish "la impresora"
                                if line.startswith("printer") or line.startswith("la impresora"):
                                    parts = line.split()
                                    if len(parts) >= 2:
                                        # English: "printer NAME ..."
                                        # Spanish: "la impresora NAME ..."
                                        idx = 2 if line.startswith("la impresora") else 1
                                        if len(parts) > idx:
                                            printer_name = parts[idx]
                                            if printer_name not in printers:
                                                printers.append(printer_name)
                    except Exception:
                        pass
                
                # Method 3: lpstat -v (last resort)
                if not printers:
                    try:
                        result = subprocess.run(
                            ["lpstat", "-v"], 
                            capture_output=True, 
                            text=True, 
                            timeout=5
                        )
                        if result.returncode == 0:
                            for line in result.stdout.split("\n"):
                                line = line.strip()
                                # Format: "device for PRINTER_NAME: ..."
                                # or "dispositivo para PRINTER_NAME: ..."
                                if "device for" in line or "dispositivo para" in line:
                                    parts = line.split(":")
                                    if parts:
                                        # Extract printer name between "for/para" and ":"
                                        name_part = parts[0]
                                        if "device for" in name_part:
                                            printer_name = name_part.split("device for")[1].strip()
                                        elif "dispositivo para" in name_part:
                                            printer_name = name_part.split("dispositivo para")[1].strip()
                                        else:
                                            continue
                                        if printer_name and printer_name not in printers:
                                            printers.append(printer_name)
                    except Exception:
                        pass
                        
            elif system == "Windows":
                # Use wmic
                result = subprocess.run(
                    ["wmic", "printer", "get", "name"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    printers = [line.strip() for line in lines[1:] if line.strip()]
        except Exception as e:
            logging.getLogger(__name__).warning(f"Could not detect printers: {e}")
        
        if printers:
            for printer in printers:
                self.printer_list.addItem(printer)
            self.printer_list.addItem("─────────────────")
            self.printer_list.addItem("💡 No encuentras tu impresora?")
            self.printer_list.addItem("   Ingrésala manualmente abajo")
        else:
            self.printer_list.addItem("❌ No se detectaron impresoras")
            self.printer_list.addItem("")
            self.printer_list.addItem("Ingresa el nombre manualmente")

    def _on_printer_selected(self, item):
        """Handle printer selection from list"""
        text = item.text()
        if not text.startswith("─") and not text.startswith("💡") and not text.startswith("❌"):
            self.selected_printer = text.strip()
            self.manual_printer.clear()

    def _on_manual_entry(self):
        """Handle manual printer name entry"""
        if self.manual_printer.text().strip():
            self.selected_printer = self.manual_printer.text().strip()
            self.printer_list.clearSelection()

    def _send_test_print(self):
        """Send test print to selected printer"""
        if not self.selected_printer:
            self.test_result.setText("⚠️ Selecciona una impresora primero")
            self.test_result.setStyleSheet("color: #e67e22;")
            return
        
        # Show "sending" message
        self.test_result.setText("📤 Enviando ticket de prueba...")
        self.test_result.setStyleSheet("color: #3498db;")
        QtWidgets.QApplication.processEvents()  # Force UI update
        
        try:
            # Create test ticket content
            test_content = f"""
{"=" * 40}
     TITAN POS - TICKET DE PRUEBA
{"=" * 40}

Impresora: {self.selected_printer}
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

{"*" * 40}
     PRUEBA EXITOSA
{"*" * 40}

Si puedes leer este texto,
la impresora está configurada
correctamente.

"""
            
            logging.info(f"Sending test print to: {self.selected_printer}")
            
            # Send to printer using lp command (CUPS)
            # Use latin-1 encoding for thermal printers (ESC/POS compatibility)
            # -o raw prevents CUPS from processing the text
            result = subprocess.run(
                ["lp", "-d", self.selected_printer, "-o", "raw", "-"],
                input=test_content.encode('latin-1', errors='replace'),
                capture_output=True,
                timeout=10
            )
            
            logging.info(f"lp command return code: {result.returncode}")
            logging.info(f"lp stdout: {result.stdout.decode('utf-8', errors='ignore')}")
            logging.info(f"lp stderr: {result.stderr.decode('utf-8', errors='ignore')}")
            
            if result.returncode == 0:
                # Parse job ID from output
                output = result.stdout.decode('utf-8', errors='ignore')
                job_info = output.strip() if output else "Job submitted"
                
                self.test_result.setText(
                    f"✓ Ticket enviado a CUPS\n{job_info}\n\n"
                    "Verifica que la impresora esté:\n"
                    "• Encendida y conectada\n"
                    "• No en pausa en CUPS\n"
                    "• Con papel y lista"
                )
                self.test_result.setStyleSheet("color: #27ae60;")
                logging.info(f"Test print successful: {job_info}")
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore').strip()
                self.test_result.setText(
                    f"❌ Error CUPS:\n{error_msg}\n\n"
                    f"Verifica que '{self.selected_printer}' esté\n"
                    "configurada correctamente en CUPS."
                )
                self.test_result.setStyleSheet("color: #e74c3c;")
                logging.error(f"Test print failed: {error_msg}")
                
        except subprocess.TimeoutExpired:
            msg = "❌ Timeout: La impresora no responde"
            self.test_result.setText(msg)
            self.test_result.setStyleSheet("color: #e74c3c;")
            logging.error(msg)
        except FileNotFoundError:
            msg = "❌ Comando 'lp' no encontrado.\n¿Está CUPS instalado?"
            self.test_result.setText(msg)
            self.test_result.setStyleSheet("color: #e74c3c;")
            logging.error(msg)
        except Exception as e:
            msg = f"❌ Error: {str(e)}"
            self.test_result.setText(msg)
            self.test_result.setStyleSheet("color: #e74c3c;")
            logging.error(f"Test print exception: {e}", exc_info=True)

    def _on_drawer_toggled(self, checked):
        """Show/hide drawer settings"""
        self.drawer_group.setVisible(checked)

    def _test_drawer_open(self):
        """Test opening cash drawer"""
        if not self.selected_printer:
            self.drawer_test_result.setText("⚠️ Selecciona una impresora primero")
            self.drawer_test_result.setStyleSheet("color: #e67e22;")
            return
        
        pulse_str = self.drawer_seq_input.text().strip() or "\\x1B\\x70\\x00\\x19\\xFA"
        try:
            pulse_bytes = bytes(pulse_str, "utf-8").decode("unicode_escape").encode("latin1")
            ticket_engine.open_cash_drawer(self.selected_printer, pulse_bytes)
            self.drawer_test_result.setText("✓ Comando enviado al cajón")
            self.drawer_test_result.setStyleSheet("color: #27ae60;")
        except Exception as e:
            self.drawer_test_result.setText(f"❌ Error: {str(e)}")
            self.drawer_test_result.setStyleSheet("color: #e74c3c;")

    def _go_back(self):
        """Go to previous step"""
        current = self.stack.currentIndex()
        if current > 0:
            self.stack.setCurrentIndex(current - 1)
            self._update_navigation()

    def _go_next(self):
        """Go to next step"""
        current = self.stack.currentIndex()
        
        # Validation
        if current == 0 and not self.selected_printer:
            QtWidgets.QMessageBox.warning(
                self,
                "Impresora requerida",
                "Debes seleccionar una impresora antes de continuar."
            )
            return
        
        if current == 2:
            # Save paper width selection
            if self.radio_58.isChecked():
                self.paper_width = "58mm"
            else:
                self.paper_width = "80mm"
        
        if current == 3:
            # Save drawer settings
            self.drawer_enabled = self.drawer_check.isChecked()
            if self.drawer_enabled:
                self.drawer_sequence = self.drawer_seq_input.text().strip() or "\\x1B\\x70\\x00\\x19\\xFA"
        
        if current < self.stack.count() - 1:
            self.stack.setCurrentIndex(current + 1)
            
            # Update summary on last page
            if current + 1 == 4:
                self._update_summary()
            
            self._update_navigation()

    def _update_navigation(self):
        """Update navigation button states"""
        current = self.stack.currentIndex()
        total = self.stack.count()
        
        self.btn_back.setEnabled(current > 0)
        self.btn_next.setVisible(current < total - 1)
        self.btn_finish.setVisible(current == total - 1)
        
        # Update test status label in step 2
        if current == 1 and hasattr(self, 'test_status'):
            self.test_status.setText(
                f"Impresora seleccionada: <b>{self.selected_printer}</b>\n\n"
                "Envía una prueba de impresión para verificar la comunicación."
            )

    def _update_summary(self):
        """Update summary text"""
        summary = f"""
<h3>📋 Configuración de Impresora</h3>

<b>Impresora:</b> {self.selected_printer}
<b>Ancho de papel:</b> {self.paper_width}
<b>Impresión automática:</b> {'Sí' if self.auto_print_check.isChecked() else 'No'}

<b>Cajón de dinero:</b> {'Configurado' if self.drawer_enabled else 'No configurado'}
"""
        
        if self.drawer_enabled:
            summary += f"<b>Secuencia de apertura:</b> {self.drawer_sequence}\n"
        
        summary += """
<hr>
<i>Esta configuración se guardará en el archivo de configuración local.</i>
"""
        
        self.summary_text.setHtml(summary)

    def _finish(self):
        """Save configuration and close"""
        # Read current values DIRECTLY from UI widgets
        # Paper width from radio buttons
        paper = "58mm" if self.radio_58.isChecked() else "80mm"
        
        # Drawer settings from checkboxes/inputs
        drawer_enabled = self.drawer_check.isChecked()
        drawer_seq = self.drawer_seq_input.text().strip() or "\\x1B\\x70\\x00\\x19\\xFA"
        
        # Printer from either list selection or manual entry
        printer = self.selected_printer
        if self.manual_printer.text().strip():
            printer = self.manual_printer.text().strip()
        
        if not printer:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                "No se ha seleccionado una impresora."
            )
            return
        
        # Log what we're saving for debugging
        logging.getLogger(__name__).info(f"Saving printer config: printer={printer}, paper={paper}, drawer={drawer_enabled}")
        
        cfg = self.core.read_local_config()
        cfg.update({
            "printer_name": printer,
            "ticket_paper_width": paper,
            "auto_print_tickets": self.auto_print_check.isChecked(),
            "cash_drawer_enabled": drawer_enabled,
            "cash_drawer_pulse_bytes": drawer_seq,
        })
        success = self.core.write_local_config(cfg)
        
        if success:
            QtWidgets.QMessageBox.information(
                self,
                "Configuración Guardada",
                f"✓ La configuración se guardó correctamente.\n\n"
                f"Impresora: {printer}\n"
                f"Ancho papel: {paper}\n"
                f"Cajón: {'Habilitado' if drawer_enabled else 'Deshabilitado'}"
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "No se pudo guardar la configuración. Revisa los permisos del archivo."
            )
    
    def _apply_theme(self):
        """Apply current theme to dialog"""
        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        # Apply global stylesheet
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QWidget {{
                background-color: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QStackedWidget {{
                background-color: {c['bg_main']};
            }}
            QFrame {{
                background-color: {c['bg_card']};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                color: {c['text_primary']};
            }}
            QPushButton {{
                background-color: {c['btn_primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:disabled {{
                background-color: {c['border']};
                color: {c['text_secondary']};
            }}
            QLineEdit {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['input_border']};
                border-radius: 4px;
                padding: 6px;
            }}
            QLineEdit:focus {{
                border: 2px solid {c['input_focus']};
            }}
            QListWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {c['btn_primary']};
                color: white;
            }}
            QCheckBox {{
                color: {c['text_primary']};
            }}
            QRadioButton {{
                color: {c['text_primary']};
            }}
            QGroupBox {{
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                color: {c['text_secondary']};
            }}
            QTextEdit {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
            }}
        """)
