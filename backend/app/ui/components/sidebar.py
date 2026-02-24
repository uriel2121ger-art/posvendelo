"""
TITAN POS - Cyber Sidebar Component
Sidebar colapsable con animación y efectos glow.
"""

import logging
from typing import Optional, List, Tuple, Callable

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

from app.ui.themes.colors import CyberNight

logger = logging.getLogger(__name__)


class CyberSidebar(QtWidgets.QFrame):
    """
    Sidebar colapsable con estilo Cyber Night.
    
    Características:
    - Colapsa de 240px a 60px
    - Iconos SVG
    - Indicador de item activo con glow
    - Animación suave de colapso
    """
    
    item_clicked = QtCore.pyqtSignal(str)  # Emite el id del item
    
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        width_expanded: int = 240,
        width_collapsed: int = 60
    ):
        super().__init__(parent)
        self.width_expanded = width_expanded
        self.width_collapsed = width_collapsed
        self.is_collapsed = False
        self.current_item_id = None
        
        self._setup_style()
        self._setup_animation()
        self._setup_ui()
    
    def _setup_style(self):
        """Configura el estilo del sidebar."""
        self.setObjectName("sidebar")
        self.setFixedWidth(self.width_expanded)
        
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 {CyberNight.BG_SECONDARY}, stop:1 {CyberNight.BG_TERTIARY});
                border-right: 2px solid {CyberNight.BORDER_DEFAULT};
            }}
        """)
    
    def _setup_animation(self):
        """Configura la animación de colapso."""
        self.width_animation = QPropertyAnimation(self, b"minimumWidth")
        self.width_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.width_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    
    def _setup_ui(self):
        """Construye la interfaz del sidebar."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(8)
        
        # Botón de colapsar
        self.collapse_btn = QtWidgets.QPushButton("◄")
        self.collapse_btn.setFixedSize(44, 44)
        self.collapse_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 2px solid {CyberNight.BORDER_DEFAULT};
                border-radius: 12px;
                color: {CyberNight.TEXT_SECONDARY};
                font-size: 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: rgba(0, 242, 255, 0.1);
                border-color: {CyberNight.ACCENT_PRIMARY};
                color: {CyberNight.ACCENT_PRIMARY};
            }}
        """)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        
        # Contenedor de items
        self.items_container = QtWidgets.QWidget()
        self.items_layout = QtWidgets.QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(4)
        
        # Scroll area para items
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(self.items_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        
        layout.addWidget(self.collapse_btn)
        layout.addWidget(scroll, 1)
        layout.addStretch()
        
        # Almacenar items
        self.items: List[Tuple[str, QtWidgets.QPushButton]] = []
    
    def add_item(
        self,
        item_id: str,
        icon: str,
        text: str,
        callback: Optional[Callable] = None
    ):
        """
        Agrega un item al sidebar.
        
        Args:
            item_id: ID único del item
            icon: Emoji o texto del icono
            text: Texto del item
            callback: Función a llamar al hacer click
        """
        btn = QtWidgets.QPushButton(f"{icon}  {text}")
        btn.setObjectName(f"sidebar_item_{item_id}")
        btn.setCheckable(True)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(48)
        
        # Estilo base
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 12px;
                color: {CyberNight.TEXT_SECONDARY};
                padding: 12px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(0, 242, 255, 0.1);
                color: {CyberNight.ACCENT_PRIMARY};
            }}
            QPushButton:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 rgba(0, 242, 255, 0.2), stop:1 rgba(112, 0, 255, 0.2));
                color: {CyberNight.ACCENT_PRIMARY};
                border-left: 3px solid {CyberNight.ACCENT_PRIMARY};
                font-weight: 600;
            }}
        """)
        
        # Conectar señal
        if callback:
            btn.clicked.connect(lambda checked, cid=item_id: self._on_item_clicked(cid, callback))
        else:
            btn.clicked.connect(lambda checked, cid=item_id: self._on_item_clicked(cid))
        
        self.items_layout.addWidget(btn)
        self.items.append((item_id, btn))
    
    def _on_item_clicked(self, item_id: str, callback: Optional[Callable] = None):
        """Maneja el click en un item."""
        # Desmarcar item anterior
        if self.current_item_id:
            for iid, btn in self.items:
                if iid == self.current_item_id:
                    btn.setChecked(False)
                    break
        
        # Marcar nuevo item
        self.current_item_id = item_id
        for iid, btn in self.items:
            if iid == item_id:
                btn.setChecked(True)
                break
        
        # Emitir señal y llamar callback
        self.item_clicked.emit(item_id)
        if callback:
            callback()
    
    def toggle_collapse(self):
        """Alterna el estado de colapso."""
        self.is_collapsed = not self.is_collapsed
        
        if self.is_collapsed:
            # Colapsar
            self.width_animation.setStartValue(self.width_expanded)
            self.width_animation.setEndValue(self.width_collapsed)
            self.collapse_btn.setText("►")
            
            # Ocultar texto de items
            for item_id, btn in self.items:
                text = btn.text()
                # Guardar texto original en tooltip
                btn.setToolTip(text)
                # Mostrar solo icono
                parts = text.split() if text else []
                icon = parts[0] if parts else ""
                btn.setText(icon)
        else:
            # Expandir
            self.width_animation.setStartValue(self.width_collapsed)
            self.width_animation.setEndValue(self.width_expanded)
            self.collapse_btn.setText("◄")
            
            # Restaurar texto de items
            for item_id, btn in self.items:
                tooltip = btn.toolTip()
                if tooltip:
                    btn.setText(tooltip)
                    btn.setToolTip("")
        
        self.width_animation.start()
    
    def set_active_item(self, item_id: str):
        """Establece el item activo."""
        self._on_item_clicked(item_id)
