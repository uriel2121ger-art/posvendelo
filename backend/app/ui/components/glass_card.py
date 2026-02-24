"""
TITAN POS - Glass Card Component
Card con efecto glassmorphism y animación de elevación.
"""

import logging
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from app.ui.themes.colors import CyberNight

logger = logging.getLogger(__name__)


class GlassCard(QtWidgets.QFrame):
    """
    Card con efecto glassmorphism.
    
    Características:
    - Fondo semi-transparente con gradiente
    - Sombra que se intensifica en hover
    - Animación de "elevación" al pasar el mouse
    """
    
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        padding: int = 20
    ):
        super().__init__(parent)
        self.padding = padding
        self._setup_style()
        self._setup_shadow()
        self._setup_animations()
    
    def _setup_style(self):
        """Configura el estilo glassmorphism."""
        self.setObjectName("glassCard")
        self.setProperty("class", "glass-card")
        
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background: {CyberNight.GRADIENT_CARD};
                border: 1px solid rgba(42, 52, 65, 0.5);
                border-radius: {CyberNight.BORDER_RADIUS_LG}px;
                padding: {self.padding}px;
            }}
        """)
    
    def _setup_shadow(self):
        """Configura la sombra del card."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setColor(QtGui.QColor(0, 0, 0, 51))  # rgba(0, 0, 0, 0.2)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        
        self.shadow_effect = shadow
        self.setGraphicsEffect(shadow)
    
    def _setup_animations(self):
        """Configura animaciones de hover."""
        # Animación de blur (sombra más intensa en hover)
        self.blur_animation = QPropertyAnimation(self.shadow_effect, b"blurRadius")
        self.blur_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.blur_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Animación de offset Y (elevación)
        self.yoffset_animation = QPropertyAnimation(self.shadow_effect, b"yOffset")
        self.yoffset_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.yoffset_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Animación de opacidad de sombra
        self.opacity_animation = QPropertyAnimation(self.shadow_effect, b"opacity")
        self.opacity_animation.setDuration(CyberNight.ANIMATION_NORMAL)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def enterEvent(self, event: QtGui.QEnterEvent):
        """Activa la elevación al entrar el mouse."""
        super().enterEvent(event)
        
        # Aumentar blur, offset Y y opacidad
        self.blur_animation.setStartValue(20)
        self.blur_animation.setEndValue(30)
        self.blur_animation.start()
        
        self.yoffset_animation.setStartValue(4)
        self.yoffset_animation.setEndValue(8)
        self.yoffset_animation.start()
        
        self.opacity_animation.setStartValue(0.2)
        self.opacity_animation.setEndValue(0.4)
        self.opacity_animation.start()
        
        # Cambiar borde
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 rgba(37, 43, 58, 0.9), stop:1 rgba(26, 31, 46, 0.95));
                border: 1px solid rgba(0, 242, 255, 0.3);
                border-radius: {CyberNight.BORDER_RADIUS_LG}px;
                padding: {self.padding}px;
            }}
        """)
    
    def leaveEvent(self, event: QtCore.QEvent):
        """Desactiva la elevación al salir el mouse."""
        super().leaveEvent(event)
        
        # Reducir blur, offset Y y opacidad
        self.blur_animation.setStartValue(30)
        self.blur_animation.setEndValue(20)
        self.blur_animation.start()
        
        self.yoffset_animation.setStartValue(8)
        self.yoffset_animation.setEndValue(4)
        self.yoffset_animation.start()
        
        self.opacity_animation.setStartValue(0.4)
        self.opacity_animation.setEndValue(0.2)
        self.opacity_animation.start()
        
        # Restaurar borde
        self.setStyleSheet(f"""
            QFrame#glassCard {{
                background: {CyberNight.GRADIENT_CARD};
                border: 1px solid rgba(42, 52, 65, 0.5);
                border-radius: {CyberNight.BORDER_RADIUS_LG}px;
                padding: {self.padding}px;
            }}
        """)
