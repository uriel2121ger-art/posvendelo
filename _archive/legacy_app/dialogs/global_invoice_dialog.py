"""
Global Invoice Dialog - Dashboard de Facturación Global
Permite generar CFDIs globales para ventas en efectivo sin facturar
"""

from typing import Optional
from datetime import datetime, timedelta
import logging

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

class GlobalInvoiceDialog(QtWidgets.QDialog):
    """Dashboard para generar facturas globales."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.sales_data = []  # Initialize sales data
        self.setWindowTitle("Facturación Global - Dashboard Fiscal")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.update_theme()
        self.load_uninvoiced_sales()
    
    def showEvent(self, event):
        """Apply theme when dialog is shown."""
        super().showEvent(event)
        self.update_theme()
    
    def update_theme(self):
        """Apply current theme to the dialog."""
        try:
            from app.utils.theme_manager import theme_manager
            colors = theme_manager.get_colors()
            self.setStyleSheet(f"""
                QDialog {{
                    background-color: {colors['background']};
                    color: {colors['text']};
                }}
                QGroupBox {{
                    background-color: {colors['surface']};
                    border: 1px solid {colors['border']};
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                    color: {colors['text']};
                }}
                QGroupBox::title {{
                    color: {colors['text']};
                }}
                QTableWidget {{
                    background-color: {colors['surface']};
                    color: {colors['text']};
                    gridline-color: {colors['border']};
                }}
                QTableWidget::item {{
                    color: {colors['text']};
                }}
                QHeaderView::section {{
                    background-color: {colors['primary']};
                    color: white;
                    padding: 5px;
                    border: none;
                }}
                QLabel {{
                    color: {colors['text']};
                }}
                QDateEdit {{
                    background-color: {colors['surface']};
                    color: {colors['text']};
                    border: 1px solid {colors['border']};
                    padding: 5px;
                }}
                QPushButton {{
                    background-color: {colors['surface']};
                    color: {colors['text']};
                    border: 1px solid {colors['border']};
                    padding: 5px 10px;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: {colors['primary']};
                    color: white;
                }}
                QCheckBox {{
                    color: {colors['text']};
                }}
            """)
        except Exception as e:
            logger.warning(f"Could not apply theme: {e}")

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel("📊 Dashboard de Facturación Global")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Info panel
        info = QtWidgets.QLabel(
            "Genera CFDIs globales para ventas en efectivo (Serie B) sin facturar.\n"
            "El SAT permite agrupar ventas al público en general en un solo CFDI."
        )
        info.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(info)
        
        # Period selector
        period_group = QtWidgets.QGroupBox("Período")
        period_layout = QtWidgets.QHBoxLayout(period_group)
        
        self.date_from = QtWidgets.QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QtCore.QDate.currentDate().addDays(-7))
        
        self.date_to = QtWidgets.QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QtCore.QDate.currentDate().addDays(-1))
        
        period_layout.addWidget(QtWidgets.QLabel("Desde:"))
        period_layout.addWidget(self.date_from)
        period_layout.addWidget(QtWidgets.QLabel("Hasta:"))
        period_layout.addWidget(self.date_to)
        
        # Quick buttons
        btn_today = QtWidgets.QPushButton("Ayer")
        btn_today.clicked.connect(lambda: self.set_period('daily'))
        btn_week = QtWidgets.QPushButton("Semana")
        btn_week.clicked.connect(lambda: self.set_period('weekly'))
        btn_month = QtWidgets.QPushButton("Mes")
        btn_month.clicked.connect(lambda: self.set_period('monthly'))
        
        period_layout.addWidget(btn_today)
        period_layout.addWidget(btn_week)
        period_layout.addWidget(btn_month)
        
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh.clicked.connect(self.load_uninvoiced_sales)
        period_layout.addWidget(btn_refresh)
        
        # Separator
        period_layout.addWidget(QtWidgets.QLabel("  |  "))
        
        # Search by folio
        self.folio_search = QtWidgets.QLineEdit()
        self.folio_search.setPlaceholderText("Folio o ID...")
        self.folio_search.setFixedWidth(120)
        self.folio_search.returnPressed.connect(self.search_by_folio)
        period_layout.addWidget(self.folio_search)
        
        btn_search = QtWidgets.QPushButton("🔍 Buscar")
        btn_search.clicked.connect(self.search_by_folio)
        period_layout.addWidget(btn_search)
        
        layout.addWidget(period_group)
        
        # Summary panel
        summary_group = QtWidgets.QGroupBox("Resumen de Ventas Sin Facturar")
        summary_layout = QtWidgets.QGridLayout(summary_group)
        
        self.lbl_total_sales = QtWidgets.QLabel("0")
        self.lbl_total_sales.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
        self.lbl_total_amount = QtWidgets.QLabel("$0.00")
        self.lbl_total_amount.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        
        summary_layout.addWidget(QtWidgets.QLabel("Ventas:"), 0, 0)
        summary_layout.addWidget(self.lbl_total_sales, 0, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Total:"), 0, 2)
        summary_layout.addWidget(self.lbl_total_amount, 0, 3)
        
        layout.addWidget(summary_group)
        
        # Sales table
        self.sales_table = QtWidgets.QTableWidget()
        self.sales_table.setColumnCount(6)
        self.sales_table.setHorizontalHeaderLabels([
            "Seleccionar", "Folio", "Fecha", "Total", "Método", "Serie"
        ])
        self.sales_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.sales_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.sales_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.sales_table)
        
        # Select all checkbox
        select_all_layout = QtWidgets.QHBoxLayout()
        self.chk_select_all = QtWidgets.QCheckBox("Seleccionar todo")
        self.chk_select_all.stateChanged.connect(self.toggle_select_all)
        select_all_layout.addWidget(self.chk_select_all)
        select_all_layout.addStretch()
        
        self.lbl_selected = QtWidgets.QLabel("Seleccionados: 0 | $0.00")
        select_all_layout.addWidget(self.lbl_selected)
        layout.addLayout(select_all_layout)
        
        # Action buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_generate = QtWidgets.QPushButton("🧾 Generar Factura Global")
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_generate.clicked.connect(self.generate_global_invoice)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_generate)
        layout.addLayout(btn_layout)
    
    def set_period(self, period_type: str):
        """Set date range based on period type."""
        today = QtCore.QDate.currentDate()
        
        if period_type == 'daily':
            self.date_from.setDate(today.addDays(-1))
            self.date_to.setDate(today.addDays(-1))
        elif period_type == 'weekly':
            # Start from Monday of last week
            day_of_week = today.dayOfWeek()
            start = today.addDays(-day_of_week - 6)
            end = today.addDays(-day_of_week)
            self.date_from.setDate(start)
            self.date_to.setDate(end)
        elif period_type == 'monthly':
            # Last month
            first_of_month = today.addMonths(-1)
            first_of_month = first_of_month.addDays(-first_of_month.day() + 1)
            last_of_month = today.addDays(-today.day())
            self.date_from.setDate(first_of_month)
            self.date_to.setDate(last_of_month)
        
        self.load_uninvoiced_sales()
    
    def search_by_folio(self):
        """Search for a specific sale by folio or ID."""
        search_term = self.folio_search.text().strip()
        if not search_term:
            QtWidgets.QMessageBox.warning(self, "Búsqueda", "Ingresa un folio o ID para buscar.")
            return
        
        try:
            # Search by folio_visible or sale ID
            sql = """
                SELECT s.id, s.folio_visible, s.serie, s.timestamp, s.total, s.payment_method
                FROM sales s
                LEFT JOIN cfdis c ON c.sale_id = s.id
                WHERE (s.folio_visible LIKE %s OR CAST(s.id AS TEXT) = %s)
                AND c.id IS NULL
                AND s.status != 'cancelled'
                ORDER BY s.timestamp DESC
                LIMIT 50
            """
            
            sales = [dict(s) for s in self.core.db.execute_query(sql, (f"%{search_term}%", search_term))]
            
            if not sales:
                QtWidgets.QMessageBox.information(
                    self, "Sin resultados",
                    f"No se encontró ninguna venta sin facturar con folio '{search_term}'."
                )
                return
            
            # Populate table with results
            self.sales_table.setRowCount(len(sales))
            self.sales_data = sales
            
            total_amount = 0
            
            for row, sale in enumerate(sales):
                # Checkbox
                chk = QtWidgets.QCheckBox()
                chk.setChecked(True)
                chk.stateChanged.connect(self.update_selected_total)
                chk_widget = QtWidgets.QWidget()
                chk_layout = QtWidgets.QHBoxLayout(chk_widget)
                chk_layout.addWidget(chk)
                chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chk_layout.setContentsMargins(0, 0, 0, 0)
                self.sales_table.setCellWidget(row, 0, chk_widget)
                
                # Folio
                folio = sale.get('folio_visible') or f"#{sale['id']}"
                self.sales_table.setItem(row, 1, QtWidgets.QTableWidgetItem(folio))
                
                # Date
                ts = sale.get('timestamp', '')
                date_str = ts[:10] if len(ts) >= 10 else ts
                self.sales_table.setItem(row, 2, QtWidgets.QTableWidgetItem(date_str))
                
                # Total
                total = float(sale.get('total', 0))
                total_amount += total
                self.sales_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"${total:.2f}"))
                
                # Payment method
                self.sales_table.setItem(row, 4, QtWidgets.QTableWidgetItem(
                    sale.get('payment_method', 'cash').capitalize()
                ))
                
                # Serie
                self.sales_table.setItem(row, 5, QtWidgets.QTableWidgetItem(
                    sale.get('serie', 'B')
                ))
            
            self.lbl_total_sales.setText(str(len(sales)))
            self.lbl_total_amount.setText(f"${total_amount:,.2f}")
            self.chk_select_all.setChecked(True)
            self.update_selected_total()
            
            # Clear search field
            self.folio_search.clear()
            
        except Exception as e:
            logger.error(f"Error searching by folio: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al buscar: {e}")
    
    def load_uninvoiced_sales(self):
        """Load sales without individual CFDI."""
        try:
            start_date = self.date_from.date().toString("yyyy-MM-dd")
            end_date = self.date_to.date().toString("yyyy-MM-dd")
            
            # Query for cash sales without CFDI
            sql = """
                SELECT s.id, s.folio_visible, s.serie, s.timestamp, s.total, s.payment_method
                FROM sales s
                LEFT JOIN cfdis c ON c.sale_id = s.id
                WHERE CAST(s.timestamp AS DATE) BETWEEN %s AND %s
                AND c.id IS NULL
                AND s.status != 'cancelled'
                AND s.payment_method IN ('cash', 'efectivo')
                ORDER BY s.timestamp DESC
            """
            
            sales = [dict(s) for s in self.core.db.execute_query(sql, (start_date, end_date))]
            
            self.sales_table.setRowCount(len(sales))
            self.sales_data = sales
            
            total_amount = 0
            
            for row, sale in enumerate(sales):
                # Checkbox
                chk = QtWidgets.QCheckBox()
                chk.setChecked(True)
                chk.stateChanged.connect(self.update_selected_total)
                chk_widget = QtWidgets.QWidget()
                chk_layout = QtWidgets.QHBoxLayout(chk_widget)
                chk_layout.addWidget(chk)
                chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chk_layout.setContentsMargins(0, 0, 0, 0)
                self.sales_table.setCellWidget(row, 0, chk_widget)
                
                # Folio
                folio = sale.get('folio_visible') or f"#{sale['id']}"
                self.sales_table.setItem(row, 1, QtWidgets.QTableWidgetItem(folio))
                
                # Date
                ts = sale.get('timestamp', '')
                if ts:
                    date_str = ts[:10] if len(ts) >= 10 else ts
                else:
                    date_str = ''
                self.sales_table.setItem(row, 2, QtWidgets.QTableWidgetItem(date_str))
                
                # Total
                total = float(sale.get('total', 0))
                total_amount += total
                self.sales_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"${total:.2f}"))
                
                # Payment method
                self.sales_table.setItem(row, 4, QtWidgets.QTableWidgetItem(
                    sale.get('payment_method', 'cash').capitalize()
                ))
                
                # Serie
                self.sales_table.setItem(row, 5, QtWidgets.QTableWidgetItem(
                    sale.get('serie', 'B')
                ))
            
            self.lbl_total_sales.setText(str(len(sales)))
            self.lbl_total_amount.setText(f"${total_amount:,.2f}")
            self.chk_select_all.setChecked(True)
            self.update_selected_total()
            
        except Exception as e:
            logger.error(f"Error loading uninvoiced sales: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al cargar ventas: {e}")
    
    def toggle_select_all(self, state):
        """Toggle all checkboxes."""
        checked = state == Qt.CheckState.Checked.value
        for row in range(self.sales_table.rowCount()):
            widget = self.sales_table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QtWidgets.QCheckBox)
                if chk:
                    chk.setChecked(checked)
        self.update_selected_total()
    
    def update_selected_total(self):
        """Update selected count and total."""
        selected_count = 0
        selected_total = 0.0
        
        for row in range(self.sales_table.rowCount()):
            widget = self.sales_table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QtWidgets.QCheckBox)
                if chk and chk.isChecked():
                    selected_count += 1
                    if row < len(self.sales_data):
                        selected_total += float(self.sales_data[row].get('total', 0))
        
        self.lbl_selected.setText(f"Seleccionados: {selected_count} | ${selected_total:,.2f}")
    
    def get_selected_sales(self):
        """Get list of selected sale IDs."""
        selected = []
        for row in range(self.sales_table.rowCount()):
            widget = self.sales_table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QtWidgets.QCheckBox)
                if chk and chk.isChecked():
                    if row < len(self.sales_data):
                        selected.append(self.sales_data[row])
        return selected
    
    def generate_global_invoice(self):
        """Generate global CFDI for selected sales."""
        selected_sales = self.get_selected_sales()
        
        if not selected_sales:
            QtWidgets.QMessageBox.warning(
                self, "Sin selección",
                "Selecciona al menos una venta para facturar."
            )
            return
        
        # Confirm
        total = sum(float(s.get('total', 0)) for s in selected_sales)
        series = set(s.get('serie', 'B') for s in selected_sales)
        series_str = ', '.join(sorted(series))
        
        result = QtWidgets.QMessageBox.question(
            self, "Confirmar Factura Global",
            f"¿Generar factura global por {len(selected_sales)} ventas?\n\n"
            f"Series incluidas: {series_str}\n"
            f"Total: ${total:,.2f}\n\n"
            f"RFC: XAXX010101000 (Público en General)\n"
            f"Uso CFDI: S01 (Sin efectos fiscales)",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if result != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Generate using GlobalInvoicingService with selected sales
            from app.fiscal.global_invoicing import GlobalInvoicingService
            service = GlobalInvoicingService(self.core)
            
            start_date = self.date_from.date().toString("yyyy-MM-dd")
            end_date = self.date_to.date().toString("yyyy-MM-dd")
            
            # Get selected sale IDs
            sale_ids = [s['id'] for s in selected_sales]
            
            # Use new method that accepts pre-selected sales
            result = service.generate_global_cfdi_from_selection(
                sale_ids=sale_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            if result.get('success'):
                QtWidgets.QMessageBox.information(
                    self, "Factura Global Generada",
                    f"✅ CFDI Global generado exitosamente\n\n"
                    f"UUID: {result.get('uuid', 'Pendiente de timbrado')}\n"
                    f"Ventas incluidas: {result.get('sales_count', len(selected_sales))}\n"
                    f"Total: ${total:,.2f}"
                )
                self.accept()
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    f"No se pudo generar la factura:\n{result.get('error', 'Error desconocido')}"
                )
                
        except Exception as e:
            logger.error(f"Error generating global invoice: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Error al generar factura global:\n{e}"
            )

    def closeEvent(self, event):
        """Cleanup on close."""
        self.sales_data = []
        super().closeEvent(event)
