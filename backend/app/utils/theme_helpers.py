"""
Theme Helpers - Centralized theme management
Eliminates code duplication across dialogs and tabs
"""

from typing import Optional

from PyQt6 import QtCore, QtWidgets


class ThemeHelper:
    """Centralized theme management for widgets"""
    
    @staticmethod
    def get_colors(core=None):
        """
        Get current theme colors with fallback
        
        Args:
            core: POSCore instance (optional)
        
        Returns:
            Dict of theme colors
        """
        try:
            from app.utils.theme_manager import theme_manager
            
            if core:
                theme = (core.get_app_config() or {}).get("theme", "Light")
            else:
                # Try to get from global state
                try:
                    from app.core import STATE
                    theme = STATE.theme if hasattr(STATE, 'theme') else "Light"
                except Exception:
                    theme = "Light"
            
            return theme_manager.get_colors(theme)
        except Exception:
            # Ultimate fallback
            return {
                'bg_primary': '#FFFFFF',
                'text_primary': '#000000',
                'btn_primary': '#2196F3',
                'btn_success': '#4CAF50',
                'btn_danger': '#F44336',
                'btn_warning': '#FF9800',
            }
    
    @staticmethod
    def style_button(button: QtWidgets.QPushButton, 
                     button_type: str = "primary",
                     core=None) -> None:
        """
        Apply theme-aware styling to button
        
        Args:
            button: Button to style
            button_type: Type of button (primary, success, danger, warning)
            core: POSCore instance (optional)
        """
        c = ThemeHelper.get_colors(core)
        
        color_map = {
            "primary": c.get('btn_primary', '#2196F3'),
            "success": c.get('btn_success', '#4CAF50'),
            "danger": c.get('btn_danger', '#F44336'),
            "warning": c.get('btn_warning', '#FF9800'),
        }
        
        bg_color = color_map.get(button_type, color_map["primary"])
        
        button.setStyleSheet(f"""
            QPushButton {{
                background: {bg_color};
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
                background: {bg_color};
            }}
            QPushButton:pressed {{
                background: {bg_color};
                padding-top: 10px;
                padding-bottom: 6px;
            }}
        """)
    
    @staticmethod
    def apply_dialog_theme(dialog: QtWidgets.QDialog, core=None) -> None:
        """
        Apply theme to all buttons in dialog automatically
        
        Args:
            dialog: Dialog to theme
            core: POSCore instance (optional)
        """
        for btn in dialog.findChildren(QtWidgets.QPushButton):
            text = btn.text().lower()
            
            # Determine button type from text
            if any(word in text for word in ['guardar', 'save', 'aceptar', 'accept', 'aplicar', 'apply']):
                button_type = "success"
            elif any(word in text for word in ['eliminar', 'delete', 'borrar']):
                button_type = "danger"
            elif any(word in text for word in ['cancelar', 'cancel', 'cerrar', 'close']):
                button_type = "danger"
            elif any(word in text for word in ['restaurar', 'restore']):
                button_type = "success"
            elif any(word in text for word in ['agregar', 'add', 'crear', 'create', 'nuevo', 'new']):
                button_type = "primary"
            else:
                button_type = "primary"
            
            ThemeHelper.style_button(btn, button_type, core)
    
    @staticmethod
    def style_table(table: QtWidgets.QTableWidget, core=None) -> None:
        """
        Apply theme to table widget
        
        Args:
            table: Table to style
            core: POSCore instance (optional)
        """
        c = ThemeHelper.get_colors(core)
        
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {c.get('bg_card', '#FFFFFF')};
                border: 1px solid {c.get('border', '#E0E0E0')};
                border-radius: 10px;
                gridline-color: transparent;
                font-size: 13px;
            }}
            QHeaderView::section {{
                background: {c.get('table_header_bg', '#F5F5F5')};
                color: {c.get('table_header_text', '#424242')};
                padding: 12px;
                border: none;
                font-weight: bold;
            }}
            QTableWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {c.get('border', '#E0E0E0')};
                color: {c.get('text_primary', '#000000')};
            }}
            QTableWidget::item:selected {{
                background: {c.get('btn_primary', '#2196F3')};
                color: white;
            }}
        """)
    
    @staticmethod
    def create_card(parent: QtWidgets.QWidget, 
                   title: str, 
                   value: str,
                   color: str = "#2196F3",
                   core=None) -> QtWidgets.QFrame:
        """
        Create a themed card widget
        
        Args:
            parent: Parent widget
            title: Card title
            value: Card value
            color: Accent color
            core: POSCore instance
        
        Returns:
            Styled QFrame card
        """
        c = ThemeHelper.get_colors(core)
        
        card = QtWidgets.QFrame(parent)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c.get('bg_card', '#FFFFFF')};
                border: 1px solid {c.get('border', '#E0E0E0')};
                border-radius: 10px;
                border-left: 5px solid {color};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setSpacing(5)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(f"""
            color: {c.get('text_secondary', '#757575')};
            font-size: 13px;
            font-weight: 600;
            border: none;
        """)
        
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"""
            color: {color};
            font-size: 28px;
            font-weight: bold;
            border: none;
        """)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card
