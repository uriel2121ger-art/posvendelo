"""
Dialog for creating and editing KIT products (bundled products).
Allows adding/removing components and setting quantities.
"""
from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class KitEditorDialog(QtWidgets.QDialog):
    """
    Dialog for managing KIT product components.
    
    Features:
    - Add/remove components
    - Set quantities for each component
    - Auto-calculate suggested price
    - Validate no recursive KITs
    """
    
    def __init__(self, core, kit_product: dict[str, Any], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.kit_product = kit_product
        self.components = []
        
        self.setWindowTitle(f"Editar KIT - {kit_product.get('name', 'Producto')}")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        
        self._build_ui()
        self._load_components()
        self.update_theme()
        
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header Info
        header = QtWidgets.QLabel(f"📦 {self.kit_product.get('name', 'KIT')}")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        
        # Components Table
        table_label = QtWidgets.QLabel("Componentes del KIT:")
        table_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(table_label)
        
        self.components_table = QtWidgets.QTableWidget(0, 5)
        self.components_table.setHorizontalHeaderLabels([
            "SKU", "Nombre", "Precio Unit.", "Cantidad", "Subtotal"
        ])
        self.components_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.components_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.components_table.setMinimumHeight(250)
        layout.addWidget(self.components_table)
        
        # Action Buttons for Table
        table_actions = QtWidgets.QHBoxLayout()
        
        self.add_component_btn = QtWidgets.QPushButton("+ Agregar Componente")
        self.add_component_btn.clicked.connect(self._add_component)
        self.add_component_btn.setFixedHeight(35)
        
        self.remove_component_btn = QtWidgets.QPushButton("- Eliminar Seleccionado")
        self.remove_component_btn.clicked.connect(self._remove_component)
        self.remove_component_btn.setFixedHeight(35)
        
        self.edit_qty_btn = QtWidgets.QPushButton("✏ Editar Cantidad")
        self.edit_qty_btn.clicked.connect(self._edit_quantity)
        self.edit_qty_btn.setFixedHeight(35)
        
        table_actions.addWidget(self.add_component_btn)
        table_actions.addWidget(self.edit_qty_btn)
        table_actions.addWidget(self.remove_component_btn)
        table_actions.addStretch()
        layout.addLayout(table_actions)
        
        # Price Summary
        price_card = QtWidgets.QFrame()
        price_layout = QtWidgets.QHBoxLayout(price_card)
        price_layout.setContentsMargins(15, 10, 15, 10)
        
        self.suggested_price_label = QtWidgets.QLabel("Precio Sugerido (suma componentes): $0.00")
        self.suggested_price_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #27ae60;")
        
        self.current_price_label = QtWidgets.QLabel(
            f"Precio Actual del KIT: ${self.kit_product.get('price', 0.0):.2f}"
        )
        self.current_price_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        
        price_layout.addWidget(self.suggested_price_label)
        price_layout.addStretch()
        price_layout.addWidget(self.current_price_label)
        
        layout.addWidget(price_card)
        
        # Bottom Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        apply_suggested_btn = QtWidgets.QPushButton("Aplicar Precio Sugerido")
        apply_suggested_btn.clicked.connect(self._apply_suggested_price)
        apply_suggested_btn.setFixedHeight(35)
        apply_suggested_btn.setFixedWidth(180)
        
        save_btn = QtWidgets.QPushButton("Guardar y Cerrar")
        save_btn.setFixedHeight(35)
        save_btn.setFixedWidth(150)
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.setFixedHeight(35)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(apply_suggested_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def _load_components(self) -> None:
        """Load existing components from database."""
        try:
            self.components = self.core.get_kit_items(self.kit_product.get('id'))
            self._refresh_table()
        except Exception as e:
            print(f"Error loading kit components: {e}")
            self.components = []
            
    def _refresh_table(self) -> None:
        """Refresh the components table."""
        self.components_table.setRowCount(len(self.components))
        
        total_suggested = 0.0
        
        for row_idx, component in enumerate(self.components):
            qty = float(component.get('qty', 1.0))
            price = float(component.get('price', 0.0))
            subtotal = qty * price
            total_suggested += subtotal
            
            items = [
                component.get('sku', ''),
                component.get('name', ''),
                f"${price:.2f}",
                f"{qty:.2f}",
                f"${subtotal:.2f}"
            ]
            
            for col_idx, text in enumerate(items):
                item = QtWidgets.QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.components_table.setItem(row_idx, col_idx, item)
                
        self.suggested_price_label.setText(f"Precio Sugerido (suma componentes): ${total_suggested:.2f}")
        self._suggested_price = total_suggested
        
    def _add_component(self) -> None:
        """Open product search to add a component."""
        from app.dialogs.product_search import ProductSearchDialog
        
        dialog = ProductSearchDialog(core=self.core, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_product:
            product = dialog.selected_product
            
            # Validate not a KIT
            if product.get('sale_type') == 'kit':
                QtWidgets.QMessageBox.warning(
                    self,
                    "Producto Inválido",
                    "No puedes agregar un KIT como componente de otro KIT."
                )
                return
                
            # Check if already in list
            product_id = product.get('id') or product.get('product_id')
            if any(c.get('child_product_id') == product_id for c in self.components):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Componente Duplicado",
                    "Este producto ya está en la lista de componentes."
                )
                return
                
            # Ask for quantity
            qty, ok = QtWidgets.QInputDialog.getDouble(
                self,
                "Cantidad",
                f"¿Cuántas unidades de '{product.get('name')}' por cada KIT?",
                value=1.0,
                min=0.001,
                decimals=3
            )
            
            if not ok:
                return
                
            # Add to database
            try:
                self.core.add_kit_component(
                    self.kit_product.get('id'),
                    product_id,
                    qty
                )
                
                # Reload components
                self._load_components()
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo agregar el componente: {e}"
                )
                
    def _remove_component(self) -> None:
        """Remove selected component."""
        selected_rows = self.components_table.selectedIndexes()
        if not selected_rows:
            QtWidgets.QMessageBox.information(
                self,
                "Sin Selección",
                "Selecciona un componente para eliminar."
            )
            return
            
        row = selected_rows[0].row()
        component = self.components[row]
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Eliminar '{component.get('name')}' del KIT?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                self.core.remove_kit_component(
                    self.kit_product.get('id'),
                    component.get('child_product_id')
                )
                self._load_components()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo eliminar el componente: {e}"
                )
                
    def _edit_quantity(self) -> None:
        """Edit quantity of selected component."""
        selected_rows = self.components_table.selectedIndexes()
        if not selected_rows:
            QtWidgets.QMessageBox.information(
                self,
                "Sin Selección",
                "Selecciona un componente para editar su cantidad."
            )
            return
            
        row = selected_rows[0].row()
        component = self.components[row]
        current_qty = float(component.get('qty', 1.0))
        
        new_qty, ok = QtWidgets.QInputDialog.getDouble(
            self,
            "Editar Cantidad",
            f"Nueva cantidad para '{component.get('name')}':",
            value=current_qty,
            min=0.001,
            decimals=3
        )
        
        if ok and new_qty != current_qty:
            try:
                self.core.update_kit_component_qty(
                    self.kit_product.get('id'),
                    component.get('child_product_id'),
                    new_qty
                )
                self._load_components()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo actualizar la cantidad: {e}"
                )
                
    def _apply_suggested_price(self) -> None:
        """Apply the suggested price to the KIT product."""
        if not hasattr(self, '_suggested_price'):
            return
            
        reply = QtWidgets.QMessageBox.question(
            self,
            "Aplicar Precio Sugerido",
            f"¿Cambiar el precio del KIT a ${self._suggested_price:.2f}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                self.core.update_product(
                    self.kit_product.get('id'),
                    {"price": self._suggested_price}
                )
                self.kit_product['price'] = self._suggested_price
                self.current_price_label.setText(f"Precio Actual del KIT: ${self._suggested_price:.2f}")
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Precio Actualizado",
                    "El precio del KIT se actualizó correctamente."
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo actualizar el precio: {e}"
                )
                
    def update_theme(self) -> None:
        """Apply theme colors to the dialog."""
        theme = theme_manager.get_theme()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme['bg']};
                color: {theme['fg']};
            }}
            QFrame {{
                background-color: {theme['card']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
            }}
            QTableWidget {{
                background-color: {theme['bg']};
                alternate-background-color: {theme['card']};
                border: 1px solid {theme['border']};
                gridline-color: {theme['border']};
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QHeaderView::section {{
                background-color: {theme['header_bg']};
                color: {theme['header_fg']};
                padding: 8px;
                border: none;
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {theme['btn_primary']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme['btn_primary_hover']};
            }}
            QPushButton:pressed {{
                background-color: {theme['btn_primary_pressed']};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
