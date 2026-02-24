"""
Quick turn close dialog (F10 shortcut).
Shows minimal summary and allows fast turn closing.
"""
from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class QuickTurnCloseDialog(QtWidgets.QDialog):
    """Quick turn close dialog for F10 shortcut.
    
    Features:
    - Fast turn closing without detailed breakdown
    - Shows cash expected vs counted
    - Minimal fields for speed
    """
    
    def __init__(self, core, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Cierre Rápido de Turno (F10)")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._load_turn_data()
        self._build_ui()
        self.update_theme()
    
    def _load_turn_data(self) -> None:
        """Load current turn data."""
        try:
            from app.core import STATE
            self.current_turn = self.core.get_current_turn(STATE.branch_id)
            
            if not self.current_turn:
                raise ValueError("No hay turno abierto")
            
            # Get cash movements
            movements = self.core.get_cash_movements(self.current_turn['id'])
            
            # Calculate expected cash
            initial = float(self.current_turn.get('initial_cash', 0.0))
            entries = sum(float(m.get('amount', 0)) for m in movements if m.get('type') == 'entry')
            exits = sum(float(m.get('amount', 0)) for m in movements if m.get('type') == 'exit')
            
            # Get sales in cash
            sales_cash = self.core.get_turn_sales_by_method(self.current_turn['id'], 'cash')
            total_cash_sales = sum(float(s.get('total', 0)) for s in sales_cash)
            
            self.expected_cash = initial + entries - exits + total_cash_sales
            self.total_sales = float(self.core.get_turn_total_sales(self.current_turn['id']) or 0.0)
            
        except Exception as e:
            self.expected_cash = 0.0
            self.total_sales = 0.0
            print(f"Error loading turn data: {e}")
    
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Title
        title = QtWidgets.QLabel("⚡ Cierre Rápido de Turno")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Summary card
        summary_card = QtWidgets.QFrame()
        summary_layout = QtWidgets.QVBoxLayout(summary_card)
        
        # Total sales
        sales_lbl = QtWidgets.QLabel(f"💰 Ventas Totales: ${self.total_sales:,.2f}")
        sales_lbl.setStyleSheet("font-size: 16px; font-weight: 600; padding: 10px;")
        summary_layout.addWidget(sales_lbl)
        
        # Expected cash
        expected_lbl = QtWidgets.QLabel(f"📊 Efectivo Esperado: ${self.expected_cash:,.2f}")
        expected_lbl.setStyleSheet("font-size: 14px; padding: 10px;")
        summary_layout.addWidget(expected_lbl)
        
        layout.addWidget(summary_card)
        
        # Cash counted input
        counted_layout = QtWidgets.QHBoxLayout()
        counted_layout.addWidget(QtWidgets.QLabel("💵 Efectivo Contado:"))
        
        self.counted_input = QtWidgets.QDoubleSpinBox()
        self.counted_input.setRange(0, 999999)
        self.counted_input.setDecimals(2)
        self.counted_input.setValue(self.expected_cash)
        self.counted_input.setPrefix("$ ")
        self.counted_input.setMinimumWidth(150)
        self.counted_input.valueChanged.connect(self._update_difference)
        counted_layout.addWidget(self.counted_input)
        counted_layout.addStretch()
        
        layout.addLayout(counted_layout)
        
        # Difference indicator
        self.diff_label = QtWidgets.QLabel("✓ Sin diferencia")
        self.diff_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.diff_label.setStyleSheet("font-size: 14px; padding: 10px; font-weight: bold;")
        layout.addWidget(self.diff_label)
        
        # Notes (optional)
        layout.addWidget(QtWidgets.QLabel("📝 Notas (opcional):"))
        self.notes_input = QtWidgets.QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText("Observaciones del cierre...")
        layout.addWidget(self.notes_input)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.cancel_btn = QtWidgets.QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.close_btn = QtWidgets.QPushButton("✓ Cerrar Turno")
        self.close_btn.clicked.connect(self._close_turn)
        self.close_btn.setDefault(True)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        # Initial difference check
        self._update_difference()
    
    def _update_difference(self) -> None:
        """Update difference indicator."""
        counted = self.counted_input.value()
        diff = counted - self.expected_cash
        
        if abs(diff) < 0.01:  # No difference
            self.diff_label.setText("✓ Sin diferencia")
            self.diff_label.setStyleSheet("font-size: 14px; padding: 10px; font-weight: bold; color: #27ae60;")
        elif diff > 0:  # Surplus
            self.diff_label.setText(f"⬆ Sobrante: ${diff:,.2f}")
            self.diff_label.setStyleSheet("font-size: 14px; padding: 10px; font-weight: bold; color: #f39c12;")
        else:  # Shortage
            self.diff_label.setText(f"⬇ Faltante: ${abs(diff):,.2f}")
            self.diff_label.setStyleSheet("font-size: 14px; padding: 10px; font-weight: bold; color: #e74c3c;")
    
    def _close_turn(self) -> None:
        """Close the turn."""
        counted = self.counted_input.value()
        notes = self.notes_input.toPlainText()
        
        # Confirm if there's a difference
        diff = abs(counted - self.expected_cash)
        if diff >= 0.01:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirmar Cierre",
                f"Hay una diferencia de ${diff:,.2f}\n¿Deseas continuar con el cierre?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                return
        
        try:
            from app.core import STATE

            # Close turn
            self.core.close_turn(
                turn_id=self.current_turn['id'],
                final_cash=counted,
                notes=notes
            )
            
            self.accept()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudo cerrar el turno:\n{str(e)}"
            )
    
    def update_theme(self) -> None:
        """Apply theme colors."""
        theme = theme_manager.get_theme()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.get('bg_primary', '#ffffff')};
                color: {theme.get('text_primary', '#2c3e50')};
            }}
            QFrame {{
                background-color: {theme.get('bg_secondary', '#ecf0f1')};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{
                color: {theme.get('text_primary', '#2c3e50')};
                border: none;
            }}
            QPushButton {{
                background-color: {theme.get('btn_primary', '#3498db')};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {theme.get('btn_primary_hover', '#2980b9')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get('btn_primary_pressed', '#21618c')};
            }}
            QDoubleSpinBox, QTextEdit {{
                background-color: {theme.get('input_bg', '#ffffff')};
                color: {theme.get('text_primary', '#2c3e50')};
                border: 2px solid {theme.get('border', '#bdc3c7')};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
