"""
Protected Table Delegates - Blindaje de Celdas Críticas
Delegate que protege campos críticos con confirmación antes de editar.

Uso:
    table.setItemDelegateForColumn(0, ProtectedDelegate(table))  # ID - ReadOnly
    table.setItemDelegateForColumn(3, ConfirmEditDelegate(table, "stock"))  # Stock - Confirm
"""

from typing import List, Optional
import logging

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStyledItemDelegate,
    QWidget,
)

logger = logging.getLogger(__name__)

class ProtectedDelegate(QStyledItemDelegate):
    """
    Delegate ReadOnly absoluto.
    
    Uso: Para columnas que NUNCA deben editarse (ID, SKU, Stock Fiscal).
    
    Ejemplo:
        table.setItemDelegateForColumn(0, ProtectedDelegate(table))
    """
    
    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> None:
        """No crear editor = campo no editable."""
        return None
    
    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        """No hacer nada."""
        pass
    
    def setModelData(self, editor: QWidget, model: QAbstractItemModel, 
                      index: QModelIndex) -> None:
        """No guardar nada."""
        pass

class ConfirmEditDelegate(QStyledItemDelegate):
    """
    Delegate con confirmación antes de editar.
    
    Requiere doble-click + confirmación en cuadro de diálogo.
    
    Uso:
        delegate = ConfirmEditDelegate(table, "precio")
        table.setItemDelegateForColumn(2, delegate)
    """
    
    def __init__(self, parent: QWidget = None, field_name: str = "campo",
                 require_reason: bool = False):
        """
        Args:
            parent: Widget padre
            field_name: Nombre del campo (para mensaje de confirmación)
            require_reason: Si True, pide motivo del cambio
        """
        super().__init__(parent)
        self.field_name = field_name
        self.require_reason = require_reason
        self._pending_edit = None
    
    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> Optional[QWidget]:
        """Crear editor solo después de confirmación."""
        current_value = index.data(Qt.ItemDataRole.DisplayRole)
        
        # Mostrar confirmación
        reply = QMessageBox.question(
            parent.window(),
            "⚠️ Confirmar Edición",
            f"¿Deseas modificar el {self.field_name}?\n\n"
            f"Valor actual: {current_value}\n\n"
            f"Esta acción quedará registrada en auditoría.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return None
        
        # Si requiere motivo
        if self.require_reason:
            from PyQt6.QtWidgets import QInputDialog
            reason, ok = QInputDialog.getText(
                parent.window(),
                "Motivo del Cambio",
                f"¿Por qué modificas el {self.field_name}?"
            )
            if not ok or not reason.strip():
                return None
            self._pending_edit = {'reason': reason}
        
        # Determinar tipo de editor basado en el valor actual
        try:
            float(current_value)
            editor = QDoubleSpinBox(parent)
            editor.setRange(-999999, 999999)
            editor.setDecimals(2)
            return editor
        except (ValueError, TypeError):
            editor = QLineEdit(parent)
            return editor
    
    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        """Cargar valor actual en el editor."""
        value = index.data(Qt.ItemDataRole.EditRole)
        
        if isinstance(editor, QDoubleSpinBox):
            try:
                editor.setValue(float(value or 0))
            except (ValueError, TypeError):
                editor.setValue(0)
        elif isinstance(editor, QLineEdit):
            editor.setText(str(value or ""))
    
    def setModelData(self, editor: QWidget, model: QAbstractItemModel, 
                      index: QModelIndex) -> None:
        """Guardar valor con auditoría."""
        old_value = index.data(Qt.ItemDataRole.DisplayRole)
        
        if isinstance(editor, QDoubleSpinBox):
            new_value = editor.value()
        elif isinstance(editor, QLineEdit):
            new_value = editor.text()
        else:
            return
        
        if str(old_value) == str(new_value):
            return  # Sin cambios
        
        # Guardar en modelo
        model.setData(index, new_value, Qt.ItemDataRole.EditRole)
        
        # Log de auditoría (si está disponible)
        try:
            from app.utils.audit_logger import get_audit_logger
            audit = get_audit_logger()
            if audit:
                reason = self._pending_edit.get('reason') if self._pending_edit else None
                audit.log(
                    'FIELD_EDIT',
                    'table_cell',
                    entity_name=self.field_name,
                    old_value={'value': old_value},
                    new_value={'value': new_value},
                    details={'reason': reason} if reason else None
                )
        except Exception as e:
            logger.warning(f"Could not log field edit: {e}")
        
        self._pending_edit = None

class PriceEditDelegate(ConfirmEditDelegate):
    """
    Delegate especializado para precios.
    
    Valida que el precio sea positivo y razonable.
    """
    
    def __init__(self, parent: QWidget = None, max_price: float = 999999):
        super().__init__(parent, field_name="precio", require_reason=True)
        self.max_price = max_price
    
    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> Optional[QWidget]:
        """Crear editor de precio con validación."""
        editor = super().createEditor(parent, option, index)
        
        if isinstance(editor, QDoubleSpinBox):
            editor.setRange(0.01, self.max_price)
            editor.setPrefix("$")
            editor.setDecimals(2)
        
        return editor

class StockEditDelegate(ConfirmEditDelegate):
    """
    Delegate especializado para ajustes de stock.
    
    SIEMPRE requiere motivo y confirma con advertencia.
    """
    
    def __init__(self, parent: QWidget = None, allow_negative: bool = False):
        super().__init__(parent, field_name="stock", require_reason=True)
        self.allow_negative = allow_negative
    
    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> Optional[QWidget]:
        """Crear editor de stock con advertencia extra."""
        current = index.data(Qt.ItemDataRole.DisplayRole)
        
        # Advertencia extra para stock
        reply = QMessageBox.warning(
            parent.window(),
            "⚠️ AJUSTE DE INVENTARIO",
            f"Estás por modificar el STOCK de un producto.\n\n"
            f"Stock actual: {current}\n\n"
            "Esta acción:\n"
            "• Quedará registrada en auditoría\n"
            "• Puede afectar los reportes fiscales\n"
            "• Requiere motivo obligatorio\n\n"
            "¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return None
        
        # Pedir motivo
        from PyQt6.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getText(
            parent.window(),
            "Motivo del Ajuste de Stock",
            "Motivo (requerido):"
        )
        
        if not ok or not reason.strip():
            QMessageBox.warning(
                parent.window(),
                "Error",
                "Se requiere un motivo para ajustar el stock."
            )
            return None
        
        self._pending_edit = {'reason': reason}
        
        # Crear editor numérico
        editor = QDoubleSpinBox(parent)
        editor.setDecimals(2)
        if self.allow_negative:
            editor.setRange(-999999, 999999)
        else:
            editor.setRange(0, 999999)
        
        return editor

def setup_protected_table(table, protected_columns: List[int], 
                          price_columns: List[int] = None,
                          stock_columns: List[int] = None):
    """
    Configura protección de tabla con delegates apropiados.
    
    Args:
        table: QTableWidget o QTableView
        protected_columns: Columnas ReadOnly (ID, SKU, etc)
        price_columns: Columnas de precio (con confirmación + motivo)
        stock_columns: Columnas de stock (con advertencia máxima)
    
    Ejemplo:
        setup_protected_table(
            self.products_table,
            protected_columns=[0, 1],  # ID, SKU
            price_columns=[3],         # Precio
            stock_columns=[4]          # Stock
        )
    """
    # Columnas protegidas (ReadOnly)
    for col in protected_columns:
        table.setItemDelegateForColumn(col, ProtectedDelegate(table))
    
    # Columnas de precio
    if price_columns:
        for col in price_columns:
            table.setItemDelegateForColumn(col, PriceEditDelegate(table))
    
    # Columnas de stock
    if stock_columns:
        for col in stock_columns:
            table.setItemDelegateForColumn(col, StockEditDelegate(table))
    
    logger.info(f"Table protection configured: {len(protected_columns)} protected, "
                f"{len(price_columns or [])} price, {len(stock_columns or [])} stock")

# Ejemplo de uso en una tabla de productos:
"""
from app.utils.table_delegates import setup_protected_table

# En __init__ de ProductsTab:
setup_protected_table(
    self.table,
    protected_columns=[0, 1, 6],  # ID, SKU, Stock Fiscal
    price_columns=[3, 4],          # Precio Venta, Precio Mayoreo
    stock_columns=[5]              # Conteo Físico (editable con confirmación)
)
"""
