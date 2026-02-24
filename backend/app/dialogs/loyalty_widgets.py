"""
MIDAS LOYALTY WIDGET
Widget visual para mostrar información de lealtad en la pantalla de ventas

Este widget muestra:
- Saldo actual del cliente
- Puntos que ganará con la compra actual
- Nivel de lealtad
"""

from typing import Optional
from decimal import Decimal

from PyQt6 import QtCore, QtGui, QtWidgets


class LoyaltyWidget(QtWidgets.QFrame):
    """
    Widget brillante que muestra la información del monedero electrónico.
    
    Aparece cuando se selecciona un cliente en la pantalla de ventas.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.customer_id = None
        self.customer_name = ""
        self.saldo_actual = Decimal('0.00')
        self.puntos_potenciales = Decimal('0.00')
        self.nivel = "BRONCE"
        
        self._build_ui()
        self.hide()  # Oculto por defecto
    
    def _build_ui(self):
        """Construye la interfaz visual del widget"""
        # Frame con bordes brillantes
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)
        
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Título
        lbl_titulo = QtWidgets.QLabel("💰 MONEDERO ELECTRÓNICO")
        lbl_titulo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_titulo.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #FFD700;
        """)
        layout.addWidget(lbl_titulo)
        
        # Saludo personalizado
        self.lbl_saludo = QtWidgets.QLabel("Selecciona un cliente")
        self.lbl_saludo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_saludo.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self.lbl_saludo)
        
        # Saldo actual (GRANDE Y BRILLANTE)
        self.lbl_saldo = QtWidgets.QLabel("$0.00")
        self.lbl_saldo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_saldo.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            color: #00C851;
            margin: 5px 0;
        """)
        layout.addWidget(self.lbl_saldo)
        
        lbl_saldo_desc = QtWidgets.QLabel("en tu monedero")
        lbl_saldo_desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_saldo_desc.setStyleSheet("font-size: 10px; color: #999;")
        layout.addWidget(lbl_saldo_desc)
        
        # Separador
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(line)
        
        # Puntos que ganará
        self.lbl_ganara = QtWidgets.QLabel("Esta compra te generará:")
        self.lbl_ganara.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_ganara.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(self.lbl_ganara)
        
        self.lbl_puntos_nuevos = QtWidgets.QLabel("+$0.00")
        self.lbl_puntos_nuevos.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_puntos_nuevos.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #FF9800;
        """)
        layout.addWidget(self.lbl_puntos_nuevos)
        
        # Nivel de lealtad
        self.lbl_nivel = QtWidgets.QLabel("🥉 BRONCE")
        self.lbl_nivel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_nivel.setStyleSheet("""
            font-size: 12px;
            font-weight: bold;
            padding: 5px;
            border-radius: 10px;
            background-color: #CD7F32;
            color: white;
        """)
        layout.addWidget(self.lbl_nivel)
        
        self.setLayout(layout)
        
        # Estilo del frame principal
        self.setStyleSheet("""
            LoyaltyWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #FFF9E6, stop:1 #FFE6B3);
                border: 2px solid #FFD700;
                border-radius: 15px;
            }
        """)
    
    def set_customer(self, customer_id: int, customer_name: str, saldo: Decimal, nivel: str = "BRONCE"):
        """
        Establece el cliente actual y muestra su información.
        
        Args:
            customer_id: ID del cliente
            customer_name: Nombre del cliente
            saldo: Saldo actual en puntos
            nivel: Nivel de lealtad
        """
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.saldo_actual = saldo
        self.nivel = nivel
        
        # Actualizar UI
        self.lbl_saludo.setText(f"Hola {customer_name}! 👋")
        self.lbl_saldo.setText(f"${saldo:.2f}")
        
        # Actualizar nivel con emoji y color
        nivel_info = self._get_nivel_info(nivel)
        self.lbl_nivel.setText(f"{nivel_info['emoji']} {nivel}")
        self.lbl_nivel.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            padding: 5px 15px;
            border-radius: 10px;
            background-color: {nivel_info['color']};
            color: white;
        """)
        
        self.show()
    
    def update_puntos_potenciales(self, puntos: Decimal):
        """
        Actualiza los puntos que el cliente ganará con la compra actual.
        
        Args:
            puntos: Puntos que ganará
        """
        self.puntos_potenciales = puntos
        
        if puntos > 0:
            self.lbl_puntos_nuevos.setText(f"+${puntos:.2f}")
            self.lbl_ganara.show()
            self.lbl_puntos_nuevos.show()
            
            # Animación de brillo (efecto llamativo)
            self._animate_glow()
        else:
            self.lbl_ganara.hide()
            self.lbl_puntos_nuevos.hide()
    
    def clear(self):
        """Limpia el widget y lo oculta"""
        self.customer_id = None
        self.customer_name = ""
        self.saldo_actual = Decimal('0.00')
        self.puntos_potenciales = Decimal('0.00')
        self.nivel = "BRONCE"
        
        self.lbl_saludo.setText("Selecciona un cliente")
        self.lbl_saldo.setText("$0.00")
        self.lbl_puntos_nuevos.setText("+$0.00")
        self.lbl_ganara.hide()
        self.lbl_puntos_nuevos.hide()
        
        self.hide()
    
    def _get_nivel_info(self, nivel: str) -> dict:
        """Obtiene el emoji y color para cada nivel"""
        niveles = {
            "BRONCE": {"emoji": "🥉", "color": "#CD7F32"},
            "PLATA": {"emoji": "🥈", "color": "#C0C0C0"},
            "ORO": {"emoji": "🥇", "color": "#FFD700"},
            "PLATINO": {"emoji": "💎", "color": "#E5E4E2"}
        }
        return niveles.get(nivel, niveles["BRONCE"])
    
    def _animate_glow(self):
        """Efecto de brillo para los puntos nuevos"""
        # Animación simple de opacidad
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        self.lbl_puntos_nuevos.setGraphicsEffect(opacity_effect)
        
        animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(1000)
        animation.setStartValue(0.3)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)
        animation.start()
    
    def to_dict(self) -> dict:
        """Serializes widget state for session storage."""
        return {
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "saldo_actual": float(self.saldo_actual) if self.saldo_actual else 0.0,
            "puntos_potenciales": float(self.puntos_potenciales) if self.puntos_potenciales else 0.0,
            "nivel": self.nivel
        }
    
    def from_dict(self, data: dict):
        """Restores widget state from dict."""
        if data and data.get("customer_id"):
            self.set_customer(
                data["customer_id"],
                data.get("customer_name", ""),
                Decimal(str(data.get("saldo_actual", 0))),
                data.get("nivel", "BRONCE")
            )
            if data.get("puntos_potenciales"):
                self.update_puntos_potenciales(Decimal(str(data["puntos_potenciales"])))

class LoyaltyHistoryDialog(QtWidgets.QDialog):
    """
    Diálogo para mostrar el historial de movimientos de puntos.
    """
    
    def __init__(self, customer_id: int, customer_name: str, loyalty_engine, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.loyalty_engine = loyalty_engine
        
        self.setWindowTitle(f"Historial de Puntos - {customer_name}")
        self.setMinimumSize(800, 600)
        
        self._build_ui()
        self._load_history()
    
    def _build_ui(self):
        """Construye la interfaz del diálogo"""
        layout = QtWidgets.QVBoxLayout()
        
        # Header con saldo actual
        header = QtWidgets.QFrame()
        header.setStyleSheet("""
            background-color: #FFD700;
            border-radius: 10px;
            padding: 15px;
        """)
        header_layout = QtWidgets.QHBoxLayout()
        
        lbl_header = QtWidgets.QLabel(f"💰 Historial de {self.customer_name}")
        lbl_header.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header_layout.addWidget(lbl_header)
        
        self.lbl_saldo_header = QtWidgets.QLabel("Saldo: $0.00")
        self.lbl_saldo_header.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        header_layout.addWidget(self.lbl_saldo_header)
        
        header.setLayout(header_layout)
        layout.addWidget(header)
        
        # Tabla de transacciones
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Tipo", "Monto", "Saldo Después", "Descripción", "Regla"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.table)
        
        # Botón de cerrar
        btn_close = QtWidgets.QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        self.setLayout(layout)
    
    def _load_history(self):
        """Carga el historial de transacciones"""
        try:
            # Obtener saldo actual
            saldo = self.loyalty_engine.get_balance(self.customer_id)
            self.lbl_saldo_header.setText(f"Saldo: ${saldo:.2f}")
            
            # Obtener historial
            transactions = self.loyalty_engine.get_transaction_history(self.customer_id, limit=100)
            
            self.table.setRowCount(len(transactions))
            
            for row, tx in enumerate(transactions):
                # Fecha
                fecha = tx['fecha_hora']
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(fecha))
                
                # Tipo
                tipo = tx['tipo']
                tipo_item = QtWidgets.QTableWidgetItem(tipo)
                if tipo == 'EARN':
                    tipo_item.setForeground(QtGui.QColor("#00C851"))
                elif tipo == 'REDEEM':
                    tipo_item.setForeground(QtGui.QColor("#FF4444"))
                self.table.setItem(row, 1, tipo_item)
                
                # Monto
                monto = float(tx['monto'])
                monto_str = f"${abs(monto):.2f}"
                if monto > 0:
                    monto_str = "+" + monto_str
                monto_item = QtWidgets.QTableWidgetItem(monto_str)
                monto_item.setForeground(QtGui.QColor("#00C851" if monto > 0 else "#FF4444"))
                self.table.setItem(row, 2, monto_item)
                
                # Saldo después
                saldo_nuevo = float(tx['saldo_nuevo'])
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"${saldo_nuevo:.2f}"))
                
                # Descripción
                descripcion = tx.get('descripcion', '')
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(descripcion))
                
                # Regla
                regla = tx.get('regla_aplicada', '')
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(regla))
            
            # Ajustar columnas
            self.table.resizeColumnsToContents()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudo cargar el historial: {e}"
            )

    def showEvent(self, event):
        """Apply theme colors when dialog is shown."""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            for btn in self.findChildren(QtWidgets.QPushButton):
                text = btn.text().lower()
                if any(w in text for w in ['guardar', 'save', 'aceptar', 'ok', 'crear', 'agregar']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(w in text for w in ['cancelar', 'cancel', 'cerrar', 'eliminar', 'delete']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception:
            pass
