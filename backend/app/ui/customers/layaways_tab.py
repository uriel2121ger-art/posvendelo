from datetime import datetime
import logging

from PyQt6 import QtCore, QtWidgets

from app.core import POSCore

logger = logging.getLogger(__name__)
from app.dialogs.payment_dialog import PaymentDialog
from app.utils import ticket_engine
from app.utils.theme_manager import theme_manager


class ApartadosTab(QtWidgets.QWidget):
    """Pestaña de Apartados (Gestión de Layaways)"""
    
    def __init__(self, core: POSCore, parent_tab=None):
        super().__init__()
        self.parent_tab = parent_tab
        self.core = core
        self._build_ui()
    
    def _build_ui(self):
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Cards de resumen
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(15)
        
        self.card_activos = self._create_card("Apartados Activos", "0", "#4CAF50", c)
        self.card_total = self._create_card("Total en Apartados", "$0.00", "#2196F3", c)
        self.card_vencimientos = self._create_card("Próximos Vencimientos", "0", "#FF9800", c)
        
        cards_layout.addWidget(self.card_activos)
        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_vencimientos)
        
        layout.addLayout(cards_layout)
        
        # Sub-tabs
        self.sub_tabs = QtWidgets.QTabWidget()
        
        # Tab Activos
        tab_activos = QtWidgets.QWidget()
        activos_layout = QtWidgets.QVBoxLayout(tab_activos)
        activos_layout.setContentsMargins(15, 15, 15, 15)
        
        self.table_activos = QtWidgets.QTableWidget(0, 8)
        self.table_activos.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_activos.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_activos.setHorizontalHeaderLabels(["Cliente", "Productos", "Total", "Pagado", "Restante", "Vencimiento", "Abonar", "Cancelar"])
        self.table_activos.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_activos.verticalHeader().setVisible(False)
        activos_layout.addWidget(self.table_activos)
        
        # Tab Completados
        tab_completados = QtWidgets.QWidget()
        completados_layout = QtWidgets.QVBoxLayout(tab_completados)
        completados_layout.setContentsMargins(15, 15, 15, 15)
        
        self.table_completados = QtWidgets.QTableWidget(0, 7)
        self.table_completados.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_completados.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_completados.setHorizontalHeaderLabels(["Cliente", "Productos", "Total", "Pagado", "Finalizado", "Notas", "Estado"])
        self.table_completados.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_completados.verticalHeader().setVisible(False)
        completados_layout.addWidget(self.table_completados)
        
        # Tab Cancelados
        tab_cancelados = QtWidgets.QWidget()
        cancelados_layout = QtWidgets.QVBoxLayout(tab_cancelados)
        cancelados_layout.setContentsMargins(15, 15, 15, 15)
        
        self.table_cancelados = QtWidgets.QTableWidget(0, 7)
        self.table_cancelados.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_cancelados.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_cancelados.setHorizontalHeaderLabels(["Cliente", "Productos", "Total", "Pagado", "Cancelado", "Notas", "Estado"])
        self.table_cancelados.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table_cancelados.verticalHeader().setVisible(False)
        cancelados_layout.addWidget(self.table_cancelados)
        
        self.sub_tabs.addTab(tab_activos, "Activos")
        self.sub_tabs.addTab(tab_completados, "Completados")
        self.sub_tabs.addTab(tab_cancelados, "Cancelados")
        
        layout.addWidget(self.sub_tabs)
    
    def _create_card(self, title: str, value: str, color: str, c: dict) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 10px;
                border-left: 5px solid {color};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 13px; font-weight: 600; border: none;")
        
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card
    
    def refresh_data(self):
        """Refrescar datos de apartados"""
        try:
            # Verificar si la tabla layaways existe
            # Use DatabaseManager.list_tables() for PostgreSQL compatibility
            try:
                tables = self.core.db.list_tables()
                table_exists = 'layaways' in tables
            except Exception:
                # Fallback: try list_tables() or information_schema
                try:
                    tables = self.core.db.list_tables()
                    table_exists = 'layaways' in tables
                except Exception:
                    # Last resort: try information_schema for PostgreSQL
                    try:
                        table_check = self.core.db.execute_query("""
                            SELECT table_name FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = 'layaways'
                        """)
                        table_exists = len(table_check) > 0
                    except Exception:
                        table_exists = False
            
            # FIX 2026-02-01: Usar table_exists en lugar de table_check (variable correcta)
            if not table_exists:
                logger.info("Tabla 'layaways' no existe - funcionalidad pendiente")
                # Resetear cards a 0
                self.card_activos.findChild(QtWidgets.QLabel, "value_label").setText("0")
                self.card_total.findChild(QtWidgets.QLabel, "value_label").setText("$0.00")
                self.card_vencimientos.findChild(QtWidgets.QLabel, "value_label").setText("0")
                self.table_activos.setRowCount(0)
                return
            
            # Utilizar el método core.list_layaways que ya maneja la lógica correcta
            layaways_active = self.core.list_layaways(status='active')
            layaways_completed = self.core.list_layaways(status='completed')
            layaways_cancelled = self.core.list_layaways(status='cancelled')
            
            # Actualizar cards (sumando activos)
            activos = len(layaways_active)
            total_deuda = sum(float(l.get('balance_due', 0) or 0) for l in layaways_active)
            vencimientos = sum(1 for l in layaways_active if l.get('due_date', '') <= datetime.now().strftime('%Y-%m-%d'))
            
            self.card_activos.findChild(QtWidgets.QLabel, "value_label").setText(str(activos))
            self.card_total.findChild(QtWidgets.QLabel, "value_label").setText(f"${total_deuda:,.2f}")
            self.card_vencimientos.findChild(QtWidgets.QLabel, "value_label").setText(str(vencimientos))
            
            # --- Helper para llenar tablas ---
            def fill_table(table, data, is_active=False):
                table.setRowCount(len(data))
                for row_idx, layaway in enumerate(data):
                    l_dict = dict(layaway)
                    total_val = float(l_dict.get('total_amount', 0) or 0)
                    paid_val = float(l_dict.get('amount_paid', 0) or 0)
                    restante = float(l_dict.get('balance_due', 0) or 0)
                    customer_name = l_dict.get('customer_name') or l_dict.get('name') or "Desconocido"
                    
                    table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(customer_name))
                    
                    # Botón Ver Detalles
                    btn_details = QtWidgets.QLabel("📄 Ver Productos")
                    btn_details.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    btn_details.setStyleSheet("QLabel { color: #2196F3; font-weight: bold; text-decoration: underline; } QLabel:hover { color: #1976D2; }")
                    btn_details.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                    def make_details_handler(lid):
                        return lambda event: self._show_details(lid)
                    btn_details.mousePressEvent = make_details_handler(l_dict['id'])
                    table.setCellWidget(row_idx, 1, btn_details)
                    
                    table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(f"${total_val:,.2f}"))
                    table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"${paid_val:,.2f}"))
                    
                    if is_active:
                        table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(f"${restante:,.2f}"))
                        table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(l_dict.get('due_date', 'N/A')))
                        
                        # Botón Abonar / Liquidar
                        btn_pay = QtWidgets.QLabel("💰 ABONAR")
                        btn_pay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                        btn_pay.setStyleSheet("""
                            QLabel { background: #2196F3; color: white; border-radius: 4px; padding: 4px; font-weight: bold; }
                            QLabel:hover { background: #1976D2; }
                        """)
                        btn_pay.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                        def make_pay_handler(lid):
                            return lambda event: self._open_payment_layaway(lid)
                        btn_pay.mousePressEvent = make_pay_handler(l_dict['id'])
                        
                        table.setCellWidget(row_idx, 6, btn_pay)
                        
                        # Botón Cancelar Apartado
                        btn_cancel = QtWidgets.QLabel("❌ CANCELAR")
                        btn_cancel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                        btn_cancel.setStyleSheet("""
                            QLabel { background: #e74c3c; color: white; border-radius: 4px; padding: 4px; font-weight: bold; }
                            QLabel:hover { background: #c0392b; }
                        """)
                        btn_cancel.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                        def make_cancel_handler(lid, cname, ttl):
                            return lambda event: self._cancel_layaway(lid, cname, ttl)
                        btn_cancel.mousePressEvent = make_cancel_handler(l_dict['id'], customer_name, total_val)
                        
                        table.setCellWidget(row_idx, 7, btn_cancel)
                    else:
                        # Para completados/cancelados
                        date_str = l_dict.get('created_at', '')[:10] # o timestamp de cierre si existiera
                        table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(date_str))
                        table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(l_dict.get('notes', '')))
                        status_text = "Completado" if l_dict.get('status') == 'completed' else "Cancelado"
                        table.setItem(row_idx, 6, QtWidgets.QTableWidgetItem(status_text))
            
            fill_table(self.table_activos, layaways_active, is_active=True)
            fill_table(self.table_completados, layaways_completed, is_active=False)
            fill_table(self.table_cancelados, layaways_cancelled, is_active=False)
        except Exception as e:
            print(f"Error refreshing layaways: {e}")
            import traceback
            traceback.print_exc()
    
    def _open_payment_layaway(self, layaway_id):
        """Abrir diálogo de pago avanzado para abonar o liquidar"""
        try:
            # 1. Obtener info del apartado
            layaway = self.core.get_layaway(layaway_id)
            if not layaway: return
            
            balance_due = float(layaway.get('balance_due', 0))
            
            # 2. Solicitar Monto (Default = Liquidación)
            amount, ok = QtWidgets.QInputDialog.getDouble(
                self, 
                "Abonar a Apartado", 
                f"Saldo pendiente: ${balance_due:.2f}\nIngresa monto a pagar:", 
                balance_due, 0, balance_due, 2
            )
            
            if not ok or amount <= 0: return

            # 3. Abrir Diálogo de Pago (PaymentDialog)
            # PaymentDialog(amount, core, parent)
            
            payment_dlg = PaymentDialog(amount, self.core, self)
            if payment_dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                payment_data = payment_dlg.result_data
                
                # 4. Procesar pago en Core
                new_status = self.core.add_layaway_payment(layaway_id, amount, payment_data)
                
                msg = "Abono registrado correctamente."
                if new_status == 'completed':
                    msg = "¡Apartado LIQUIDADO y completado!"
                
                QtWidgets.QMessageBox.information(self, "Éxito", msg)
                
                # 5. Imprimir Ticket de Abono
                try:
                    ticket_engine.print_layaway_ticket(self.core, layaway_id, payment_data, amount)
                except Exception as e:
                    print(f"Error printing ticket: {e}")
                    # Non-blocking warning
                    logging.error(f"Error ticket: {e}")

                self.refresh_data()
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al procesar pago: {e}")

    def _show_details(self, layaway_id):
        """Muestra los productos de un apartado"""
        try:
            items = self.core.get_layaway_items(layaway_id)
            if not items:
                QtWidgets.QMessageBox.information(self, "Sin items", "Este apartado no tiene productos registrados.")
                return
                
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle(f"Detalles Apartado #{layaway_id}")
            dlg.setMinimumWidth(500)
            
            layout = QtWidgets.QVBoxLayout(dlg)
            
            table = QtWidgets.QTableWidget(len(items), 4)
            table.setHorizontalHeaderLabels(["Producto", "Cant", "Precio", "Total"])
            table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            
            for i, item in enumerate(items):
                i_dict = dict(item)
                # Fetch product name if missing (assuming get_layaway_items joins or returns product_id)
                p_name = i_dict.get('name') or i_dict.get('product_name') or f"Producto {i_dict.get('product_id')}"
                
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(p_name))
                table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(i_dict.get('qty'))))
                table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"${float(i_dict.get('price')):,.2f}"))
                table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"${float(i_dict.get('total')):,.2f}"))
            
            layout.addWidget(table)
            
            btn_close = QtWidgets.QPushButton("Cerrar")
            btn_close.clicked.connect(dlg.accept)
            layout.addWidget(btn_close)
            
            dlg.exec()
            
        except Exception as e:
            print(f"Error showing details: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"No se pudieron cargar los detalles: {e}")

    def _cancel_layaway(self, layaway_id, customer_name, total):
        """Cancelar un apartado - requiere autorización de supervisor"""
        try:
            # Verificar autorización
            from app.core import STATE
            current_role = getattr(STATE, 'role', 'cashier').lower()
            
            if current_role == 'cashier':
                from app.dialogs.supervisor_override_dialog import require_supervisor_override
                
                authorized, supervisor = require_supervisor_override(
                    core=self.core,
                    action_description=f"Cancelar Apartado #{layaway_id}\nCliente: {customer_name}\nTotal: ${total:,.2f}",
                    required_permission="cancel_layaway",
                    min_role="encargado",
                    parent=self
                )
                
                if not authorized:
                    return
            
            # Confirmar cancelación
            confirm = QtWidgets.QMessageBox.question(
                self,
                "Confirmar Cancelación",
                f"¿Está seguro de CANCELAR el apartado #{layaway_id}?\n\n"
                f"Cliente: {customer_name}\n"
                f"Total: ${total:,.2f}\n\n"
                "⚠️ Esta acción no se puede deshacer.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            
            if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            
            # Solicitar motivo
            reason, ok = QtWidgets.QInputDialog.getText(
                self,
                "Motivo de Cancelación",
                "Ingrese el motivo de la cancelación:"
            )
            
            if not ok:
                return
            
            # Ejecutar cancelación
            success = self.core.cancel_layaway(layaway_id, reason or "Sin especificar")
            
            if success:
                QtWidgets.QMessageBox.information(
                    self,
                    "Apartado Cancelado",
                    f"El apartado #{layaway_id} ha sido cancelado."
                )
                self.refresh_data()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo cancelar el apartado."
                )
                
        except Exception as e:
            print(f"Error cancelling layaway: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al cancelar: {e}")

    def update_theme(self):
        pass
