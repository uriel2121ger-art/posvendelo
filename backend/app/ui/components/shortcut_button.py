"""
Shortcut Button - TITAN POS
Botón con atajo de teclado visible integrado.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets


class ShortcutButton(QtWidgets.QPushButton):
    """
    Botón con atajo de teclado visible.
    
    Muestra el atajo como un badge junto al texto del botón.
    Soporta tema oscuro por defecto.
    
    Ejemplo:
        btn = ShortcutButton("💳 Cobrar", "F12")
        btn.clicked.connect(handle_charge)
    """
    
    def __init__(
        self,
        text: str,
        shortcut: Optional[str] = None,
        icon: Optional[QtGui.QIcon] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        color: str = "#00C896",  # Color primario del botón
    ):
        super().__init__(parent)
        
        self.main_text = text
        self.shortcut_text = shortcut
        self.button_color = color
        self._icon = icon
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Construye la UI del botón."""
        self.setMinimumHeight(45)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        # Crear texto combinado con badge de atajo
        if self.shortcut_text:
            # El shortcut se muestra como badge separado visualmente
            display_text = f"{self.main_text}  [{self.shortcut_text}]"
        else:
            display_text = self.main_text
        
        self.setText(display_text)
        
        if self._icon:
            self.setIcon(self._icon)
            self.setIconSize(QtCore.QSize(20, 20))
        
        self._apply_style()
    
    def _apply_style(self):
        """Aplica el estilo del botón."""
        # Calcular color hover (más claro) y pressed (más oscuro)
        base_color = QtGui.QColor(self.button_color)
        hover_color = base_color.lighter(115).name()
        pressed_color = base_color.darker(115).name()
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.button_color}, stop:1 {pressed_color});
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 13px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {hover_color}, stop:1 {self.button_color});
            }}
            QPushButton:pressed {{
                background: {pressed_color};
            }}
            QPushButton:disabled {{
                background: #3d4148;
                color: #666;
            }}
        """)
    
    def set_shortcut(self, shortcut: str):
        """Actualiza el atajo mostrado."""
        self.shortcut_text = shortcut
        if shortcut:
            self.setText(f"{self.main_text}  [{shortcut}]")
        else:
            self.setText(self.main_text)
    
    def set_color(self, color: str):
        """Cambia el color del botón."""
        self.button_color = color
        self._apply_style()

class ShortcutActionButton(QtWidgets.QWidget):
    """
    Botón de acción con diseño más elaborado.
    
    Incluye icono, texto principal, shortcut en badge separado,
    y descripción opcional.
    """
    
    clicked = QtCore.pyqtSignal()
    
    def __init__(
        self,
        text: str,
        shortcut: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,  # Emoji o texto
        color: str = "#00C896",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        
        self.main_text = text
        self.shortcut_text = shortcut
        self.description = description
        self.icon_text = icon or ""
        self.button_color = color
        
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
    
    def _setup_ui(self):
        """Construye la UI."""
        self.setMinimumHeight(50)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Icono (emoji)
        if self.icon_text:
            icon_label = QtWidgets.QLabel(self.icon_text)
            icon_label.setStyleSheet("""
                font-size: 20px;
                background: transparent;
                border: none;
            """)
            icon_label.setFixedWidth(28)
            layout.addWidget(icon_label)
        
        # Texto principal (y descripción si existe)
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(2)
        
        main_label = QtWidgets.QLabel(self.main_text)
        main_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: white;
            background: transparent;
            border: none;
        """)
        text_layout.addWidget(main_label)
        
        if self.description:
            desc_label = QtWidgets.QLabel(self.description)
            desc_label.setStyleSheet("""
                font-size: 11px;
                color: #888;
                background: transparent;
                border: none;
            """)
            text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        
        # Badge del shortcut
        shortcut_badge = QtWidgets.QLabel(self.shortcut_text)
        shortcut_badge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        shortcut_badge.setStyleSheet(f"""
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 6px;
            padding: 4px 10px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 11px;
            font-weight: bold;
            color: {self.button_color};
        """)
        layout.addWidget(shortcut_badge)
        
        self._apply_style()
    
    def _apply_style(self):
        """Aplica estilo al contenedor."""
        hover_bg = QtGui.QColor(self.button_color)
        hover_bg.setAlpha(30)
        
        self.setStyleSheet(f"""
            ShortcutActionButton {{
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }}
            ShortcutActionButton:hover {{
                background: rgba({hover_bg.red()}, {hover_bg.green()}, {hover_bg.blue()}, 0.15);
                border: 1px solid {self.button_color};
            }}
        """)
    
    def mousePressEvent(self, event):
        """Emite señal de click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

def update_button_with_shortcut(
    button: QtWidgets.QPushButton,
    shortcut: str,
    position: str = "right",  # 'right', 'below', 'badge'
):
    """
    Actualiza un botón existente para mostrar su atajo.
    
    Esta función es útil para actualizar botones existentes sin
    tener que recrearlos como ShortcutButton.
    
    Args:
        button: El QPushButton a actualizar
        shortcut: El texto del atajo (ej: "F12", "Ctrl+S")
        position: Dónde mostrar el atajo
    """
    current_text = button.text()
    
    # Limpiar cualquier atajo anterior
    if " [" in current_text and current_text.endswith("]"):
        current_text = current_text.rsplit(" [", 1)[0]
    if " (" in current_text and current_text.endswith(")"):
        # Algunos botones ya tienen el formato "Cobrar (F12)"
        pass  # Mantener el formato existente
    
    if position == "right":
        button.setText(f"{current_text} [{shortcut}]")
    elif position == "below":
        button.setText(f"{current_text}\n{shortcut}")
    elif position == "badge":
        # Para badge necesitamos un layout más complejo
        # Por ahora usamos el formato simple
        button.setText(f"{current_text} [{shortcut}]")
