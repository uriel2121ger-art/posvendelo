"""
Dialog for selling products in package units.
Allows selling products in specific package quantities (e.g., caja de 12, paquete de 6).
"""
from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class PackageSaleDialog(QtWidgets.QDialog):
    """
    Dialog for selling products by package.
    
    Features:
    - Define package size (units per package)
    - Calculate total units from package quantity
    - Price per package vs price per unit
    - Common presets (6-pack, 12-pack, 24-pack)
    """
    
    def __init__(self, product: dict[str, Any], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.product = product
        self.result_qty = 0.0
        self.package_size = 1
        self.package_count = 1
        
        self.setWindowTitle(f"Venta por Paquete - {product.get('name', 'Producto')}")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        
        self._build_ui()
        self.update_theme()
        
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Header
        header = QtWidgets.QLabel(f"📦 {self.product.get('name', 'Producto')}")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)
        
        price_label = QtWidgets.QLabel(f"Precio unitario: ${self.product.get('price', 0.0):.2f}")
        price_label.setStyleSheet("font-size: 14px; color: #7f8c8d;")
        layout.addWidget(price_label)
        
        # Package Size Selection
        package_group = QtWidgets.QGroupBox("Tamaño del Paquete")
        package_layout = QtWidgets.QVBoxLayout(package_group)
        
        # Quick presets
        presets_layout = QtWidgets.QHBoxLayout()
        presets_label = QtWidgets.QLabel("Presets comunes:")
        presets_layout.addWidget(presets_label)
        
        preset_btns = []
        for size in [6, 12, 24]:
            btn = QtWidgets.QPushButton(f"{size} unidades")
            btn.setFixedWidth(100)
            btn.clicked.connect(lambda checked, s=size: self._set_package_size(s))
            preset_btns.append(btn)
            presets_layout.addWidget(btn)
            
        presets_layout.addStretch()
        package_layout.addLayout(presets_layout)
        
        # Custom package size
        custom_layout = QtWidgets.QFormLayout()
        
        self.package_size_input = QtWidgets.QSpinBox()
        self.package_size_input.setRange(1, 1000)
        self.package_size_input.setValue(1)
        self.package_size_input.setSuffix(" unidades")
        self.package_size_input.setFixedHeight(35)
        self.package_size_input.valueChanged.connect(self._update_preview)
        
        custom_layout.addRow("Unidades por paquete:", self.package_size_input)
        package_layout.addLayout(custom_layout)
        
        layout.addWidget(package_group)
        
        # Package Quantity
        qty_group = QtWidgets.QGroupBox("Cantidad a Vender")
        qty_layout = QtWidgets.QFormLayout(qty_group)
        
        self.package_count_input = QtWidgets.QSpinBox()
        self.package_count_input.setRange(1, 10000)
        self.package_count_input.setValue(1)
        self.package_count_input.setSuffix(" paquetes")
        self.package_count_input.setFixedHeight(35)
        self.package_count_input.valueChanged.connect(self._update_preview)
        
        qty_layout.addRow("Paquetes:", self.package_count_input)
        layout.addWidget(qty_group)
        
        # Preview
        preview_card = QtWidgets.QFrame()
        preview_card.setFrameShape(QtWidgets.QFrame.Shape.Box)
        preview_layout = QtWidgets.QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(20, 15, 20, 15)
        
        preview_header = QtWidgets.QLabel("📊 Resumen")
        preview_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        preview_layout.addWidget(preview_header)
        
        self.total_units_label = QtWidgets.QLabel("Total de unidades: 1")
        self.total_units_label.setStyleSheet("font-size: 13px;")
        
        self.total_price_label = QtWidgets.QLabel(f"Total: ${self.product.get('price', 0.0):.2f}")
        self.total_price_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60;")
        
        self.unit_price_label = QtWidgets.QLabel(
            f"Precio por unidad: ${self.product.get('price', 0.0):.2f}"
        )
        self.unit_price_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        
        preview_layout.addWidget(self.total_units_label)
        preview_layout.addWidget(self.total_price_label)
        preview_layout.addWidget(self.unit_price_label)
        
        layout.addWidget(preview_card)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        
        accept_btn = QtWidgets.QPushButton("Agregar al Carrito")
        accept_btn.setFixedHeight(40)
        accept_btn.setFixedWidth(160)
        accept_btn.setDefault(True)
        accept_btn.clicked.connect(self._accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(accept_btn)
        layout.addLayout(btn_layout)
        
        self._update_preview()
        
    def _set_package_size(self, size: int) -> None:
        """Set package size from preset button."""
        self.package_size_input.setValue(size)
        
    def _update_preview(self) -> None:
        """Update the preview calculations."""
        package_size = self.package_size_input.value()
        package_count = self.package_count_input.value()
        
        total_units = package_size * package_count
        unit_price = float(self.product.get('price', 0.0))
        total_price = total_units * unit_price
        
        self.total_units_label.setText(
            f"Total de unidades: {total_units:,} ({package_count} paquete{'s' if package_count != 1 else ''} × {package_size} unidades)"
        )
        self.total_price_label.setText(f"Total: ${total_price:,.2f}")
        self.unit_price_label.setText(f"Precio por unidad: ${unit_price:.2f}")
        
    def _accept(self) -> None:
        """Accept and calculate result quantity."""
        package_size = self.package_size_input.value()
        package_count = self.package_count_input.value()
        
        self.result_qty = float(package_size * package_count)
        self.package_size = package_size
        self.package_count = package_count
        
        self.accept()
        
    def update_theme(self) -> None:
        """Apply theme colors to the dialog."""
        theme = theme_manager.get_theme()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme['bg']};
                color: {theme['fg']};
            }}
            QGroupBox {{
                border: 1px solid {theme['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QFrame {{
                background-color: {theme['card']};
                border: 1px solid {theme['border']};
                border-radius: 8px;
            }}
            QSpinBox {{
                background-color: {theme['input_bg']};
                color: {theme['input_fg']};
                border: 1px solid {theme['border']};
                border-radius: 4px;
                padding: 8px;
            }}
            QSpinBox:focus {{
                border: 2px solid {theme['btn_primary']};
            }}
            QPushButton {{
                background-color: {theme['btn_primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
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
