from PyQt6 import QtCore, QtGui, QtWidgets
import logging

from app.core import STATE, POSCore
from app.utils.theme_manager import theme_manager


class TurnPartialDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, summary=None, core: POSCore = None):
        super().__init__(parent)
        self.core = core
        self.summary = summary
        self.setWindowTitle("Corte Parcial")
        self.setFixedSize(500, 550)  # Increased height for summary
        self._build_ui()

    def _build_ui(self):
        # Get theme colors
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        colors = theme_manager.get_colors(theme)
        
        input_style = f"""
            background-color: {colors['input_bg']};
            color: {colors['text_primary']};
            border: 1px solid {colors['input_border']};
            border-radius: 5px;
            padding: 5px;
        """
        
        # Apply theme to dialog
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg_main']};
                color: {colors['text_primary']};
            }}
            QLabel {{
                color: {colors['text_primary']};
            }}
            QLineEdit {{
                {input_style}
            }}
            QDoubleSpinBox {{
                {input_style}
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        lbl_title = QtWidgets.QLabel("Registrar Entrada/Salida")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_title)
        
        # Type Selection
        self.type_group = QtWidgets.QButtonGroup(self)
        type_layout = QtWidgets.QHBoxLayout()
        
        self.rb_in = QtWidgets.QRadioButton("Entrada (Depósito)")
        self.rb_out = QtWidgets.QRadioButton("Salida (Retiro)")
        self.rb_out.setChecked(True)
        # Style radio buttons
        radio_style = f"color: {colors['text_primary']};"
        self.rb_in.setStyleSheet(radio_style)
        self.rb_out.setStyleSheet(radio_style)
        
        self.type_group.addButton(self.rb_in)
        self.type_group.addButton(self.rb_out)
        
        type_layout.addWidget(self.rb_in)
        type_layout.addWidget(self.rb_out)
        layout.addLayout(type_layout)
        
        # Amount
        layout.addWidget(QtWidgets.QLabel("Monto:"))
        self.amount_spin = QtWidgets.QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999.99)
        self.amount_spin.setPrefix("$")
        self.amount_spin.setDecimals(2)
        self.amount_spin.setFixedHeight(40)
        self.amount_spin.setStyleSheet(f"font-size: 16px; {input_style}")
        layout.addWidget(self.amount_spin)
        
        # Reason
        layout.addWidget(QtWidgets.QLabel("Motivo / Concepto:"))
        self.reason_edit = QtWidgets.QLineEdit()
        self.reason_edit.setPlaceholderText("Ej. Pago a proveedor, Cambio inicial...")
        self.reason_edit.setFixedHeight(40)
        layout.addWidget(self.reason_edit)
        
        # Add summary display if provided
        if self.summary:
            layout.addWidget(QtWidgets.QLabel(""))  # Spacer
            summary_lbl = QtWidgets.QLabel("📊 Resumen del Turno Actual")
            summary_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(summary_lbl)
            
            expected_cash = float(self.summary.get("expected_cash", 0))
            initial_cash = float(self.summary.get("initial_cash", 0))
            cash_sales = float(self.summary.get("cash_sales", 0))
            
            info_text = f"Fondo Inicial: ${initial_cash:,.2f}\n"
            info_text += f"Ventas Efectivo: ${cash_sales:,.2f}\n"
            info_text += f"Efectivo Esperado: ${expected_cash:,.2f}"
            
            info_lbl = QtWidgets.QLabel(info_text)
            info_lbl.setStyleSheet(f"padding: 10px; background: {colors['bg_card']}; border: 1px solid {colors['border']}; border-radius: 5px; color: {colors['text_primary']};")
            layout.addWidget(info_lbl)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        # Print button (only if summary provided)
        if self.summary:
            btn_print = QtWidgets.QPushButton("🖨️ Imprimir Reporte")
            btn_print.clicked.connect(self._print_report)
            btn_print.setStyleSheet(f"background-color: {colors['btn_primary']}; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
            btn_layout.addWidget(btn_print)
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QtWidgets.QPushButton("Registrar")
        btn_save.clicked.connect(self._save)
        btn_save.setStyleSheet(f"background-color: {colors['btn_success']}; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
    def _save(self):
        amount = self.amount_spin.value()
        reason = self.reason_edit.text().strip()
        
        if amount <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "El monto debe ser mayor a 0")
            return
            
        if not reason:
            QtWidgets.QMessageBox.warning(self, "Error", "Debes especificar un motivo")
            return
            
        move_type = "in" if self.rb_in.isChecked() else "out"
        
        try:
            self.core.register_cash_movement(
                turn_id=None, # Will infer current turn
                type_=move_type,
                amount=amount,
                reason=reason,
                branch_id=STATE.branch_id,
                user_id=STATE.user_id
            )
            
            # Abrir cajón después de registrar movimiento de efectivo
            try:
                from app.utils.ticket_engine import open_cash_drawer_safe
                open_cash_drawer_safe(core=self.core)
            except Exception as e:
                logging.warning(f"No se pudo abrir cajón después de movimiento: {e}")
            
            # Detailed notification
            type_text = "ENTRADA de efectivo" if move_type == "in" else "SALIDA de efectivo"
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
            msg_box.setWindowTitle("✅ Movimiento Registrado")
            msg_box.setText(f"<b>{type_text}</b>")
            msg_box.setInformativeText(
                f"<b>Monto:</b> ${amount:,.2f}<br>"
                f"<b>Concepto:</b> {reason}<br><br>"
                f"Este movimiento se reflejará en el corte del turno."
            )
            msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            msg_box.exec()
            
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo registrar: {e}")
    
    def _print_report(self):
        """Print partial cut report"""
        try:
            from app.utils import ticket_engine
            ticket_engine.print_turn_report(self.summary, self.core, report_type="CORTE PARCIAL")
            QtWidgets.QMessageBox.information(self, "Impresión", "Reporte enviado a impresora")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error de Impresión", f"No se pudo imprimir: {e}")
