"""
TITAN POS - Modern Button Component
Botón con efectos glow animados y variantes de estilo.
"""

import logging
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from app.ui.themes.colors import CyberNight

logger = logging.getLogger(__name__)


class ModernButton(QtWidgets.QPushButton):
    """
    Botón moderno con efectos glow animados.
    
    Variantes:
    - primary: Gradiente cyan→violeta
    - success: Verde neón
    - danger: Rosa neón
    - outline: Borde cyan, fondo transparente
    """
    
    def __init__(
        self,
        text: str,
        variant: str = "primary",
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(text, parent)
        self.variant = variant
        self._setup_style()
        self._setup_shadow()
        self._setup_animations()
    
    def _setup_style(self):
        """Configura el estilo base del botón según la variante."""
        self.setObjectName(f"btn_{self.variant}")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)
        
        # Aplicar clase CSS para QSS
        self.setProperty("class", f"btn-{self.variant}")
        
        # Estilos inline según variante
        if self.variant == "primary":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {CyberNight.GRADIENT_PRIMARY};
                    border: none;
                    border-radius: 12px;
                    color: {CyberNight.TEXT_ON_ACCENT};
                    font-weight: 700;
                    font-size: 16px;
                    padding: 16px 32px;
                }}
                QPushButton:hover {{
                    background: {CyberNight.GRADIENT_PRIMARY_HOVER};
                }}
            """)
        elif self.variant == "success":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {CyberNight.ACCENT_SUCCESS};
                    border: none;
                    border-radius: 12px;
                    color: {CyberNight.TEXT_ON_ACCENT};
                    font-weight: 700;
                    font-size: 16px;
                    padding: 16px 32px;
                }}
                QPushButton:hover {{
                    background: {CyberNight.ACCENT_SUCCESS_HOVER};
                }}
            """)
        elif self.variant == "danger":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {CyberNight.ACCENT_DANGER};
                    border: none;
                    border-radius: 12px;
                    color: {CyberNight.TEXT_PRIMARY};
                    font-weight: 700;
                    font-size: 16px;
                    padding: 16px 32px;
                }}
                QPushButton:hover {{
                    background: {CyberNight.ACCENT_DANGER_HOVER};
                }}
            """)
        elif self.variant == "outline":
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 2px solid {CyberNight.ACCENT_PRIMARY};
                    border-radius: 12px;
                    color: {CyberNight.ACCENT_PRIMARY};
                    font-weight: 600;
                    font-size: 16px;
                    padding: 14px 30px;
                }}
                QPushButton:hover {{
                    background: rgba(0, 242, 255, 0.1);
                    border-color: {CyberNight.ACCENT_PRIMARY_HOVER};
                    color: {CyberNight.ACCENT_PRIMARY_HOVER};
                }}
            """)
    
    def _setup_shadow(self):
        """Configura el efecto de sombra/glow."""
        shadow = QGraphicsDropShadowEffect(self)
        
        # Color de sombra según variante
        if self.variant == "primary":
            shadow.setColor(QtGui.QColor(0, 242, 255, 76))  # rgba(0, 242, 255, 0.3)
        elif self.variant == "success":
            shadow.setColor(QtGui.QColor(0, 255, 136, 76))  # rgba(0, 255, 136, 0.3)
        elif self.variant == "danger":
            shadow.setColor(QtGui.QColor(255, 51, 102, 76))  # rgba(255, 51, 102, 0.3)
        else:
            shadow.setColor(QtGui.QColor(0, 242, 255, 51))  # rgba(0, 242, 255, 0.2)
        
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        
        self.shadow_effect = shadow
        self.setGraphicsEffect(shadow)
    
    def _setup_animations(self):
        """Configura animaciones de hover."""
        # Animación de blur (glow más intenso en hover)
        self.blur_animation = QPropertyAnimation(self.shadow_effect, b"blurRadius")
        self.blur_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.blur_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Animación de opacidad de sombra
        self.opacity_animation = QPropertyAnimation(self.shadow_effect, b"opacity")
        self.opacity_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def enterEvent(self, event: QtGui.QEnterEvent):
        """Activa el glow al entrar el mouse."""
        super().enterEvent(event)
        
        # Aumentar blur y opacidad
        self.blur_animation.setStartValue(20)
        self.blur_animation.setEndValue(30)
        self.blur_animation.start()
        
        self.opacity_animation.setStartValue(0.3)
        self.opacity_animation.setEndValue(0.5)
        self.opacity_animation.start()
    
    def leaveEvent(self, event: QtCore.QEvent):
        """Desactiva el glow al salir el mouse."""
        super().leaveEvent(event)
        
        # Reducir blur y opacidad
        self.blur_animation.setStartValue(30)
        self.blur_animation.setEndValue(20)
        self.blur_animation.start()
        
        self.opacity_animation.setStartValue(0.5)
        self.opacity_animation.setEndValue(0.3)
        self.opacity_animation.start()
