from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import json
import logging
import time

from app.core import STATE, POSCore
from app.utils.path_utils import get_debug_log_path_str, agent_log_enabled
from app.utils.validators import safe_float


class CancelSaleDialog(QDialog):
    def __init__(self, core: POSCore, sale_id: int, parent=None):
        super().__init__(parent)
        self.core = core
        self.sale_id = sale_id
        self.setWindowTitle(f"Cancelar Venta #{sale_id}")
        self.setFixedSize(500, 500)
        self.items_to_cancel = {} # {product_id: qty}
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Apply theme
        from app.utils.theme_manager import theme_manager
        c = theme_manager.get_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QLabel {{
                color: {c['text_primary']};
                background: transparent;
            }}
            QTableWidget {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                gridline-color: {c['border']};
            }}
            QHeaderView::section {{
                background: {c['bg_card']};
                color: {c['text_primary']};
                padding: 8px;
                border: none;
            }}
            QCheckBox {{
                color: {c['text_primary']};
            }}
            QPlainTextEdit {{
                background: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 5px;
            }}
            QPushButton {{
                background: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                padding: 10px 20px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
        """)
        
        layout.addWidget(QLabel("Seleccione los productos a cancelar (Doble clic para editar cantidad):"))
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Producto", "Cant. Orig", "A Cancelar"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)
        
        self.cb_total = QCheckBox("Cancelación Total (Todos los productos)")
        self.cb_total.toggled.connect(self._toggle_total)
        layout.addWidget(self.cb_total)
        
        self.cb_restore = QCheckBox("Restaurar Inventario")
        self.cb_restore.setChecked(True)
        layout.addWidget(self.cb_restore)
        
        layout.addWidget(QLabel("Motivo de la cancelación:"))
        self.reason_edit = QPlainTextEdit()
        self.reason_edit.setPlaceholderText("Ej. Error de cajero, cliente devolvió producto...")
        self.reason_edit.setFixedHeight(60)
        layout.addWidget(self.reason_edit)
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Salir")
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton("Confirmar Cancelación")
        # CRITICAL FIX: Ensure button is enabled and connected properly
        btn_confirm.setEnabled(True)
        btn_confirm.clicked.connect(self._confirm)
        btn_confirm.setStyleSheet("")  # Styled in showEvent
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H0","location":"cancel_sale_dialog.py:_build_ui","message":"Button created and connected","data":{"button_text":btn_confirm.text(),"button_enabled":btn_confirm.isEnabled()},"timestamp":int(time.time()*1000)})+"\n")
            except Exception:
                pass
        # #endregion
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)

    def _load_data(self):
        self.items = self.core.get_sale_items(self.sale_id)
        self.table.setRowCount(len(self.items))
        self.table.blockSignals(True)
        for i, item in enumerate(self.items):
            self.table.setItem(i, 0, QTableWidgetItem(item.get("name", "")))
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get("qty", 0))))
            
            qty_item = QTableWidgetItem("0")
            qty_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, qty_item)
            
            # Store original qty in user role
            qty_item.setData(Qt.ItemDataRole.UserRole, float(item.get("qty", 0)))
            qty_item.setData(Qt.ItemDataRole.UserRole + 1, item.get("product_id"))
            
        self.table.blockSignals(False)

    def _toggle_total(self, checked):
        self.table.blockSignals(True)
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 2)
            orig_qty = item.data(Qt.ItemDataRole.UserRole)
            item.setText(str(orig_qty) if checked else "0")
        self.table.setEnabled(not checked)
        self.table.blockSignals(False)

    def _on_item_changed(self, item):
        if item.column() != 2: return
        self.table.blockSignals(True)
        try:
            val = float(item.text())
            max_qty = item.data(Qt.ItemDataRole.UserRole)
            if val < 0: item.setText("0")
            if val > max_qty: item.setText(str(max_qty))
        except ValueError:
            item.setText("0")
        finally:
            self.table.blockSignals(False)

    def _confirm(self):
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"cancel_sale_dialog.py:_confirm","message":"Function entry","data":{"sale_id":self.sale_id,"items_count":len(self.items) if hasattr(self, 'items') else 0},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as log_err:
                # Log error but don't block execution
                print(f"DEBUG LOG ERROR: {log_err}")
        # #endregion
        reason = self.reason_edit.toPlainText().strip()
        if not reason:
            QMessageBox.warning(self, "Error", "Debe ingresar un motivo")
            return
            
        cancel_data = []
        total_refund = 0.0
        
        for i in range(self.table.rowCount()):
            qty_item = self.table.item(i, 2)
            cancel_qty = safe_float(qty_item.text(), default=0.0)
            if cancel_qty > 0:
                prod_id = qty_item.data(Qt.ItemDataRole.UserRole + 1)
                # Find price
                price = 0.0
                for it in self.items:
                    if it["product_id"] == prod_id:
                        price = safe_float(it.get("price"), default=0.0)
                        break
                
                cancel_data.append({
                    "product_id": prod_id,
                    "qty": cancel_qty,
                    "price": price
                })
                total_refund += (cancel_qty * price)
        
        # #region agent log
        if agent_log_enabled():
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"cancel_sale_dialog.py:_confirm","message":"Cancel data prepared","data":{"sale_id":self.sale_id,"cancel_data_count":len(cancel_data),"total_refund":total_refund,"restore_inventory":self.cb_restore.isChecked()},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as log_err:
                print(f"DEBUG LOG ERROR: {log_err}")
        # #endregion
        
        if not cancel_data:
            QMessageBox.warning(self, "Error", "No hay productos a cancelar")
            return
            
        try:
            self.core.cancel_sale(
                sale_id=self.sale_id,
                items=cancel_data,
                reason=reason,
                restore_inventory=self.cb_restore.isChecked(),
                refund_amount=total_refund,
                user_id=STATE.user_id,
                branch_id=STATE.branch_id
            )
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H3","location":"cancel_sale_dialog.py:_confirm","message":"Cancel sale succeeded","data":{"sale_id":self.sale_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_err:
                    print(f"DEBUG LOG ERROR: {log_err}")
            # #endregion
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H5","location":"cancel_sale_dialog.py:_confirm","message":"About to show success message","data":{"sale_id":self.sale_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_err:
                    print(f"DEBUG LOG ERROR: {log_err}")
            # #endregion
            
            # Abrir cajón después de cancelar venta
            try:
                from app.utils.ticket_engine import open_cash_drawer_safe
                open_cash_drawer_safe(core=self.core)
            except Exception as e:
                logging.warning(f"No se pudo abrir cajón después de cancelar venta: {e}")
            
            QMessageBox.information(self, "Éxito", "Venta cancelada correctamente")
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H6","location":"cancel_sale_dialog.py:_confirm","message":"Success message shown, about to accept","data":{"sale_id":self.sale_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_err:
                    print(f"DEBUG LOG ERROR: {log_err}")
            # #endregion
            self.accept()
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H7","location":"cancel_sale_dialog.py:_confirm","message":"Dialog accept() called","data":{"sale_id":self.sale_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_err:
                    print(f"DEBUG LOG ERROR: {log_err}")
            # #endregion
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H4","location":"cancel_sale_dialog.py:_confirm","message":"Cancel sale failed","data":{"sale_id":self.sale_id,"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_err:
                    print(f"DEBUG LOG ERROR: {log_err}")
            # #endregion
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"No se pudo cancelar: {e}\n\nDetalles:\n{error_details[:500]}")

    def showEvent(self, event):
        """Apply theme colors"""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            # Apply theme to buttons
            for btn in self.findChildren(QPushButton):
                text = btn.text().lower()
                if any(word in text for word in ['guardar', 'save', 'crear', 'create']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['eliminar', 'delete', 'cancelar', 'cancel', 'confirmar']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['restaurar', 'restore']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['agregar', 'add']):
                    btn.setStyleSheet(f"background: {c['btn_primary']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception as e:
            pass  # Silently fail if theme_manager not available

