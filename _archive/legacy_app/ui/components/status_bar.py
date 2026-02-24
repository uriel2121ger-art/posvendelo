"""
Status Bar - TITAN POS
Barra de estado con indicadores del sistema: conexión, usuario, sucursal, turno, ventas.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets

# Estados de conexión con configuración visual
CONNECTION_STATES: Dict[str, Dict[str, Any]] = {
    "online": {
        "icon": "🟢",
        "text": "En línea",
        "color": "#00C896",
        "tooltip": "Conexión estable con el servidor central",
    },
    "offline": {
        "icon": "🔴",
        "text": "Sin conexión",
        "color": "#FF4757",
        "tooltip": "Modo offline - Las ventas se sincronizarán cuando vuelva la conexión",
    },
    "syncing": {
        "icon": "🟡",
        "text": "Sincronizando...",
        "color": "#FFA502",
        "tooltip": "Sincronizando datos pendientes con el servidor",
    },
    "degraded": {
        "icon": "🟠",
        "text": "Conexión lenta",
        "color": "#FF7F50",
        "tooltip": "Conexión inestable - Algunas funciones pueden estar lentas",
    },
}

class StatusItem(QtWidgets.QWidget):
    """
    Item individual del status bar.
    
    Muestra un icono y texto, opcionalmente clickeable.
    """
    
    clicked = QtCore.pyqtSignal()
    
    def __init__(
        self,
        icon: str,
        text: str,
        clickable: bool = True,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.clickable = clickable
        self._setup_ui(icon, text)
        
        if clickable:
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    
    def _setup_ui(self, icon: str, text: str):
        """Construye la UI del item."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)
        
        self.icon_label = QtWidgets.QLabel(icon)
        self.icon_label.setStyleSheet("""
            font-size: 14px;
            background: transparent;
            border: none;
        """)
        
        self.text_label = QtWidgets.QLabel(text)
        self.text_label.setStyleSheet("""
            font-size: 12px;
            color: #a0a4ab;
            background: transparent;
            border: none;
        """)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        
        self.setStyleSheet("""
            StatusItem {
                background: transparent;
            }
            StatusItem:hover {
                background: rgba(255, 255, 255, 0.05);
            }
        """)
    
    def mousePressEvent(self, event):
        """Emite señal al hacer click."""
        if self.clickable and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def set_icon(self, icon: str):
        """Actualiza el icono."""
        self.icon_label.setText(icon)
    
    def set_text(self, text: str):
        """Actualiza el texto."""
        self.text_label.setText(text)
    
    def set_color(self, color: str):
        """Cambia el color del texto."""
        self.text_label.setStyleSheet(f"""
            font-size: 12px;
            color: {color};
            background: transparent;
            border: none;
        """)

