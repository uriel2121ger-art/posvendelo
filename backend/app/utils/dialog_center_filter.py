"""
Dialog Center Event Filter - Centra TODOS los diálogos automáticamente

Esta solución usa un Event Filter a nivel de aplicación que intercepta
CUALQUIER ventana que se muestre y la centra si es un diálogo.
"""
import logging

from PyQt6 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class DialogCenterFilter(QtCore.QObject):
    """Event filter que centra automáticamente todos los diálogos."""
    
    def eventFilter(self, obj, event):
        # Interceptar evento Show de cualquier QDialog o QMessageBox
        if event.type() == QtCore.QEvent.Type.Show:
            if isinstance(obj, (QtWidgets.QDialog, QtWidgets.QMessageBox)):
                # Usar QTimer para centrar después del show
                QtCore.QTimer.singleShot(1, lambda: self._center_dialog(obj))
        
        return super().eventFilter(obj, event)
    
    def _center_dialog(self, dialog):
        """Centra el diálogo en su padre o en la pantalla."""
        try:
            parent = dialog.parent()
            
            if parent and parent.isVisible():
                # Centrar en el padre
                parent_geo = parent.frameGeometry()
                x = parent_geo.x() + (parent_geo.width() - dialog.width()) // 2
                y = parent_geo.y() + (parent_geo.height() - dialog.height()) // 2
            else:
                # Centrar en la pantalla
                screen = QtWidgets.QApplication.primaryScreen()
                if screen:
                    screen_geo = screen.geometry()
                    x = (screen_geo.width() - dialog.width()) // 2
                    y = (screen_geo.height() - dialog.height()) // 2
                else:
                    return
            
            # Asegurar que no salga de la pantalla
            screen = dialog.screen() or QtWidgets.QApplication.primaryScreen()
            if screen:
                sg = screen.geometry()
                x = max(sg.x(), min(x, sg.right() - dialog.width()))
                y = max(sg.y(), min(y, sg.bottom() - dialog.height()))
            
            dialog.move(x, y)
        # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
        except Exception as e:
            logger.debug(f"Error centering dialog: {e}")

# Instancia global del filtro
_dialog_filter = None

def install_dialog_center_filter(app: QtWidgets.QApplication):
    """
    Instala el filtro de centrado en la aplicación.
    
    DEBE llamarse después de crear QApplication.
    
    Uso:
        app = QtWidgets.QApplication(sys.argv)
        install_dialog_center_filter(app)
    """
    global _dialog_filter
    
    if _dialog_filter is None:
        _dialog_filter = DialogCenterFilter()
    
    app.installEventFilter(_dialog_filter)
    print("✅ Auto-centrado de diálogos activado")
