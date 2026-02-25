"""
Toast Notification System - TITAN POS
Sistema de notificaciones visuales mejoradas con iconos grandes y auto-cierre.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple
from enum import Enum

from PyQt6 import QtCore, QtGui, QtWidgets


class NotificationType(Enum):
    """Tipos de notificación disponibles."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CONFIRM = "confirm"

# Configuración de estilos por tipo de notificación
NOTIFICATION_STYLES = {
    NotificationType.SUCCESS: {
        "icon": "✅",
        "big_icon": "✓",
        "color": "#00C896",
        "bg": "linear-gradient(135deg, #00C896 0%, #00a878 100%)",
        "auto_close": True,
        "duration": 5000,  # 5 segundos como solicitado
    },
    NotificationType.ERROR: {
        "icon": "❌",
        "big_icon": "✕",
        "color": "#FF4757",
        "bg": "linear-gradient(135deg, #FF4757 0%, #c92a38 100%)",
        "auto_close": False,
        "duration": 0,
    },
    NotificationType.WARNING: {
        "icon": "⚠️",
        "big_icon": "!",
        "color": "#FFA502",
        "bg": "linear-gradient(135deg, #FFA502 0%, #cc8400 100%)",
        "auto_close": False,
        "duration": 0,
    },
    NotificationType.INFO: {
        "icon": "ℹ️",
        "big_icon": "i",
        "color": "#3498db",
        "bg": "linear-gradient(135deg, #3498db 0%, #2980b9 100%)",
        "auto_close": True,
        "duration": 5000,  # 5 segundos
    },
    NotificationType.CONFIRM: {
        "icon": "❓",
        "big_icon": "?",
        "color": "#9b59b6",
        "bg": "linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%)",
        "auto_close": False,
        "duration": 0,
    },
}

