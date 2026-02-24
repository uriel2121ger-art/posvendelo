"""
TITAN POS - Base Dialogs
Diálogos reutilizables para reducir duplicación de código
"""

from typing import Any, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DialogBase:
    """Clase base con métodos estáticos para diálogos comunes."""
    
    @staticmethod
    def info(parent: QWidget, title: str, message: str, detail: str = None):
        """Muestra un diálogo de información."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle(title)
        msg.setText(message)
        if detail:
            msg.setDetailedText(detail)
        # Aplicar tema al QMessageBox
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg, core)
        except Exception:
            pass  # Continuar sin tema si falla
        msg.exec()
    
    @staticmethod
    def success(parent: QWidget, message: str = "Operación exitosa"):
        """Muestra un diálogo de éxito."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("✅ Éxito")
        msg.setText(message)
        # Aplicar tema al QMessageBox
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg, core)
        except Exception:
            pass
        msg.exec()
    
    @staticmethod
    def warning(parent: QWidget, title: str, message: str):
        """Muestra un diálogo de advertencia."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        # Aplicar tema al QMessageBox
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg, core)
        except Exception:
            pass
        msg.exec()
    
    @staticmethod
    def error(parent: QWidget, title: str, message: str, detail: str = None):
        """Muestra un diálogo de error."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        if detail:
            msg.setDetailedText(detail)
        msg.exec()
    
    @staticmethod
    def confirm(parent: QWidget, title: str, message: str) -> bool:
        """Muestra un diálogo de confirmación. Retorna True si confirma."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        # Aplicar tema al QMessageBox
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg, core)
        except Exception:
            pass
        result = msg.exec()
        return result == QMessageBox.StandardButton.Yes
    
    @staticmethod
    def confirm_danger(parent: QWidget, title: str, message: str) -> bool:
        """Confirmación para acciones peligrosas (con icono de warning)."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(f"⚠️ {title}")
        msg.setText(message)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        # Aplicar tema al QMessageBox
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg, core)
        except Exception:
            pass
        return msg.exec() == QMessageBox.StandardButton.Yes
    
    @staticmethod
    def input_text(parent: QWidget, title: str, label: str, default: str = "") -> Tuple[str, bool]:
        """Solicita texto al usuario. Retorna (texto, ok)."""
        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(parent, title, label, text=default)
        return text, ok
    
    @staticmethod
    def input_number(parent: QWidget, title: str, label: str, 
                     default: float = 0, min_val: float = 0, 
                     max_val: float = 999999, decimals: int = 2) -> Tuple[float, bool]:
        """Solicita un número al usuario. Retorna (número, ok)."""
        from PyQt6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getDouble(
            parent, title, label, default, min_val, max_val, decimals
        )
        return value, ok
    
    @staticmethod
    def select_option(parent: QWidget, title: str, label: str, 
                     options: list) -> Tuple[str, bool]:
        """Permite seleccionar de una lista. Retorna (opción, ok)."""
        from PyQt6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(parent, title, label, options, 0, False)
        return item, ok

class ProgressDialog(QProgressDialog):
    """Diálogo de progreso mejorado."""
    
    def __init__(self, parent: QWidget, title: str = "Procesando...", 
                 message: str = "Por favor espere...", cancelable: bool = True):
        super().__init__(message, "Cancelar" if cancelable else None, 0, 100, parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumDuration(500)
        self.setAutoClose(True)
        self.setAutoReset(True)
    
    def update_progress(self, value: int, message: str = None):
        """Actualiza el progreso."""
        self.setValue(value)
        if message:
            self.setLabelText(message)
        QApplication.processEvents()

class LoadingDialog(QDialog):
    """Diálogo de carga simple (sin barra de progreso)."""
    
    def __init__(self, parent: QWidget, message: str = "Cargando..."):
        super().__init__(parent)
        self.setWindowTitle("Por favor espere")
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.CustomizeWindowHint | 
            Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"⏳ {message}"))
        self.setMinimumWidth(250)
        
        # Centrar en pantalla
        self._center_on_parent()
    
    def _center_on_parent(self):
        """Centra el diálogo sobre su padre o en la pantalla."""
        center_dialog(self)
    
    def show_for(self, duration_ms: int = 2000):
        """Muestra el diálogo por un tiempo determinado."""
        self._center_on_parent()
        self.show()
        QTimer.singleShot(duration_ms, self.accept)

def center_dialog(dialog: QDialog):
    """
    Centra un diálogo sobre su ventana padre o en la pantalla.
    Llamar después de construir el diálogo y antes de exec().
    """
    parent = dialog.parent()
    
    if parent and hasattr(parent, 'geometry'):
        # Centrar sobre el padre
        parent_geom = parent.geometry()
        dialog_geom = dialog.frameGeometry()
        
        x = parent_geom.x() + (parent_geom.width() - dialog_geom.width()) // 2
        y = parent_geom.y() + (parent_geom.height() - dialog_geom.height()) // 2
        
        dialog.move(x, y)
    else:
        # Centrar en la pantalla principal
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.availableGeometry()
            dialog_geom = dialog.frameGeometry()
            
            x = (screen_geom.width() - dialog_geom.width()) // 2
            y = (screen_geom.height() - dialog_geom.height()) // 2
            
            dialog.move(screen_geom.x() + x, screen_geom.y() + y)

class QuickMessage:
    """Mensajes rápidos sin crear objetos."""
    
    @staticmethod
    def ok(parent, msg: str):
        """Muestra mensaje de información."""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Información")
        msg_box.setText(msg)
        # Aplicar tema
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg_box, core)
        except Exception:
            pass
        msg_box.exec()
    
    @staticmethod
    def fail(parent, msg: str):
        """Muestra mensaje de error."""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(msg)
        # Aplicar tema
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg_box, core)
        except Exception:
            pass
        msg_box.exec()
    
    @staticmethod
    def ask(parent, msg: str) -> bool:
        """Muestra mensaje de confirmación."""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Confirmar")
        msg_box.setText(msg)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        # Aplicar tema
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(msg_box, core)
        except Exception:
            pass
        result = msg_box.exec()
        return result == QMessageBox.StandardButton.Yes

class CenteredDialog(QDialog):
    """
    Diálogo que se centra automáticamente sobre su padre o en la pantalla.
    Usar como clase base en lugar de QDialog para diálogos que necesitan centrarse.
    Aplica tema automáticamente.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_theme()
    
    def _apply_theme(self):
        """Aplicar tema al diálogo."""
        try:
            from app.utils.theme_helpers import ThemeHelper
            from app.core import STATE
            core = getattr(STATE, 'core', None)
            ThemeHelper.apply_dialog_theme(self, core)
        except Exception:
            pass
    
    def showEvent(self, event):
        """Se llama cuando el diálogo se muestra - lo centramos aquí."""
        super().showEvent(event)
        self._center()
        # Re-aplicar tema por si cambió
        self._apply_theme()
    
    def _center(self):
        """Centra el diálogo sobre su padre o en la pantalla."""
        center_dialog(self)
    
    def exec(self):
        """Centra antes de ejecutar."""
        self._center()
        return super().exec()

# Alias cortos para uso rápido
Dialogs = DialogBase
Q = QuickMessage

# Exportar todo lo necesario
__all__ = [
    'DialogBase', 'Dialogs',
    'ProgressDialog', 'LoadingDialog',
    'QuickMessage', 'Q',
    'center_dialog', 'CenteredDialog'
]
