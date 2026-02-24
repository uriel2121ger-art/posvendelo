"""
Dialog for detailed turn summary with payment method breakdown.
Shows detailed report of all payment methods used during turn.
"""
from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class DetailedTurnReportDialog(QtWidgets.QDialog):
    """
    Detailed turn closing report with payment method breakdown.
    
    Shows:
    - Total sales by payment method
    - Cash movements (entries/exits)
    - Expected vs actual cash
    - Complete transaction list
    """
    
    def __init__(self, core, turn_id: int, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.turn_id = turn_id
        
        self.setWindowTitle("Corte de Caja Detallado")
        self.setModal(True)
        self.setMinimumSize(900, 700)
        
        self._load_data()
        self._build_ui()
        self.update_theme()
        
    def _load_data(self) -> None:
        """Load turn data and calculate breakdown."""
        # Get turn summary
        self.turn_summary = self.core.get_turn_summary(self.turn_id)
        
        # Get all sales by payment method
        sales_sql = """
            SELECT payment_method, COUNT(*) as count, COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE turn_id = %s
            GROUP BY payment_method
        """
        self.payment_breakdown = [
            dict(row) for row in self.core.db.execute_query(sales_sql, (self.turn_id,))
        ]
        
        # Get cash movements
        self.cash_movements = self.core.get_turn_movements(self.turn_id)
        
        # Get list of all sales
        sales_list_sql = """
            SELECT id, timestamp, total, payment_method, customer_id
            FROM sales
            WHERE turn_id = %s
            ORDER BY id DESC
            LIMIT 100
        """
        self.recent_sales = [
            dict(row) for row in self.core.db.execute_query(sales_list_sql, (self.turn_id,))
        ]
        
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QtWidgets.QLabel(f"📊 Corte de Caja Detallado - Turno #{self.turn_id}")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        
        # Tabs
        tabs = QtWidgets.QTabWidget()
        
        # Tab 1: Summary by Payment Method
        summary_tab = QtWidgets.QWidget()
        summary_layout = QtWidgets.QVBoxLayout(summary_tab)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        
        # Payment Method Table
        method_table = QtWidgets.QTableWidget(0, 3)
        method_table.setHorizontalHeaderLabels(["Método de Pago", "Transacciones", "Total"])
        method_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        method_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        method_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Payment method display names
        method_names = {
            "cash": "💵 Efectivo",
            "card": "💳 Tarjeta",
            "transfer": "🏦 Transferencia",
            "usd": "💵 Dólares USD",
            "vales": "🎫 Vales",
            "voucher": "🎫 Vales",
            "cheque": "📄 Cheque",
            "credit": "📝 Crédito",
            "wallet": "🌟 Puntos/Monedero",
            "mixed": "🔀 Mixto"
        }
        
        method_table.setRowCount(len(self.payment_breakdown))
        grand_total = 0.0
        
        for row_idx, payment in enumerate(self.payment_breakdown):
            method = payment.get('payment_method', 'cash')
            count = payment.get('count', 0)
            total = float(payment.get('total', 0.0))
            grand_total += total
            
            display_name = method_names.get(method, method.capitalize())
            
            items = [display_name, str(count), f"${total:,.2f}"]
            
            for col_idx, text in enumerate(items):
                item = QtWidgets.QTableWidgetItem(str(text))
                if col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                method_table.setItem(row_idx, col_idx, item)
                
        summary_layout.addWidget(QtWidgets.QLabel("Ventas por Método de Pago:"))
        summary_layout.addWidget(method_table)
        
        # Grand Total
        total_label = QtWidgets.QLabel(f"TOTAL GENERAL: ${grand_total:,.2f}")
        total_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60; padding: 10px;")
        total_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        summary_layout.addWidget(total_label)
        
        tabs.addTab(summary_tab, "Por Método de Pago")
        
        # Tab 2: Cash Control
        cash_tab = QtWidgets.QWidget()
        cash_layout = QtWidgets.QVBoxLayout(cash_tab)
        cash_layout.setContentsMargins(10, 10, 10, 10)
        
        # Cash summary
        initial_cash = self.turn_summary.get('initial_cash', 0.0)
        cash_sales = self.turn_summary.get('cash_sales', 0.0)
        total_in = self.turn_summary.get('total_in', 0.0)
        total_out = self.turn_summary.get('total_out', 0.0)
        expected_cash = self.turn_summary.get('expected_cash', 0.0)
        
        cash_summary_card = QtWidgets.QFrame()
        cash_summary_layout = QtWidgets.QFormLayout(cash_summary_card)
        cash_summary_layout.setContentsMargins(15, 15, 15, 15)
        
        cash_summary_layout.addRow("Fondo Inicial:", QtWidgets.QLabel(f"${initial_cash:,.2f}"))
        cash_summary_layout.addRow("Ventas en Efectivo:", QtWidgets.QLabel(f"${cash_sales:,.2f}"))
        cash_summary_layout.addRow("Entradas de Efectivo:", QtWidgets.QLabel(f"${total_in:,.2f}"))
        cash_summary_layout.addRow("Salidas de Efectivo:", QtWidgets.QLabel(f"$-{total_out:,.2f}"))
        
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        cash_summary_layout.addRow(separator)
        
        expected_label = QtWidgets.QLabel(f"${expected_cash:,.2f}")
        expected_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9;")
        cash_summary_layout.addRow("Efectivo Esperado:", expected_label)
        
        cash_layout.addWidget(cash_summary_card)
        
        # Cash movements table
        cash_layout.addWidget(QtWidgets.QLabel("\nMovimientos de Efectivo:"))
        
        movements_table = QtWidgets.QTableWidget(0, 4)
        movements_table.setHorizontalHeaderLabels(["Tipo", "Monto", "Razón", "Fecha/Hora"])
        movements_table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        movements_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        movements_table.setRowCount(len(self.cash_movements))
        
        for row_idx, movement in enumerate(self.cash_movements):
            type_icon = "🟢" if movement.get('movement_type') == 'in' else "🔴"
            type_text = f"{type_icon} Entrada" if movement.get('movement_type') == 'in' else f"{type_icon} Salida"
            amount = float(movement.get('amount', 0.0))
            reason = movement.get('reason', '')
            timestamp = movement.get('created_at', '')[:19] if movement.get('created_at') else ''
            
            items = [type_text, f"${amount:,.2f}", reason, timestamp]
            
            for col_idx, text in enumerate(items):
                item = QtWidgets.QTableWidgetItem(str(text))
                movements_table.setItem(row_idx, col_idx, item)
                
        cash_layout.addWidget(movements_table)
        
        tabs.addTab(cash_tab, "Control de Efectivo")
        
        # Tab 3: Recent Transactions
        trans_tab = QtWidgets.QWidget()
        trans_layout = QtWidgets.QVBoxLayout(trans_tab)
        trans_layout.setContentsMargins(10, 10, 10, 10)
        
        trans_table = QtWidgets.QTableWidget(0, 4)
        trans_table.setHorizontalHeaderLabels(["ID Venta", "Fecha/Hora", "Total", "Método Pago"])
        trans_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        trans_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        trans_table.setRowCount(len(self.recent_sales))
        
        for row_idx, sale in enumerate(self.recent_sales):
            sale_id = sale.get('id', 0)
            timestamp = sale.get('timestamp', '')[:19] if sale.get('timestamp') else ''
            total = float(sale.get('total', 0.0))
            method = sale.get('payment_method', 'cash')
            method_display = method_names.get(method, method.capitalize())
            
            items = [f"#{sale_id}", timestamp, f"${total:,.2f}", method_display]
            
            for col_idx, text in enumerate(items):
                item = QtWidgets.QTableWidgetItem(str(text))
                if col_idx in (0, 2):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                trans_table.setItem(row_idx, col_idx, item)
                
        trans_layout.addWidget(QtWidgets.QLabel("Últimas 100 Transacciones:"))
        trans_layout.addWidget(trans_table)
        
        tabs.addTab(trans_tab, "Transacciones")
        
        layout.addWidget(tabs)
        
        # Close button
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        print_btn = QtWidgets.QPushButton("🖨️ Imprimir Reporte")
        print_btn.setFixedHeight(40)
        print_btn.setFixedWidth(160)
        print_btn.clicked.connect(self._print_report)
        
        close_btn = QtWidgets.QPushButton("Cerrar")
        close_btn.setFixedHeight(40)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
    
    def _print_report(self) -> None:
        """Generate and print the detailed report via CUPS."""
        from app.utils import ticket_engine
        
        try:
            # Build print summary from our data
            print_summary = {
                'turn_id': self.turn_id,
                'id': self.turn_id,
                'initial_cash': self.turn_summary.get('initial_cash', 0),
                'cash_sales': self.turn_summary.get('cash_sales', 0),
                'total_in': self.turn_summary.get('total_in', 0),
                'total_out': self.turn_summary.get('total_out', 0),
                'expected_cash': self.turn_summary.get('expected_cash', 0),
                'payment_breakdown': {},
                'total_sales_all_methods': 0,
                'user_id': self.turn_summary.get('user_id', 'N/A'),
            }
            
            # Add payment breakdown
            for payment in self.payment_breakdown:
                method = payment.get('payment_method', 'cash')
                count = payment.get('count', 0)
                total = float(payment.get('total', 0))
                print_summary['payment_breakdown'][method] = {
                    'count': count,
                    'total': total
                }
                print_summary['total_sales_all_methods'] += total
            
            # Print using ticket_engine
            ticket_engine.print_turn_report(print_summary, self.core, report_type="DETALLADO")
            
            QtWidgets.QMessageBox.information(
                self,
                "Impresión",
                "Reporte enviado a impresora."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error de Impresión",
                f"Error al imprimir: {e}"
            )
        
    def update_theme(self) -> None:
        """Apply theme colors to the dialog."""
        c = theme_manager.get_colors()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QTableWidget {{
                background-color: {c['bg_main']};
                alternate-background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                gridline-color: {c['border']};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QHeaderView::section {{
                background-color: {c['table_header_bg']};
                color: {c['table_header_text']};
                padding: 10px;
                border: none;
                font-weight: bold;
            }}
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 6px;
            }}
            QPushButton {{
                background-color: {c['btn_primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QLabel {{
                border: none;
                background: transparent;
                color: {c['text_primary']};
            }}
            QTabWidget::pane {{
                border: 1px solid {c['border']};
                background-color: {c['bg_card']};
            }}
            QTabBar::tab {{
                background-color: {c['bg_main']};
                color: {c['text_primary']};
                padding: 10px 20px;
                border: 1px solid {c['border']};
            }}
            QTabBar::tab:selected {{
                background-color: {c['bg_card']};
                border-bottom: 2px solid {c['btn_primary']};
            }}
        """)

    def closeEvent(self, event):
        """Cleanup on close."""
        super().closeEvent(event)