class Toast(QtWidgets.QWidget):
    """
    Notificación estilo toast con iconos grandes y auto-cierre opcional.
    
    Diseñada para ser más visible y clara que los QMessageBox estándar.
    Incluye barra de progreso animada para auto-cierre.
    """
    
    closed = QtCore.pyqtSignal()
    action_clicked = QtCore.pyqtSignal(str)  # Emite el action_id
    
    def __init__(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        actions: Optional[List[Tuple[str, str]]] = None,  # [(id, label), ...]
        parent: Optional[QtWidgets.QWidget] = None,
        custom_duration: Optional[int] = None,  # Override de duración en ms
    ):
        super().__init__(parent)
        self.notification_type = notification_type
        self.title = title
        self.message = message
        self.actions = actions or []
        self.custom_duration = custom_duration
        
        self.style_config = NOTIFICATION_STYLES[notification_type].copy()
        if custom_duration is not None:
            self.style_config["duration"] = custom_duration
            self.style_config["auto_close"] = custom_duration > 0
        
        self._animation_timer: Optional[QtCore.QTimer] = None
        self._progress_step = 0
        
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self._setup_ui()
        
        if self.style_config["auto_close"]:
            self._start_auto_close_timer()
    
    def _setup_ui(self):
        """Construye la interfaz del toast."""
        self.setFixedSize(480, 200)
        
        # Obtener colores del tema actual
        try:
            from app.utils.theme_manager import theme_manager
            from app.core import STATE
            # Intentar obtener tema desde core si está disponible
            if hasattr(STATE, 'core') and STATE.core:
                theme = (STATE.core.get_app_config() or {}).get("theme", "Cyber Night")
            else:
                theme = getattr(STATE, 'theme', 'Cyber Night')
            c = theme_manager.get_colors(theme)
        except Exception:
            # Fallback a colores Cyber Night por defecto
            c = {
                'bg_card': '#2a2f38',
                'bg_secondary': '#1e2128',
                'text_primary': '#e8eaed',
                'text_secondary': '#b0b4bb'
            }
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sombra
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QtGui.QColor(0, 0, 0, 100))
        shadow.setOffset(0, 8)
        
        # Card container - Usar colores del tema
        card = QtWidgets.QFrame()
        card.setGraphicsEffect(shadow)
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {c.get('bg_card', '#2a2f38')}, stop:1 {c.get('bg_secondary', '#1e2128')});
                border-radius: 16px;
                border: 2px solid {self.style_config['color']};
            }}
        """)
        card_layout = QtWidgets.QHBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 20)
        card_layout.setSpacing(20)
        
        # === Icono grande ===
        icon_container = QtWidgets.QFrame()
        icon_container.setFixedSize(90, 90)
        icon_container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self.style_config['color']}, stop:1 {self._darken_color(self.style_config['color'])});
                border-radius: 45px;
            }}
        """)
        icon_layout = QtWidgets.QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QtWidgets.QLabel(self.style_config['big_icon'])
        icon_label.setStyleSheet("""
            font-size: 48px;
            font-weight: bold;
            color: white;
            background: transparent;
            border: none;
        """)
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)
        
        # === Contenido ===
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setSpacing(8)
        
        # Título
        title_label = QtWidgets.QLabel(self.title)
        title_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: bold;
            color: {self.style_config['color']};
            background: transparent;
            border: none;
        """)
        
        # Mensaje - Usar color del tema
        message_label = QtWidgets.QLabel(self.message)
        message_label.setStyleSheet(f"""
            font-size: 14px;
            color: {c.get('text_secondary', '#b0b4bb')};
            background: transparent;
            border: none;
        """)
        message_label.setWordWrap(True)
        
        content_layout.addWidget(title_label)
        content_layout.addWidget(message_label)
        content_layout.addStretch()
        
        # === Botones de acción ===
        if self.actions:
            actions_layout = QtWidgets.QHBoxLayout()
            actions_layout.setSpacing(12)
            actions_layout.addStretch()
            
            for i, (action_id, label) in enumerate(self.actions):
                btn = QtWidgets.QPushButton(label)
                # Primer botón es primario, resto secundarios
                if i == 0:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: {self.style_config['color']};
                            color: white;
                            border: none;
                            border-radius: 8px;
                            padding: 10px 20px;
                            font-weight: bold;
                            font-size: 13px;
                        }}
                        QPushButton:hover {{
                            background: {self._lighten_color(self.style_config['color'])};
                        }}
                        QPushButton:pressed {{
                            background: {self._darken_color(self.style_config['color'])};
                        }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent;
                            color: {self.style_config['color']};
                            border: 2px solid {self.style_config['color']};
                            border-radius: 8px;
                            padding: 10px 20px;
                            font-weight: bold;
                            font-size: 13px;
                        }}
                        QPushButton:hover {{
                            background: rgba(255, 255, 255, 0.1);
                        }}
                    """)
                btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, aid=action_id: self._on_action(aid))
                actions_layout.addWidget(btn)
            
            content_layout.addLayout(actions_layout)
        
        # === Barra de progreso (auto-close) ===
        if self.style_config["auto_close"]:
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setFixedHeight(4)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: rgba(255, 255, 255, 0.1);
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background: {self.style_config['color']};
                    border-radius: 2px;
                }}
            """)
            content_layout.addWidget(self.progress_bar)
        
        # Botón cerrar (X)
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #888;
                border: none;
                border-radius: 16px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.3);
                color: #FF4757;
            }
        """)
        close_btn.clicked.connect(self.close_animation)
        
        card_layout.addWidget(icon_container)
        card_layout.addLayout(content_layout, 1)
        card_layout.addWidget(close_btn, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        
        main_layout.addWidget(card)
    
    def _darken_color(self, hex_color: str) -> str:
        """Oscurece un color hex."""
        color = QtGui.QColor(hex_color)
        return color.darker(130).name()
    
    def _lighten_color(self, hex_color: str) -> str:
        """Aclara un color hex."""
        color = QtGui.QColor(hex_color)
        return color.lighter(115).name()
    
    def _start_auto_close_timer(self):
        """Inicia el timer de auto-cierre con animación de progreso."""
        duration = self.style_config["duration"]
        steps = 100
        step_duration = duration / steps
        
        self._progress_step = 0
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.timeout.connect(self._update_progress)
        self._animation_timer.start(int(step_duration))
    
    def _update_progress(self):
        """Actualiza la barra de progreso."""
        self._progress_step += 1
        progress = 100 - self._progress_step
        
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(max(0, progress))
        
        if self._progress_step >= 100:
            if self._animation_timer:
                self._animation_timer.stop()
            self.close_animation()
    
    def _on_action(self, action_id: str):
        """Maneja click en botón de acción."""
        self.action_clicked.emit(action_id)
        self.close_animation()
    
    def close_animation(self):
        """Cierra el toast con animación fade-out."""
        if self._animation_timer:
            self._animation_timer.stop()
        
        # Animación de fade out
        # CRITICAL FIX: Verificar si el widget soporta windowOpacity antes de usarlo
        try:
            self.fade_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
            self.fade_anim.setDuration(200)
            self.fade_anim.setStartValue(1.0)
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.InQuad)
            self.fade_anim.finished.connect(self._finish_close)
            self.fade_anim.start()
        except Exception:
            # Widget no soporta windowOpacity, cerrar directamente
            self._finish_close()
    
    def _finish_close(self):
        """Finaliza el cierre."""
        self.closed.emit()
        self.close()
    
    def show_centered(self, parent: Optional[QtWidgets.QWidget] = None):
        """Muestra el toast centrado sobre el padre."""
        target = parent or self.parent()
        
        if target:
            # Obtener el centro del widget padre en coordenadas globales
            parent_rect = target.rect()
            parent_center = target.mapToGlobal(parent_rect.center())
            
            x = parent_center.x() - self.width() // 2
            y = parent_center.y() - self.height() // 2
        else:
            # Centrar en pantalla
            screen = QtWidgets.QApplication.primaryScreen()
            if screen:
                screen_geo = screen.geometry()
                x = (screen_geo.width() - self.width()) // 2
                y = (screen_geo.height() - self.height()) // 2
            else:
                x, y = 100, 100
        
        self.move(x, y)
        
        # Animación de entrada
        # CRITICAL FIX: Verificar si el widget soporta windowOpacity antes de usarlo
        try:
            self.setWindowOpacity(0.0)
            self.show()
            
            self.fade_in_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
            self.fade_in_anim.setDuration(200)
            self.fade_in_anim.setStartValue(0.0)
            self.fade_in_anim.setEndValue(1.0)
            self.fade_in_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)
            self.fade_in_anim.start()
        except Exception:
            # Widget no soporta windowOpacity, mostrar sin animación
            self.show()
    
    def mousePressEvent(self, event):
        """Permite arrastrar el toast."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Mueve el toast al arrastrar."""
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

