"""
TITAN POS - Animated Label Component
Label que anima cambios de valor numérico (útil para totales).
"""

import logging
from typing import Optional, Union

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

from app.ui.themes.colors import CyberNight

logger = logging.getLogger(__name__)


class AnimatedLabel(QtWidgets.QLabel):
    """
    Label que anima cambios de valor numérico.
    
    Útil para:
    - Totales del carrito
    - Precios
    - Contadores
    """
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
        font_family: str = "JetBrains Mono",
        font_size: int = 28,
        color: str = CyberNight.ACCENT_PRIMARY
    ):
        super().__init__(text, parent)
        self.font_family = font_family
        self.font_size = font_size
        self.color = color
        self._current_value = 0.0
        self._setup_style()
        self._setup_animation()
    
    def _setup_style(self):
        """Configura el estilo del label."""
        font = self.font()
        font.setFamily(self.font_family)
        font.setPointSize(self.font_size)
        font.setBold(True)
        self.setFont(font)
        
        self.setStyleSheet(f"""
            QLabel {{
                color: {self.color};
                font-family: "{self.font_family}", monospace;
                font-size: {self.font_size}px;
                font-weight: 700;
            }}
        """)
    
    def _setup_animation(self):
        """Configura la animación de valor."""
        self.value_animation = QPropertyAnimation(self, b"_current_value")
        self.value_animation.setDuration(CyberNight.ANIMATION_SLOW)
        self.value_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.value_animation.valueChanged.connect(self._on_value_changed)
    
    def _on_value_changed(self, value: float):
        """Actualiza el texto cuando cambia el valor animado."""
        formatted_value = f"${value:,.2f}" if isinstance(value, (int, float)) else str(value)
        self.setText(formatted_value)
    
    def set_value(self, value: Union[int, float], animated: bool = True):
        """
        Establece el valor del label.
        
        Args:
            value: Valor numérico a mostrar
            animated: Si True, anima el cambio de valor
        """
        if animated:
            self.value_animation.setStartValue(self._current_value)
            self.value_animation.setEndValue(float(value))
            self.value_animation.start()
        else:
            self._current_value = float(value)
            formatted_value = f"${value:,.2f}" if isinstance(value, (int, float)) else str(value)
            self.setText(formatted_value)
    
    def get_value(self) -> float:
        """Retorna el valor actual."""
        return self._current_value
