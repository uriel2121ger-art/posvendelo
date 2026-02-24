"""
Diálogo de Ventas del Turno - Permite al cajero ver y cancelar ventas de su turno
"""

from PyQt6 import QtCore, QtGui, QtWidgets

from app.utils.theme_manager import theme_manager


class TurnSalesDialog(QtWidgets.QDialog):
    """Diálogo que muestra las ventas del turno actual del cajero"""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.selected_sale_id = None
        
        self.setWindowTitle("📋 Ventas de Mi Turno")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        self._build_ui()
        self._apply_theme()
        self._load_sales()
    
    def _apply_theme(self):
        """Aplicar colores del tema actual"""
        c = theme_manager.get_colors()
        
        self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        self.header.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c['btn_primary']};")
        self.info_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")
        self.summary_label.setStyleSheet(f"font-weight: bold; color: {c['text_primary']};")
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                gridline-color: {c['border']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_header']};
                padding: 8px;
                border: 1px solid {c['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {c['btn_primary']};
                color: white;
            }}
        """)
        
        self.cancel_sale_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['btn_danger']};
                color: white;
                font-weight: bold;
                padding: 12px 25px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background: #c0392b;
            }}
            QPushButton:disabled {{
                background: {c['btn_disabled']};
            }}
        """)
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        self.header = QtWidgets.QLabel("🛒 Ventas de tu turno actual")
        layout.addWidget(self.header)
        
        self.info_label = QtWidgets.QLabel("Seleccione una venta para cancelar. Requiere autorización de supervisor.")
        layout.addWidget(self.info_label)
        
        # Tabla de ventas
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "Folio", "Hora", "Total", "Método", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)
        
        # Resumen
        self.summary_label = QtWidgets.QLabel("Total ventas: 0 | Total: $0.00")
        layout.addWidget(self.summary_label)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.cancel_sale_btn = QtWidgets.QPushButton("❌ Cancelar Venta Seleccionada")
        self.cancel_sale_btn.setEnabled(False)
        self.cancel_sale_btn.clicked.connect(self._cancel_selected_sale)
        btn_layout.addWidget(self.cancel_sale_btn)
        
        btn_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("Cerrar")
        close_btn.setStyleSheet("padding: 12px 25px;")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_sales(self):
        """Cargar ventas del turno actual"""
        try:
            from app.core import STATE

            # Obtener turno actual
            turn = self.core.get_current_turn(STATE.branch_id, STATE.user_id)
            if not turn:
                self.summary_label.setText("⚠️ No hay turno abierto")
                return
            
            turn_id = turn.get('id')
            
            # Obtener ventas del turno
            sales = self.core.db.execute_query("""
                SELECT id, folio_visible, timestamp, total, payment_method, status
                FROM sales
                WHERE turn_id = %s AND user_id = %s
                ORDER BY id DESC
            """, (turn_id, STATE.user_id))
            
            if not sales:
                self.summary_label.setText("No hay ventas en este turno")
                return
            
            self.table.setRowCount(len(sales))
            total_amount = 0
            active_count = 0
            
            for row_idx, sale in enumerate(sales):
                sale_dict = dict(sale)
                
                # ID
                id_item = QtWidgets.QTableWidgetItem(str(sale_dict['id']))
                id_item.setData(QtCore.Qt.ItemDataRole.UserRole, sale_dict['id'])
                self.table.setItem(row_idx, 0, id_item)
                
                # Folio
                self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(sale_dict.get('folio_visible', '')))
                
                # Hora
                timestamp = sale_dict.get('timestamp', '')
                if timestamp:
                    # Handle datetime objects or strings
                    if isinstance(timestamp, str):
                        time_part = timestamp.split('T')[-1][:5] if isinstance(timestamp, str) and 'T' in timestamp else timestamp[11:16] if len(timestamp) > 16 else '-'
                    elif hasattr(timestamp, 'strftime'):
                        # It's a datetime object
                        time_part = timestamp.strftime("%H:%M")
                    else:
                        time_part = str(timestamp)[11:16] if len(str(timestamp)) > 16 else '-'
                else:
                    time_part = '-'
                self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(time_part))
                
                # Total
                total = float(sale_dict.get('total', 0))
                self.table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"${total:,.2f}"))
                
                # Método
                payment_names = {
                    'cash': 'Efectivo', 'card': 'Tarjeta', 'transfer': 'Transferencia',
                    'mixed': 'Mixto', 'credit': 'Crédito', 'wallet': 'Monedero'
                }
                method = payment_names.get(sale_dict.get('payment_method', ''), sale_dict.get('payment_method', ''))
                self.table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(method))
                
                # Estado
                status = sale_dict.get('status', 'completed')
                status_text = '✅ Activa' if status != 'cancelled' else '❌ Cancelada'
                status_item = QtWidgets.QTableWidgetItem(status_text)
                if status == 'cancelled':
                    status_item.setForeground(QtGui.QColor('#e74c3c'))
                    for col in range(6):
                        item = self.table.item(row_idx, col)
                        if item:
                            item.setForeground(QtGui.QColor('#999'))
                else:
                    total_amount += total
                    active_count += 1
                self.table.setItem(row_idx, 5, status_item)
            
            self.summary_label.setText(f"Ventas activas: {active_count} | Total: ${total_amount:,.2f}")
            
        except Exception as e:
            print(f"Error loading turn sales: {e}")
            self.summary_label.setText(f"Error: {e}")
    
    def _on_selection_changed(self):
        """Manejar cambio de selección"""
        row = self.table.currentRow()
        if row >= 0:
            id_item = self.table.item(row, 0)
            status_item = self.table.item(row, 5)
            
            if id_item and status_item:
                self.selected_sale_id = id_item.data(QtCore.Qt.ItemDataRole.UserRole)
                # Solo habilitar si no está cancelada
                is_cancelled = '❌' in status_item.text()
                self.cancel_sale_btn.setEnabled(not is_cancelled)
        else:
            self.selected_sale_id = None
            self.cancel_sale_btn.setEnabled(False)
    
    def _cancel_selected_sale(self):
        """Cancelar la venta seleccionada con autorización"""
        if not self.selected_sale_id:
            return
        
        # Obtener detalles de la venta
        sale = self.core.get_sale(self.selected_sale_id)
        if not sale:
            QtWidgets.QMessageBox.warning(self, "Error", "No se encontró la venta.")
            return
        
        if sale.get("status") == "cancelled":
            QtWidgets.QMessageBox.warning(self, "Aviso", "Esta venta ya está cancelada.")
            return
        
        total = float(sale.get('total', 0))
        folio = sale.get('folio_visible', f"#{self.selected_sale_id}")
        
        # Requiere autorización
        from app.dialogs.supervisor_override_dialog import require_supervisor_override
        
        authorized, supervisor = require_supervisor_override(
            core=self.core,
            action_description=f"Cancelar Venta\nFolio: {folio}\nTotal: ${total:,.2f}",
            required_permission="cancel_sale",
            min_role="encargado",
            parent=self
        )
        
        if not authorized:
            return
        
        # Diálogo de cancelación
        from app.dialogs.cancel_sale_dialog import CancelSaleDialog
        dlg = CancelSaleDialog(self.core, self.selected_sale_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtWidgets.QMessageBox.information(
                self, 
                "Venta Cancelada", 
                f"La venta {folio} ha sido cancelada.\n\n"
                f"Autorizado por: {supervisor.get('full_name', supervisor.get('username'))}"
            )
            self._load_sales()  # Refrescar
