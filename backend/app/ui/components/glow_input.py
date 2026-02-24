"""
TITAN POS - Glow Input Component
Input con glow cyan animado al hacer focus.
"""

import logging
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from app.ui.themes.colors import CyberNight

logger = logging.getLogger(__name__)


class GlowInput(QtWidgets.QLineEdit):
    """
    Input con efecto glow animado al hacer focus.
    
    Características:
    - Glow cyan que aparece suavemente al hacer focus
    - Animación de transición del borde
    - Estilo Cyber Night integrado
    """
    
    def __init__(
        self,
        placeholder: str = "",
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self._setup_style()
        self._setup_shadow()
        self._setup_animations()
    
    def _setup_style(self):
        """Configura el estilo base del input."""
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.03);
                border: 2px solid {CyberNight.BORDER_DEFAULT};
                border-radius: {CyberNight.BORDER_RADIUS_LG}px;
                color: {CyberNight.TEXT_PRIMARY};
                padding: 16px 20px;
                font-size: 18px;
                font-family: "Inter", sans-serif;
                selection-background-color: rgba(0, 242, 255, 0.3);
                selection-color: {CyberNight.TEXT_PRIMARY};
            }}
            QLineEdit::placeholder {{
                color: {CyberNight.TEXT_TERTIARY};
            }}
        """)
    
    def _setup_shadow(self):
        """Configura el efecto de sombra/glow."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setColor(QtGui.QColor(0, 242, 255, 0))  # Inicialmente transparente
        shadow.setBlurRadius(0)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        
        self.shadow_effect = shadow
        self.setGraphicsEffect(shadow)
    
    def _setup_animations(self):
        """Configura animaciones de focus."""
        # Animación de blur (glow más intenso en focus)
        self.blur_animation = QPropertyAnimation(self.shadow_effect, b"blurRadius")
        self.blur_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.blur_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Animación de opacidad de sombra
        self.opacity_animation = QPropertyAnimation(self.shadow_effect, b"opacity")
        self.opacity_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def focusInEvent(self, event: QtGui.QFocusEvent):
        """Activa el glow al hacer focus."""
        super().focusInEvent(event)
        
        # Cambiar borde
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(0, 242, 255, 0.05);
                border: 2px solid {CyberNight.BORDER_FOCUS};
                border-radius: {CyberNight.BORDER_RADIUS_LG}px;
                color: {CyberNight.TEXT_PRIMARY};
                padding: 16px 20px;
                font-size: 18px;
                font-family: "Inter", sans-serif;
                selection-background-color: rgba(0, 242, 255, 0.3);
                selection-color: {CyberNight.TEXT_PRIMARY};
            }}
            QLineEdit::placeholder {{
                color: {CyberNight.TEXT_TERTIARY};
            }}
        """)
        
        # Activar glow
        self.shadow_effect.setColor(QtGui.QColor(0, 242, 255, 76))  # rgba(0, 242, 255, 0.3)
        
        self.blur_animation.setStartValue(0)
        self.blur_animation.setEndValue(20)
        self.blur_animation.start()
        
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(0.3)
        self.opacity_animation.start()
    
    def focusOutEvent(self, event: QtGui.QFocusEvent):
        """Desactiva el glow al perder focus."""
        super().focusOutEvent(event)
        
        # Restaurar borde
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255, 255, 255, 0.03);
                border: 2px solid {CyberNight.BORDER_DEFAULT};
                border-radius: {CyberNight.BORDER_RADIUS_LG}px;
                color: {CyberNight.TEXT_PRIMARY};
                padding: 16px 20px;
                font-size: 18px;
                font-family: "Inter", sans-serif;
                selection-background-color: rgba(0, 242, 255, 0.3);
                selection-color: {CyberNight.TEXT_PRIMARY};
            }}
            QLineEdit::placeholder {{
                color: {CyberNight.TEXT_TERTIARY};
            }}
        """)
        
        # Desactivar glow
        self.blur_animation.setStartValue(20)
        self.blur_animation.setEndValue(0)
        self.blur_animation.start()
        
        self.opacity_animation.setStartValue(0.3)
        self.opacity_animation.setEndValue(0)
        self.opacity_animation.start()