class StatusBar(QtWidgets.QFrame):
    """
    Barra de estado con indicadores del sistema.
    
    Muestra: Conexión, Usuario, Sucursal, Turno, Ventas, Hora.
    Cada indicador es clickeable para ver más detalles.
    """
    
    # Señales para clicks en cada indicador
    clicked_connection = QtCore.pyqtSignal()
    clicked_user = QtCore.pyqtSignal()
    clicked_branch = QtCore.pyqtSignal()
    clicked_turn = QtCore.pyqtSignal()
    clicked_sales = QtCore.pyqtSignal()
    
    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        
        self.setFixedHeight(40)
        self.setStyleSheet("""
            StatusBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1d23, stop:1 #12151a);
                border-top: 1px solid #2d3138;
            }
        """)
        
        self._setup_ui()
        self._start_update_timer()
    
    def _setup_ui(self):
        """Construye la interfaz del status bar."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(0)
        
        # === Conexión ===
        self.connection_indicator = StatusItem("🟢", "En línea", clickable=True)
        self.connection_indicator.clicked.connect(self.clicked_connection.emit)
        self.connection_indicator.setToolTip("Estado de conexión con el servidor")
        
        # === Usuario ===
        self.user_indicator = StatusItem("👤", "Sin usuario", clickable=True)
        self.user_indicator.clicked.connect(self.clicked_user.emit)
        self.user_indicator.setToolTip("Click para cambiar usuario")
        
        # === Sucursal ===
        self.branch_indicator = StatusItem("🏪", "Sin sucursal", clickable=True)
        self.branch_indicator.clicked.connect(self.clicked_branch.emit)
        self.branch_indicator.setToolTip("Información de la sucursal actual")
        
        # === Turno ===
        self.turn_indicator = StatusItem("⏱️", "Sin turno", clickable=True)
        self.turn_indicator.clicked.connect(self.clicked_turn.emit)
        self.turn_indicator.setToolTip("Click para ver resumen del turno")
        
        # === Ventas del turno ===
        self.sales_indicator = StatusItem("💰", "$0.00", clickable=True)
        self.sales_indicator.clicked.connect(self.clicked_sales.emit)
        self.sales_indicator.setToolTip("Total vendido en el turno actual")
        
        # === Hora ===
        self.time_indicator = StatusItem("🕐", "--:--:--", clickable=False)
        self.time_indicator.setToolTip("Hora del sistema")
        
        # Función para crear separadores
        def create_separator():
            sep = QtWidgets.QFrame()
            sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            sep.setFixedSize(1, 20)
            sep.setStyleSheet("background: #3d4148;")
            return sep
        
        # Agregar widgets al layout
        layout.addWidget(self.connection_indicator)
        layout.addWidget(create_separator())
        layout.addWidget(self.user_indicator)
        layout.addWidget(create_separator())
        layout.addWidget(self.branch_indicator)
        layout.addWidget(create_separator())
        layout.addWidget(self.turn_indicator)
        layout.addWidget(create_separator())
        layout.addWidget(self.sales_indicator)
        layout.addStretch()
        layout.addWidget(self.time_indicator)
    
    def _start_update_timer(self):
        """Inicia el timer para actualizar la hora cada segundo."""
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._update_time)
        self.timer.start(1000)
        self._update_time()  # Actualizar inmediatamente
    
    def _update_time(self):
        """Actualiza el indicador de hora."""
        now = datetime.now()
        self.time_indicator.set_text(now.strftime("%H:%M:%S"))
    
    def update_connection(self, state: str):
        """
        Actualiza el indicador de conexión.
        
        Args:
            state: 'online', 'offline', 'syncing', o 'degraded'
        """
        config = CONNECTION_STATES.get(state, CONNECTION_STATES["offline"])
        self.connection_indicator.set_icon(config["icon"])
        self.connection_indicator.set_text(config["text"])
        self.connection_indicator.set_color(config["color"])
        self.connection_indicator.setToolTip(config["tooltip"])
    
    def update_user(self, name: str, role: str):
        """
        Actualiza el indicador de usuario.
        
        Args:
            name: Nombre del usuario
            role: Rol (Admin, Cajero, etc.)
        """
        display_name = name if len(name) <= 15 else f"{name[:12]}..."
        self.user_indicator.set_text(f"{display_name} ({role})")
        self.user_indicator.setToolTip(f"Usuario: {name}\nRol: {role}\nClick para cambiar")
    
    def update_branch(self, name: str, branch_id: Optional[int] = None):
        """
        Actualiza el indicador de sucursal.
        
        Args:
            name: Nombre de la sucursal
            branch_id: ID opcional de la sucursal
        """
        display_name = name if len(name) <= 20 else f"{name[:17]}..."
        self.branch_indicator.set_text(display_name)
        tooltip = f"Sucursal: {name}"
        if branch_id:
            tooltip += f"\nID: {branch_id}"
        self.branch_indicator.setToolTip(tooltip)
    
    def update_turn(self, turn_id: Optional[int], active: bool, start_time: Optional[str] = None):
        """
        Actualiza el indicador de turno.
        
        Args:
            turn_id: ID del turno (None si no hay turno)
            active: True si el turno está activo
            start_time: Hora de inicio opcional
        """
        if active and turn_id:
            self.turn_indicator.set_text(f"Turno #{turn_id}")
            self.turn_indicator.set_color("#00C896")
            tooltip = f"Turno activo: #{turn_id}"
            if start_time:
                tooltip += f"\nIniciado: {start_time}"
            self.turn_indicator.setToolTip(tooltip)
        else:
            self.turn_indicator.set_text("Sin turno")
            self.turn_indicator.set_color("#888888")
            self.turn_indicator.setToolTip("No hay turno activo\nClick para abrir turno")
    
    def update_sales(self, total: float, count: int = 0):
        """
        Actualiza el indicador de ventas del turno.
        
        Args:
            total: Total vendido
            count: Número de ventas
        """
        self.sales_indicator.set_text(f"${total:,.2f}")
        
        tooltip = f"Ventas del turno: ${total:,.2f}"
        if count > 0:
            tooltip += f"\nTransacciones: {count}"
        self.sales_indicator.setToolTip(tooltip)
        
        # Colorear según monto
        if total >= 10000:
            self.sales_indicator.set_color("#00C896")  # Verde para buenos números
        elif total >= 1000:
            self.sales_indicator.set_color("#FFA502")  # Naranja para regular
        else:
            self.sales_indicator.set_color("#a0a4ab")  # Gris normal
    
    def set_all_from_state(
        self,
        connection: str = "online",
        user_name: str = "",
        user_role: str = "",
        branch_name: str = "",
        turn_id: Optional[int] = None,
        turn_active: bool = False,
        total_sales: float = 0.0,
        sales_count: int = 0,
    ):
        """
        Actualiza todos los indicadores de una vez.
        
        Útil para sincronizar el estado completo.
        """
        self.update_connection(connection)
        if user_name:
            self.update_user(user_name, user_role)
        if branch_name:
            self.update_branch(branch_name)
        self.update_turn(turn_id, turn_active)
        self.update_sales(total_sales, sales_count)

    def closeEvent(self, event):
        """Cleanup timers on close."""
        if hasattr(self, 'timer') and self.timer:
            self.timer.stop()
        super().closeEvent(event)
