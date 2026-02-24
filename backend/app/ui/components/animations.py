"""
Cart Animations - TITAN POS
Animaciones suaves para el carrito de ventas y eventos de la UI.
"""

from __future__ import annotations

import weakref
from typing import Callable, Optional

from PyQt6 import QtCore, QtGui, QtWidgets


class CartAnimations:
    """
    Animaciones para el carrito de ventas.
    
    Incluye:
    - Agregar producto (slide-in + flash verde)
    - Eliminar producto (fade-out + collapse)
    - Error (shake)
    - Cambio de cantidad (pulse)
    """
    
    @staticmethod
    def add_product(
        table: QtWidgets.QTableWidget,
        row: int,
        accent_color: str = "#00C896",
    ):
        """
        Animación al agregar producto al carrito.

        Flash verde en la fila + expansión suave.
        """
        if row < 0 or row >= table.rowCount():
            return

        table_ref = weakref.ref(table)

        # Guardar colores originales
        original_colors = []
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                original_colors.append((col, item.background()))
                # Flash color de acento
                item.setBackground(QtGui.QColor(accent_color))

        # Restaurar colores después de 300ms
        def restore_colors():
            try:
                t = table_ref()
                if t is None:
                    return
                for col, bg in original_colors:
                    item = t.item(row, col)
                    if item:
                        item.setBackground(bg)
            except RuntimeError:
                pass

        QtCore.QTimer.singleShot(300, restore_colors)

        # Animación de altura (expansión)
        original_height = 45
        table.setRowHeight(row, 0)

        steps = 8
        step_delay = 25

        def animate_height(step: int = 0):
            try:
                t = table_ref()
                if t is None:
                    return
                if step <= steps:
                    new_height = int(original_height * (step / steps))
                    t.setRowHeight(row, new_height)
                    next_step = step + 1
                    QtCore.QTimer.singleShot(step_delay, lambda: animate_height(next_step))
            except RuntimeError:
                pass

        animate_height()
    
    @staticmethod
    def remove_product(
        table: QtWidgets.QTableWidget,
        row: int,
        callback: Optional[Callable[[], None]] = None,
        error_color: str = "#FF4757",
    ):
        """
        Animación al eliminar producto del carrito.

        Flash rojo + colapso de fila, luego ejecuta callback.
        """
        if row < 0 or row >= table.rowCount():
            if callback:
                callback()
            return

        table_ref = weakref.ref(table)

        # Flash rojo
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                item.setBackground(QtGui.QColor(error_color))

        # Animación de colapso
        original_height = table.rowHeight(row)
        steps = 6
        step_delay = 30

        def collapse(step: int = 0):
            try:
                t = table_ref()
                if t is None:
                    if callback:
                        callback()
                    return
                if step <= steps:
                    new_height = int(original_height * (1 - step / steps))
                    t.setRowHeight(row, max(0, new_height))
                    next_step = step + 1
                    QtCore.QTimer.singleShot(step_delay, lambda: collapse(next_step))
                else:
                    if callback:
                        callback()
            except RuntimeError:
                if callback:
                    callback()

        # Iniciar colapso después del flash
        QtCore.QTimer.singleShot(150, collapse)
    
    @staticmethod
    def shake_error(widget: QtWidgets.QWidget, intensity: int = 10):
        """
        Animación de sacudida para indicar error.

        Sacude el widget horizontalmente (útil para campos de entrada).
        """
        original_pos = widget.pos()
        widget_ref = weakref.ref(widget)

        # Patrón de sacudida
        shake_pattern = [
            intensity, -intensity * 2,
            intensity * 1.5, -intensity,
            intensity * 0.5, -intensity * 0.3,
            0
        ]

        def create_shake_callback(offset: float):
            def safe_move():
                try:
                    w = widget_ref()
                    if w is not None:
                        w.move(original_pos.x() + int(offset), original_pos.y())
                except RuntimeError:
                    pass
            return safe_move

        for i, offset in enumerate(shake_pattern):
            QtCore.QTimer.singleShot(i * 40, create_shake_callback(offset))
    
    @staticmethod
    def pulse_widget(widget: QtWidgets.QWidget, scale: float = 1.05):
        """
        Efecto de pulso en un widget.

        Nota: Qt no soporta transform scale directamente,
        este es un efecto visual alternativo con opacidad.
        """
        widget_ref = weakref.ref(widget)

        try:
            # Crear efecto de opacidad
            effect = QtWidgets.QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

            # Animación de opacidad
            anim = QtCore.QPropertyAnimation(effect, b"opacity")
            anim.setDuration(200)
            anim.setKeyValueAt(0, 1.0)
            anim.setKeyValueAt(0.5, 0.7)
            anim.setKeyValueAt(1, 1.0)
            anim.setEasingCurve(QtCore.QEasingCurve.Type.InOutQuad)

            # CRITICAL FIX: Usar función segura que verifica si el widget existe
            def safe_cleanup():
                try:
                    w = widget_ref()
                    if w is not None:
                        w.setGraphicsEffect(None)
                except RuntimeError:
                    # Widget ya fue eliminado, ignorar
                    pass

            anim.finished.connect(safe_cleanup)
            anim.start()

            # Guardar referencia para evitar garbage collection
            widget._pulse_anim = anim
        except RuntimeError:
            # Widget fue eliminado antes de configurar la animación
            pass
    
    @staticmethod
    def flash_success(widget: QtWidgets.QWidget, color: str = "#00C896"):
        """
        Flash verde rápido para indicar éxito.
        """
        original_style = widget.styleSheet()
        widget_ref = weakref.ref(widget)

        # Aplicar color de éxito
        widget.setStyleSheet(original_style + f"; background-color: {color};")

        # Restaurar después de 200ms
        def restore_style():
            try:
                w = widget_ref()
                if w is not None:
                    w.setStyleSheet(original_style)
            except RuntimeError:
                pass

        QtCore.QTimer.singleShot(200, restore_style)
    
    @staticmethod
    def flash_error(widget: QtWidgets.QWidget, color: str = "#FF4757"):
        """
        Flash rojo rápido para indicar error.
        """
        original_style = widget.styleSheet()
        widget_ref = weakref.ref(widget)

        # Aplicar color de error
        widget.setStyleSheet(original_style + f"; background-color: {color};")

        # Restaurar después de 200ms
        def restore_style():
            try:
                w = widget_ref()
                if w is not None:
                    w.setStyleSheet(original_style)
            except RuntimeError:
                pass

        QtCore.QTimer.singleShot(200, restore_style)

