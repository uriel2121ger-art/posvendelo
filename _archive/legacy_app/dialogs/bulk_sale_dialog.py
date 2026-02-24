"""
Dialog for selling bulk/weight products.
Supports two modes:
1. By Weight: Enter weight (kg) → calculates total
2. By Amount: Enter desired amount ($) → calculates weight
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class BulkSaleDialog(QtWidgets.QDialog):
    """
    Dialog for bulk product sales with dual input modes.
    
    Mode 1 - By Weight: User enters weight, calculates total price
    Mode 2 - By Amount: User enters desired price, calculates weight
    """
    
    def __init__(self, product: dict[str, Any], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.product = product
        self.result_qty = 0.0
        self.result_mode = "weight"  # "weight" or "amount"
        
        self.setWindowTitle(f"Venta a Granel - {product.get('name', '')}")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self._build_ui()
        self.update_theme()
        
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Product Info
        info_card = QtWidgets.QFrame()
        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        product_name = QtWidgets.QLabel(f"📦 {self.product.get('name', 'Producto')}")
        product_name.setStyleSheet("font-size: 16px; font-weight: bold;")

        # Use Decimal for monetary calculations
        price_per_unit = float(Decimal(str(self.product.get('price', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        price_label = QtWidgets.QLabel(f"Precio por kg: ${price_per_unit:.2f}")
        price_label.setStyleSheet("font-size: 14px; color: #7f8c8d;")
        
        info_layout.addWidget(product_name)
        info_layout.addWidget(price_label)
        layout.addWidget(info_card)
        
        # Mode Selection
        mode_group = QtWidgets.QGroupBox("Modo de Venta")
        mode_layout = QtWidgets.QVBoxLayout(mode_group)
        
        self.mode_by_weight = QtWidgets.QRadioButton("Venta por Peso (kg)")
        self.mode_by_weight.setChecked(True)
        self.mode_by_weight.toggled.connect(self._on_mode_changed)
        
        self.mode_by_amount = QtWidgets.QRadioButton("Venta por Importe ($)")
        self.mode_by_amount.toggled.connect(self._on_mode_changed)
        
        mode_layout.addWidget(self.mode_by_weight)
        mode_layout.addWidget(self.mode_by_amount)
        layout.addWidget(mode_group)
        
        # Input Section
        input_group = QtWidgets.QGroupBox()
        input_layout = QtWidgets.QFormLayout(input_group)
        input_layout.setSpacing(15)
        
        # Weight Input
        self.weight_input = QtWidgets.QDoubleSpinBox()
        self.weight_input.setRange(0.001, 9999.999)
        self.weight_input.setDecimals(3)
        self.weight_input.setValue(1.000)
        self.weight_input.setSuffix(" kg")
        self.weight_input.setFixedHeight(40)
        self.weight_input.valueChanged.connect(self._update_preview)
        
        # Amount Input
        self.amount_input = QtWidgets.QDoubleSpinBox()
        self.amount_input.setRange(0.01, 999999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(price_per_unit)
        self.amount_input.setPrefix("$ ")
        self.amount_input.setFixedHeight(40)
        self.amount_input.valueChanged.connect(self._update_preview)
        self.amount_input.setEnabled(False)
        
        input_layout.addRow("Peso:", self.weight_input)
        input_layout.addRow("Importe:", self.amount_input)
        layout.addWidget(input_group)
        
        # Preview/Calculation
        self.preview_card = QtWidgets.QFrame()
        preview_layout = QtWidgets.QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(15, 15, 15, 15)
        
        self.calculation_label = QtWidgets.QLabel()
        self.calculation_label.setStyleSheet("font-size: 13px; font-family: monospace;")
        self.calculation_label.setWordWrap(True)
        
        self.result_label = QtWidgets.QLabel()
        self.result_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60;")
        self.result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        preview_layout.addWidget(QtWidgets.QLabel("Cálculo:"))
        preview_layout.addWidget(self.calculation_label)
        preview_layout.addSpacing(10)
        preview_layout.addWidget(self.result_label)
        layout.addWidget(self.preview_card)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        
        accept_btn = QtWidgets.QPushButton("Aceptar")
        accept_btn.setFixedHeight(40)
        accept_btn.setFixedWidth(120)
        accept_btn.setDefault(True)
        accept_btn.clicked.connect(self._accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(accept_btn)
        layout.addLayout(btn_layout)
        
        # Initial preview
        self._update_preview()
        
        # Focus
        self.weight_input.setFocus()
        self.weight_input.selectAll()
        
    def _on_mode_changed(self) -> None:
        """Toggle between weight and amount input modes."""
        by_weight = self.mode_by_weight.isChecked()
        
        self.weight_input.setEnabled(by_weight)
        self.amount_input.setEnabled(not by_weight)
        
        if by_weight:
            self.weight_input.setFocus()
            self.weight_input.selectAll()
        else:
            self.amount_input.setFocus()
            self.amount_input.selectAll()
            
        self._update_preview()
        
    def _update_preview(self) -> None:
        """Update the calculation preview based on current mode and values."""
        price_per_kg = float(Decimal(str(self.product.get('price', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
        if self.mode_by_weight.isChecked():
            # Mode 1: Calculate total from weight
            weight = self.weight_input.value()
            total = weight * price_per_kg
            
            self.calculation_label.setText(
                f"{weight:.3f} kg × ${price_per_kg:.2f}/kg = ${total:.2f}"
            )
            self.result_label.setText(f"Total: ${total:.2f}")
            
        else:
            # Mode 2: Calculate weight from amount
            amount = self.amount_input.value()
            
            if price_per_kg > 0:
                weight = amount / price_per_kg
                self.calculation_label.setText(
                    f"${amount:.2f} ÷ ${price_per_kg:.2f}/kg = {weight:.3f} kg"
                )
                self.result_label.setText(f"Peso: {weight:.3f} kg")
            else:
                self.calculation_label.setText("Error: Precio por kg es 0")
                self.result_label.setText("Error")
                
    def _accept(self) -> None:
        """Save the result and close dialog."""
        price_per_kg = float(Decimal(str(self.product.get('price', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
        if self.mode_by_weight.isChecked():
            # Result is the weight entered
            self.result_qty = self.weight_input.value()
            self.result_mode = "weight"
        else:
            # Result is the calculated weight from amount
            if price_per_kg > 0:
                amount = self.amount_input.value()
                self.result_qty = amount / price_per_kg
                self.result_mode = "amount"
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "El precio por kg debe ser mayor a 0"
                )
                return
                
        if self.result_qty <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Cantidad Inválida",
                "La cantidad debe ser mayor a 0"
            )
            return
            
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
            QRadioButton {{
                padding: 5px;
                font-size: 13px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
            }}
            QDoubleSpinBox {{
                border: 1px solid {theme['border']};
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
                background-color: {theme['input_bg']};
                color: {theme['input_fg']};
            }}
            QDoubleSpinBox:focus {{
                border: 2px solid {theme['btn_primary']};
            }}
            QDoubleSpinBox:disabled {{
                background-color: {theme['bg']};
                color: {theme['muted']};
            }}
            QPushButton {{
                background-color: {theme['btn_primary']};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
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

    def closeEvent(self, event):
        """Cleanup on close."""
        super().closeEvent(event)
