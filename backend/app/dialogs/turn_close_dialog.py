from PyQt6 import QtCore, QtGui, QtWidgets

from app.utils.theme_manager import theme_manager


class TurnCloseDialog(QtWidgets.QDialog):
    def __init__(self, summary, core, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cerrar Turno")
        self.resize(650, 600)
        self.result_data = None
        self.core = core
        self.summary = summary  # Store for print function
        
        # Get theme colors
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        colors = theme_manager.get_colors(theme)
        
        expected_cash = float(summary.get("expected_cash", 0))
        system_sales = float(summary.get("cash_sales", 0))
        
        initial_cash = float(summary.get("initial_cash", 0))
        total_in = float(summary.get("total_in", 0))
        total_out = float(summary.get("total_out", 0))
        total_expenses = float(summary.get("total_expenses", 0))
        expenses_count = int(summary.get("expenses_count", 0))
        
        # Payment breakdown
        payment_breakdown = summary.get("payment_breakdown", {})
        total_sales_all = float(summary.get("total_sales_all_methods", 0))
        
        layout = QtWidgets.QVBoxLayout()
        
        input_style = f"""
            background: {colors['input_bg']};
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
            QGroupBox {{
                background-color: {colors['bg_card']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                font-weight: bold;
                color: {colors['text_primary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLabel {{
                color: {colors['text_primary']};
            }}
            QDoubleSpinBox, QPlainTextEdit {{
                {input_style}
            }}
        """)
        
        # Info Group
        info_group = QtWidgets.QGroupBox("Resumen del Turno")
        info_layout = QtWidgets.QFormLayout(info_group)
        info_layout.addRow("Fondo Inicial:", QtWidgets.QLabel(f"${initial_cash:.2f}"))
        info_layout.addRow("Ventas Efectivo:", QtWidgets.QLabel(f"${system_sales:.2f}"))
        info_layout.addRow("Entradas (+):", QtWidgets.QLabel(f"${total_in:.2f}"))
        info_layout.addRow("Salidas (-):", QtWidgets.QLabel(f"${total_out:.2f}"))
        
        # Gastos en efectivo
        if total_expenses > 0:
            lbl_expenses = QtWidgets.QLabel(f"${total_expenses:.2f} ({expenses_count} ops)")
            lbl_expenses.setStyleSheet(f"color: {colors.get('btn_danger', '#e74c3c')}; font-weight: bold;")
            info_layout.addRow("💸 Gastos Efectivo (-):", lbl_expenses)
        
        lbl_expected = QtWidgets.QLabel(f"${expected_cash:.2f}")
        lbl_expected.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {colors.get('btn_primary', '#2980b9')};")
        info_layout.addRow("Efectivo Esperado:", lbl_expected)
        
        layout.addWidget(info_group)
        
        # Payment Methods Breakdown - Theme-aware
        payment_group = QtWidgets.QGroupBox("Desglose por Método de Pago")
        payment_layout = QtWidgets.QVBoxLayout(payment_group)
        
        # Payment method translations
        method_names = {
            'cash': 'Efectivo',
            'card': 'Tarjeta',
            'credit': 'Crédito',
            'wallet': 'Wallet/Puntos',
            'gift_card': 'Tarjeta Regalo',
            'mixed': 'Mixto',
            'transfer': 'Transferencia',
            'cheque': 'Cheque'
        }
        
        # Use simple labels instead of table to avoid rendering issues
        if payment_breakdown:
            for method, data in sorted(payment_breakdown.items()):
                if method == 'mixed_details':
                    continue
                    
                method_label = QtWidgets.QLabel(
                    f"  • {method_names.get(method, method.title())}: "
                    f"{data['count']} transacciones = ${data['total']:,.2f}"
                )
                method_label.setStyleSheet(f"padding: 5px; font-size: 12px; color: {colors['text_primary']};")
                payment_layout.addWidget(method_label)
            
            # Total verification
            total_label = QtWidgets.QLabel(f"TOTAL: ${total_sales_all:,.2f}")
            total_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {colors.get('btn_success', '#27ae60')}; padding: 10px 5px;")
            payment_layout.addWidget(total_label)
        else:
            no_data_label = QtWidgets.QLabel("No hay ventas registradas en este turno")
            no_data_label.setStyleSheet(f"color: {colors.get('text_secondary', '#999')}; font-style: italic; padding: 10px;")
            payment_layout.addWidget(no_data_label)
        
        layout.addWidget(payment_group)
        
        # Input Real
        layout.addWidget(QtWidgets.QLabel("Efectivo Real en Caja:"))
        self.real_cash_input = QtWidgets.QDoubleSpinBox()
        self.real_cash_input.setRange(0, 1000000)
        self.real_cash_input.setPrefix("$")
        self.real_cash_input.setValue(expected_cash)
        self.real_cash_input.setStyleSheet(f"font-size: 16px; font-weight: bold; {input_style}")
        layout.addWidget(self.real_cash_input)
        
        # Diferencia
        self.lbl_diff = QtWidgets.QLabel("Diferencia: $0.00")
        self.lbl_diff.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_diff)
        
        self.real_cash_input.valueChanged.connect(
            lambda v: self._update_diff(v, expected_cash)
        )
        
        # Notes
        layout.addWidget(QtWidgets.QLabel("Notas:"))
        self.notes_input = QtWidgets.QPlainTextEdit()
        self.notes_input.setPlaceholderText("Comentarios sobre el cierre...")
        self.notes_input.setFixedHeight(60)
        layout.addWidget(self.notes_input)        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        # Print button
        self.btn_print = QtWidgets.QPushButton("🖨️ Imprimir Reporte")
        self.btn_print.clicked.connect(self._print_report)
        self.btn_print.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.get('btn_primary', '#2196F3')};
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors.get('btn_primary_hover', '#1976D2')};
            }}
        """)
        btn_layout.addWidget(self.btn_print)
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_close = QtWidgets.QPushButton("Cerrar Turno")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.get('btn_danger', '#e74c3c')};
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn_close.clicked.connect(self._accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def _update_diff(self, val, expected):
        diff = val - expected
        color = "green" if abs(diff) < 0.01 else "red"
        self.lbl_diff.setText(f"Diferencia: ${diff:.2f}")
        self.lbl_diff.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {color};")
        
    def _print_report(self):
        """Print turn report"""
        try:
            from app.utils import ticket_engine

            # Update summary with current input values
            print_summary = self.summary.copy()
            print_summary["real_cash"] = self.real_cash_input.value()
            print_summary["notes"] = self.notes_input.toPlainText().strip()
            
            ticket_engine.print_turn_report(print_summary, self.core, report_type="CIERRE")
            QtWidgets.QMessageBox.information(self, "Impresión", "Reporte enviado a impresora")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error de Impresión", f"No se pudo imprimir: {e}")
    
    def _accept(self):
        """Handle turn close"""
        self.result_data = {
            "closing_amount": self.real_cash_input.value(),
            "notes": self.notes_input.toPlainText().strip()
        }
        self.accept()

    def get_real_cash(self):
        return self.real_cash_input.value()