class SaleCompletedOverlay(QtWidgets.QWidget):
    """
    Overlay animado que se muestra al completar una venta exitosamente.
    
    Muestra un check grande animado con el monto y se cierra automáticamente.
    """
    
    finished = QtCore.pyqtSignal()
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        # REMOVED: WA_DeleteOnClose causaba que el widget se eliminara pero la referencia
        # en sales_tab._sale_overlay seguía existiendo, causando segfault al reusar
        # self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Construye la UI del overlay."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # Contenedor central
        self.container = QtWidgets.QFrame()
        self.container.setFixedSize(350, 280)
        self.container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(42, 47, 56, 0.98), stop:1 rgba(26, 29, 35, 0.98));
                border-radius: 20px;
                border: 2px solid #00C896;
            }
        """)
        
        container_layout = QtWidgets.QVBoxLayout(self.container)
        container_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        container_layout.setSpacing(15)
        
        # Check animado
        self.check_label = QtWidgets.QLabel("✓")
        self.check_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.check_label.setStyleSheet("""
            font-size: 80px;
            font-weight: bold;
            color: #00C896;
            background: transparent;
            border: none;
        """)
        
        # Texto
        self.text_label = QtWidgets.QLabel("¡VENTA COMPLETADA!")
        self.text_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: white;
            background: transparent;
            border: none;
        """)
        
        # Monto
        self.amount_label = QtWidgets.QLabel("$0.00")
        self.amount_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.amount_label.setStyleSheet("""
            font-size: 36px;
            font-weight: bold;
            color: #00C896;
            background: transparent;
            border: none;
        """)
        
        # Cambio (opcional)
        self.change_label = QtWidgets.QLabel("")
        self.change_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.change_label.setStyleSheet("""
            font-size: 16px;
            color: #a0a4ab;
            background: transparent;
            border: none;
        """)
        
        container_layout.addWidget(self.check_label)
        container_layout.addWidget(self.text_label)
        container_layout.addWidget(self.amount_label)
        container_layout.addWidget(self.change_label)
        
        layout.addWidget(self.container)
    
    def play(
        self,
        amount: float,
        change: Optional[float] = None,
        ticket_id: Optional[int] = None,
        duration: int = 2000,  # Duración en ms
    ):
        """
        Muestra la animación de venta completada.
        
        Args:
            amount: Monto total de la venta
            change: Cambio entregado (opcional)
            ticket_id: ID del ticket (opcional)
            duration: Tiempo que se muestra en ms
        """
        self.amount_label.setText(f"${amount:,.2f}")
        
        if change is not None and change > 0:
            self.change_label.setText(f"Cambio: ${change:,.2f}")
            self.change_label.show()
        else:
            self.change_label.hide()
        
        if ticket_id:
            self.text_label.setText(f"¡VENTA #{ticket_id} COMPLETADA!")
        
        # Resize y posicionar
        if self.parent():
            self.resize(self.parent().size())
            self.move(0, 0)
        
        self.show()
        self.raise_()
        
        # Animación de entrada del check
        self._animate_check()
        
        # Cerrar después de la duración
        QtCore.QTimer.singleShot(duration, self._close_animation)
    
    def _animate_check(self):
        """Anima la aparición del check."""
        # CRITICAL FIX: Verificar que el widget aún existe antes de animar
        if not self.check_label or not self.isVisible():
            return
        
        # Empezar pequeño
        try:
            self.check_label.setStyleSheet("""
                font-size: 1px;
                font-weight: bold;
                color: #00C896;
                background: transparent;
                border: none;
            """)
        except RuntimeError:
            # Widget ya fue eliminado
            return
        
        # Crecer gradualmente
        sizes = [10, 25, 45, 65, 85, 80]  # Rebote al final
        
        for i, size in enumerate(sizes):
            QtCore.QTimer.singleShot(
                i * 50,
                lambda s=size, widget=self.check_label: self._safe_set_style(widget, s)
            )
    
    def _safe_set_style(self, label, size):
        """Safely set style sheet, checking if widget still exists."""
        try:
            if label and hasattr(label, 'setStyleSheet'):
                label.setStyleSheet(f"""
                    font-size: {size}px;
                    font-weight: bold;
                    color: #00C896;
                    background: transparent;
                    border: none;
                """)
        except RuntimeError:
            # Widget ya fue eliminado, ignorar
            pass
    
    def _close_animation(self):
        """Animación de cierre (fade out)."""
        # CRITICAL FIX: Verificar que el widget aún existe antes de animar
        try:
            if not self.isVisible():
                self._on_close()
                return

            # CRITICAL FIX: Usar QGraphicsOpacityEffect en lugar de windowOpacity
            # porque windowOpacity no es soportado en todos los backends de Qt
            # (eglfs, linuxfb, etc.) y causa segfault
            effect = QtWidgets.QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)

            self.fade_anim = QtCore.QPropertyAnimation(effect, b"opacity")
            self.fade_anim.setDuration(300)
            self.fade_anim.setStartValue(1.0)
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.setEasingCurve(QtCore.QEasingCurve.Type.InQuad)
            self.fade_anim.finished.connect(self._on_close)
            self.fade_anim.start()
        except RuntimeError:
            # Widget ya fue eliminado, cerrar directamente
            self._on_close()
    
    def _on_close(self):
        """Callback al cerrar."""
        self.finished.emit()
        self.close()
    
    def paintEvent(self, event):
        """Dibuja el fondo semi-transparente."""
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 150))

