"""
Shortcuts Panel - TITAN POS
Panel flotante deslizable con todos los atajos de teclado disponibles.
Se activa con Shift+F1.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets


class ShortcutsPanel(QtWidgets.QWidget):
    """
    Panel flotante deslizable con todos los atajos de teclado.
    
    Se muestra/oculta con Shift+F1. Slide-in desde la derecha.
    """
    
    # Catálogo completo de atajos organizados por categoría
    SHORTCUTS: Dict[str, List[Tuple[str, str]]] = {
        "📍 NAVEGACIÓN": [
            ("F1", "Ir a Ventas"),
            ("F2", "Ir a Clientes"),
            ("F3", "Ir a Productos"),
            ("F4", "Ir a Inventario"),
            ("F5", "Ir a Turnos"),
            ("F6", "Ir a Empleados"),
        ],
        "💳 VENTAS": [
            ("F12", "Cobrar / Finalizar venta"),
            ("Enter", "Agregar producto al carrito"),
            ("F10", "Búsqueda avanzada de productos"),
            ("F9", "Verificador de precios"),
            ("F11", "Precio de mayoreo"),
            ("Ctrl+P", "Producto común (venta rápida)"),
        ],
        "🏷️ DESCUENTOS": [
            ("Ctrl+D", "Descuento a línea seleccionada"),
            ("Ctrl+Shift+D", "Descuento global a toda la venta"),
            ("Click en Total", "También abre descuento global"),
        ],
        "🛒 CARRITO": [
            ("+  /  =", "Aumentar cantidad (+1)"),
            ("-", "Disminuir cantidad (-1)"),
            ("Del", "Eliminar producto seleccionado"),
            ("Backspace", "Eliminar producto seleccionado"),
            ("Doble-click", "Cambiar precio del producto"),
        ],
        "📋 TICKETS": [
            ("Ctrl+T", "Nuevo ticket (multi-venta)"),
            ("Ctrl+W", "Cerrar ticket actual"),
            ("Tab", "Siguiente ticket"),
            ("Shift+Tab", "Ticket anterior"),
            ("F4 (en Ventas)", "Agregar nota al ticket"),
            ("PgDn", "Reimprimir último ticket"),
        ],
        "💵 CAJA": [
            ("F7", "Entrada de efectivo"),
            ("F8", "Salida de efectivo"),
            ("Ctrl+O", "Abrir cajón (requiere auth)"),
        ],
        "👤 CLIENTES": [
            ("=", "Asignar cliente a la venta"),
            ("Esc", "Limpiar cliente asignado"),
        ],
        "⚙️ GESTIÓN": [
            ("Ctrl+X", "Cancelar última venta"),
            ("Ctrl+H", "Ver ventas del turno"),
            ("Shift+F1", "Mostrar/ocultar este panel"),
        ],
    }
    
    closed = QtCore.pyqtSignal()
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedWidth(420)
        self._is_visible = False
        
        self._setup_ui()
        self._setup_shortcuts()
    
    def _setup_ui(self):
        """Construye la interfaz del panel."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sombra
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QtGui.QColor(0, 0, 0, 150))
        shadow.setOffset(-10, 0)
        
        # Container principal
        container = QtWidgets.QFrame()
        container.setGraphicsEffect(shadow)
        container.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2a2f38, stop:1 #1a1d23);
                border-left: 3px solid #00C896;
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
            }
        """)
        
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # === Header ===
        header = QtWidgets.QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("""
            QFrame {
                background: rgba(0, 200, 150, 0.15);
                border: none;
                border-top-left-radius: 16px;
            }
        """)
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 15, 0)
        
        title = QtWidgets.QLabel("⌨️  ATAJOS DE TECLADO")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #00C896;
            background: transparent;
            border: none;
        """)
        
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #888;
                border: none;
                border-radius: 18px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.3);
                color: #FF4757;
            }
        """)
        close_btn.clicked.connect(self.slide_out)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        
        container_layout.addWidget(header)
        
        # === Scroll Area con atajos ===
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255, 255, 255, 0.05);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 200, 150, 0.4);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        content = QtWidgets.QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(20, 15, 20, 20)
        content_layout.setSpacing(20)
        
        # Agregar cada categoría
        for category, shortcuts in self.SHORTCUTS.items():
            # Título de categoría
            cat_label = QtWidgets.QLabel(category)
            cat_label.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                color: #00C896;
                background: transparent;
                border: none;
                padding-bottom: 8px;
                border-bottom: 1px solid rgba(0, 200, 150, 0.3);
            """)
            content_layout.addWidget(cat_label)
            
            # Atajos de la categoría
            for key, desc in shortcuts:
                row = QtWidgets.QHBoxLayout()
                row.setSpacing(12)
                
                # Badge del atajo
                key_label = QtWidgets.QLabel(key)
                key_label.setFixedWidth(120)
                key_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                key_label.setStyleSheet("""
                    background: rgba(0, 200, 150, 0.15);
                    border: 1px solid rgba(0, 200, 150, 0.3);
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                    font-size: 12px;
                    font-weight: bold;
                    color: #00C896;
                """)
                
                # Descripción
                desc_label = QtWidgets.QLabel(desc)
                desc_label.setStyleSheet("""
                    color: #b0b4bb;
                    font-size: 13px;
                    background: transparent;
                    border: none;
                """)
                
                row.addWidget(key_label)
                row.addWidget(desc_label, 1)
                content_layout.addLayout(row)
            
            # Espaciador entre categorías
            content_layout.addSpacing(5)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        container_layout.addWidget(scroll)
        
        # === Footer ===
        footer = QtWidgets.QFrame()
        footer.setFixedHeight(50)
        footer.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.2);
                border: none;
                border-bottom-left-radius: 16px;
            }
        """)
        footer_layout = QtWidgets.QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        
        tip = QtWidgets.QLabel("💡 Presiona Shift+F1 o Esc para cerrar")
        tip.setStyleSheet("""
            color: #666;
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        tip.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(tip)
        
        container_layout.addWidget(footer)
        main_layout.addWidget(container)
    
    def _setup_shortcuts(self):
        """Configura atajos para cerrar el panel."""
        # Esc para cerrar
        esc_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.slide_out)
    
    def slide_in(self):
        """Animación de entrada desde la derecha."""
        if self._is_visible:
            return
        
        parent = self.parent()
        if not parent:
            return
        
        # Posicionar fuera de la pantalla
        parent_rect = parent.rect()
        self.setFixedHeight(parent_rect.height())
        
        start_x = parent_rect.width()
        end_x = parent_rect.width() - self.width()
        
        self.move(start_x, 0)
        self.show()
        self.raise_()
        
        # Animación
        self.slide_anim = QtCore.QPropertyAnimation(self, b"pos")
        self.slide_anim.setDuration(250)
        self.slide_anim.setStartValue(QtCore.QPoint(start_x, 0))
        self.slide_anim.setEndValue(QtCore.QPoint(end_x, 0))
        self.slide_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self.slide_anim.start()
        
        self._is_visible = True
    
    def slide_out(self):
        """Animación de salida hacia la derecha."""
        if not self._is_visible:
            return
        
        parent = self.parent()
        if not parent:
            self.hide()
            return
        
        parent_rect = parent.rect()
        end_x = parent_rect.width()
        
        self.slide_anim = QtCore.QPropertyAnimation(self, b"pos")
        self.slide_anim.setDuration(200)
        self.slide_anim.setStartValue(self.pos())
        self.slide_anim.setEndValue(QtCore.QPoint(end_x, 0))
        self.slide_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        self.slide_anim.finished.connect(self._on_slide_out_finished)
        self.slide_anim.start()
    
    def _on_slide_out_finished(self):
        """Callback cuando termina la animación de salida."""
        self.hide()
        self._is_visible = False
        self.closed.emit()
    
    def toggle(self):
        """Alterna visibilidad del panel."""
        if self._is_visible:
            self.slide_out()
        else:
            self.slide_in()
    
    def is_panel_visible(self) -> bool:
        """Retorna si el panel está visible."""
        return self._is_visible
