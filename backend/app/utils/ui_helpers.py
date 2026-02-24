"""
UI Helper Utilities

Provides reusable UI components and styling functions for consistent
appearance across all tabs in the TITAN POS application.
"""

from typing import Any, Dict, List

from PyQt6 import QtCore, QtGui, QtWidgets

from app.utils import theme_manager


def create_card(title: str, value: str, color: str, theme_colors: Dict[str, str]) -> QtWidgets.QFrame:
    """
    Create a standardized summary card widget.
    
    Args:
        title: Card title text
        value: Card value text (will be displayed prominently)
        color: Border color (hex code)
        theme_colors: Dictionary of theme colors from theme_manager
        
    Returns:
        QFrame widget configured as a summary card
        
    Example:
        >>> c = theme_manager.get_colors("Light")
        >>> card = create_card("Total Sales", "$1,234.56", "#4CAF50", c)
    """
    card = QtWidgets.QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {theme_colors['bg_card']};
            border: 1px solid {theme_colors['border']};
            border-radius: 10px;
            border-left: 5px solid {color};
        }}
    """)
    
    layout = QtWidgets.QVBoxLayout(card)
    layout.setSpacing(5)
    layout.setContentsMargins(15, 10, 15, 10)
    
    title_label = QtWidgets.QLabel(title)
    title_label.setStyleSheet(f"""
        color: {theme_colors['text_secondary']};
        font-size: 13px;
        font-weight: 600;
        border: none;
    """)
    
    value_label = QtWidgets.QLabel(value)
    value_label.setObjectName("value_label")  # For easy updates
    value_label.setStyleSheet(f"""
        color: {color};
        font-size: 28px;
        font-weight: bold;
        border: none;
    """)
    
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    
    return card

def create_styled_table(columns: List[str], theme_colors: Dict[str, str]) -> QtWidgets.QTableWidget:
    """
    Create a standardized table widget with consistent styling.
    
    Args:
        columns: List of column header names
        theme_colors: Dictionary of theme colors from theme_manager
        
    Returns:
        QTableWidget with standard styling applied
        
    Example:
        >>> c = theme_manager.get_colors("Light")
        >>> table = create_styled_table(["ID", "Name", "Email"], c)
    """
    table = QtWidgets.QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(False)
    
    apply_table_style(table, theme_colors)
    
    return table

def apply_table_style(table: QtWidgets.QTableWidget, theme_colors: Dict[str, str]):
    """
    Apply standard styling to a table widget.
    
    Args:
        table: QTableWidget to style
        theme_colors: Dictionary of theme colors from theme_manager
    """
    table.setStyleSheet(f"""
        QTableWidget {{
            background: {theme_colors['bg_card']};
            border: 1px solid {theme_colors['border']};
            border-radius: 10px;
            gridline-color: transparent;
            font-size: 13px;
        }}
        QHeaderView::section {{
            background: {theme_colors['table_header_bg']};
            color: {theme_colors['table_header_text']};
            padding: 12px;
            border: none;
            font-weight: bold;
        }}
        QTableWidget::item {{
            padding: 10px;
            border-bottom: 1px solid {theme_colors['border']};
        }}
        QTableWidget::item:selected {{
            background: {theme_colors.get('selection_bg', '#E3F2FD')};
        }}
    """)

def apply_input_style(widget: QtWidgets.QWidget, theme_colors: Dict[str, str]):
    """
    Apply standard styling to input widgets (QLineEdit, QComboBox, etc).
    
    Args:
        widget: Input widget to style
        theme_colors: Dictionary of theme colors from theme_manager
    """
    widget.setStyleSheet(f"""
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {{
            background: {theme_colors['input_bg']};
            color: {theme_colors['text_primary']};
            border: 1px solid {theme_colors['input_border']};
            border-radius: 6px;
            padding: 8px;
            font-size: 13px;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTextEdit:focus {{
            border: 2px solid {theme_colors['input_focus']};
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 10px;
        }}
    """)

def create_action_button(text: str, color: str, theme_colors: Dict[str, str], 
                         icon: QtGui.QIcon = None) -> QtWidgets.QPushButton:
    """
    Create a standardized action button.
    
    Args:
        text: Button text
        color: Button background color (hex code)
        theme_colors: Dictionary of theme colors
        icon: Optional icon for the button
        
    Returns:
        QPushButton with standard styling
    """
    button = QtWidgets.QPushButton(text)
    if icon:
        button.setIcon(icon)
    
    button.setFixedHeight(40)
    button.setStyleSheet(f"""
        QPushButton {{
            background: {color};
            color: white;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
            padding: 0 20px;
        }}
        QPushButton:hover {{
            opacity: 0.9;
        }}
        QPushButton:pressed {{
            opacity: 0.8;
        }}
        QPushButton:disabled {{
            background: {theme_colors['btn_disabled']};
            color: {theme_colors['text_disabled']};
        }}
    """)
    
    return button

def create_group_box(title: str, theme_colors: Dict[str, str]) -> QtWidgets.QGroupBox:
    """
    Create a standardized group box for organizing form sections.
    
    Args:
        title: Group box title
        theme_colors: Dictionary of theme colors
        
    Returns:
        QGroupBox with standard styling
    """
    group = QtWidgets.QGroupBox(title)
    group.setStyleSheet(f"""
        QGroupBox {{
            background: {theme_colors['bg_card']};
            border: 1px solid {theme_colors['border']};
            border-radius: 10px;
            margin-top: 10px;
            padding: 20px;
            font-weight: bold;
            font-size: 16px;
            color: {theme_colors['text_primary']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 5px;
        }}
    """)
    
    return group

def show_loading_indicator(parent: QtWidgets.QWidget, message: str = "Cargando...") -> QtWidgets.QDialog:
    """
    Show a loading indicator dialog.
    
    Args:
        parent: Parent widget
        message: Loading message to display
        
    Returns:
        QDialog that can be closed when loading is complete
    """
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle("Cargando")
    dialog.setModal(True)
    dialog.setFixedSize(300, 100)
    
    layout = QtWidgets.QVBoxLayout(dialog)
    
    label = QtWidgets.QLabel(message)
    label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    
    progress = QtWidgets.QProgressBar()
    progress.setRange(0, 0)  # Indeterminate progress
    layout.addWidget(progress)
    
    dialog.show()
    QtWidgets.QApplication.processEvents()
    
    return dialog

def format_currency(amount: float) -> str:
    """
    Format a number as currency.
    
    Args:
        amount: Numeric amount
        
    Returns:
        Formatted currency string
    """
    return f"${amount:,.2f}"

def format_percentage(value: float) -> str:
    """
    Format a number as percentage.
    
    Args:
        value: Numeric value (0-100)
        
    Returns:
        Formatted percentage string
    """
    return f"{value:.1f}%"

def update_card_value(card: QtWidgets.QFrame, new_value: str):
    """
    Update the value displayed in a card widget.
    
    Args:
        card: Card widget created with create_card()
        new_value: New value to display
    """
    value_label = card.findChild(QtWidgets.QLabel, "value_label")
    if value_label:
        value_label.setText(new_value)

# =============================================================================
# CENTERED DIALOGS - Mejora de UX
# =============================================================================

def show_centered_question(parent, title: str, message: str, 
                          buttons=None) -> int:
    """
    Muestra un diálogo de pregunta centrado en la ventana padre.
    """
    if buttons is None:
        buttons = QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
    
    msg = QtWidgets.QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QtWidgets.QMessageBox.Icon.Question)
    msg.setStandardButtons(buttons)
    
    # TRUCO: Usar QTimer para centrar DESPUÉS de que se muestre
    def center_dialog():
        if parent:
            # Obtener geometría de la ventana padre
            parent_geometry = parent.frameGeometry()
            # Calcular centro
            x = parent_geometry.x() + (parent_geometry.width() - msg.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - msg.height()) // 2
            msg.move(x, y)
    
    QtCore.QTimer.singleShot(0, center_dialog)
    return msg.exec()

def show_centered_info(parent, title: str, message: str):
    """Muestra un diálogo de información centrado."""
    msg = QtWidgets.QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
    
    def center_dialog():
        if parent:
            parent_geometry = parent.frameGeometry()
            x = parent_geometry.x() + (parent_geometry.width() - msg.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - msg.height()) // 2
            msg.move(x, y)
    
    QtCore.QTimer.singleShot(0, center_dialog)
    return msg.exec()

def show_centered_warning(parent, title: str, message: str):
    """Muestra un diálogo de advertencia centrado."""
    msg = QtWidgets.QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    
    def center_dialog():
        if parent:
            parent_geometry = parent.frameGeometry()
            x = parent_geometry.x() + (parent_geometry.width() - msg.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - msg.height()) // 2
            msg.move(x, y)
    
    QtCore.QTimer.singleShot(0, center_dialog)
    return msg.exec()

def show_centered_error(parent, title: str, message: str):
    """Muestra un diálogo de error centrado."""
    msg = QtWidgets.QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    
    def center_dialog():
        if parent:
            parent_geometry = parent.frameGeometry()
            x = parent_geometry.x() + (parent_geometry.width() - msg.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - msg.height()) // 2
            msg.move(x, y)
    
    QtCore.QTimer.singleShot(0, center_dialog)
    return msg.exec()