class QuantityChangeAnimation:
    """
    Animación para cambios de cantidad en el carrito.
    """
    
    @staticmethod
    def animate_increase(
        cell: QtWidgets.QTableWidgetItem,
        color: str = "#00C896",
    ):
        """Animación de incremento de cantidad."""
        if not cell:
            return
        
        original_bg = cell.background()
        cell.setBackground(QtGui.QColor(color))
        
        # Restaurar después de 200ms
        QtCore.QTimer.singleShot(
            200,
            lambda: cell.setBackground(original_bg)
        )
    
    @staticmethod
    def animate_decrease(
        cell: QtWidgets.QTableWidgetItem,
        color: str = "#FFA502",
    ):
        """Animación de decremento de cantidad."""
        if not cell:
            return
        
        original_bg = cell.background()
        cell.setBackground(QtGui.QColor(color))
        
        # Restaurar después de 200ms
        QtCore.QTimer.singleShot(
            200,
            lambda: cell.setBackground(original_bg)
        )

# === Utilidades de animación ===

def fade_in(widget: QtWidgets.QWidget, duration: int = 300):
    """Fade in animation para un widget."""
    widget_ref = weakref.ref(widget)

    try:
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QtCore.QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        # CRITICAL FIX: Limpiar efecto al terminar de forma segura
        def safe_cleanup():
            try:
                w = widget_ref()
                if w is not None:
                    w.setGraphicsEffect(None)
            except RuntimeError:
                pass

        anim.finished.connect(safe_cleanup)
        anim.start()

        # Guardar referencia para evitar garbage collection
        widget._fade_anim = anim
    except RuntimeError:
        # Widget ya fue eliminado
        pass

def fade_out(widget: QtWidgets.QWidget, duration: int = 300, callback: Optional[Callable] = None):
    """Fade out animation para un widget."""
    widget_ref = weakref.ref(widget)

    try:
        effect = QtWidgets.QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

        anim = QtCore.QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)

        # CRITICAL FIX: Envolver callback para verificar widget
        def safe_callback():
            try:
                w = widget_ref()
                if w is not None:
                    w.setGraphicsEffect(None)
                if callback:
                    callback()
            except RuntimeError:
                # Widget destruido, aún ejecutar callback si existe
                if callback:
                    try:
                        callback()
                    except Exception:
                        pass

        anim.finished.connect(safe_callback)
        anim.start()
        widget._fade_anim = anim
    except RuntimeError:
        # Widget ya fue eliminado, ejecutar callback directamente
        if callback:
            try:
                callback()
            except Exception:
                pass

def slide_in_from_right(widget: QtWidgets.QWidget, parent: QtWidgets.QWidget, duration: int = 250):
    """Slide in desde la derecha."""
    parent_width = parent.width()
    widget_width = widget.width()
    
    start_x = parent_width
    end_x = parent_width - widget_width
    
    widget.move(start_x, widget.y())
    widget.show()
    
    anim = QtCore.QPropertyAnimation(widget, b"pos")
    anim.setDuration(duration)
    anim.setStartValue(QtCore.QPoint(start_x, widget.y()))
    anim.setEndValue(QtCore.QPoint(end_x, widget.y()))
    anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
    anim.start()
    
    widget._slide_anim = anim