class ToastManager:
    """
    Gestor global de toasts.
    
    Uso:
        ToastManager.success("Título", "Mensaje", parent=self)
        ToastManager.error("Error", "Descripción", [("retry", "Reintentar")])
    """
    
    _instance: Optional['ToastManager'] = None
    _toasts: List[Toast] = []
    
    @classmethod
    def instance(cls) -> 'ToastManager':
        """Obtiene la instancia singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def success(
        cls,
        title: str,
        message: str,
        parent: Optional[QtWidgets.QWidget] = None,
        duration: int = 5000,
    ) -> Toast:
        """Muestra toast de éxito."""
        toast = Toast(
            NotificationType.SUCCESS,
            title,
            message,
            parent=parent,
            custom_duration=duration,
        )
        toast.show_centered(parent)
        cls._toasts.append(toast)
        toast.closed.connect(lambda: cls._remove_toast(toast))
        return toast
    
    @classmethod
    def error(
        cls,
        title: str,
        message: str,
        actions: Optional[List[Tuple[str, str]]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> Toast:
        """Muestra toast de error (requiere acción para cerrar)."""
        toast = Toast(
            NotificationType.ERROR,
            title,
            message,
            actions or [("ok", "Aceptar")],
            parent=parent,
        )
        toast.show_centered(parent)
        cls._toasts.append(toast)
        toast.closed.connect(lambda: cls._remove_toast(toast))
        return toast
    
    @classmethod
    def warning(
        cls,
        title: str,
        message: str,
        actions: Optional[List[Tuple[str, str]]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        duration: int = 0,
    ) -> Toast:
        """
        Muestra toast de advertencia.

        Args:
            duration: Tiempo en ms antes de auto-cerrar.
                      0 = no auto-cerrar (requiere click/acción).
                      >0 = se cierra automáticamente después de X ms.
        """
        toast = Toast(
            NotificationType.WARNING,
            title,
            message,
            actions,
            parent=parent,
            custom_duration=duration if duration > 0 else None,
        )
        toast.show_centered(parent)
        cls._toasts.append(toast)
        toast.closed.connect(lambda: cls._remove_toast(toast))
        return toast
    
    @classmethod
    def info(
        cls,
        title: str,
        message: str,
        parent: Optional[QtWidgets.QWidget] = None,
        duration: int = 5000,
    ) -> Toast:
        """Muestra toast informativo."""
        toast = Toast(
            NotificationType.INFO,
            title,
            message,
            parent=parent,
            custom_duration=duration,
        )
        toast.show_centered(parent)
        cls._toasts.append(toast)
        toast.closed.connect(lambda: cls._remove_toast(toast))
        return toast
    
    @classmethod
    def confirm(
        cls,
        title: str,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Optional[Callable[[], None]] = None,
        confirm_text: str = "Confirmar",
        cancel_text: str = "Cancelar",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> Toast:
        """Muestra toast de confirmación con callbacks."""
        toast = Toast(
            NotificationType.CONFIRM,
            title,
            message,
            [("confirm", confirm_text), ("cancel", cancel_text)],
            parent=parent,
        )
        
        def handle_action(action_id: str):
            if action_id == "confirm":
                on_confirm()
            elif action_id == "cancel" and on_cancel:
                on_cancel()
        
        toast.action_clicked.connect(handle_action)
        toast.show_centered(parent)
        cls._toasts.append(toast)
        toast.closed.connect(lambda: cls._remove_toast(toast))
        return toast
    
    @classmethod
    def _remove_toast(cls, toast: Toast):
        """Remueve un toast de la lista."""
        if toast in cls._toasts:
            cls._toasts.remove(toast)
    
    @classmethod
    def clear_all(cls):
        """Cierra todos los toasts activos."""
        for toast in cls._toasts[:]:
            toast.close_animation()

# Alias convenientes para acceso directo
success = ToastManager.success
error = ToastManager.error
warning = ToastManager.warning
info = ToastManager.info
confirm = ToastManager.confirm
