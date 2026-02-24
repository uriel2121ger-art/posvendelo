from PyQt6 import QtCore, QtGui, QtWidgets

from app.utils.theme_manager import theme_manager


class ChangeDialog(QtWidgets.QDialog):
    def __init__(self, total, received, change, customer_name="Público General", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cambio")
        self.setFixedSize(400, 500)
        
        # Use theme-aware colors - Check if current theme is dark
        is_dark = theme_manager.current_theme in ["Dark", "AMOLED"]
        
        # Dynamic colors based on theme
        bg_color = "#2b2b2b" if is_dark else "#f5f5f5"
        text_color = "#e0e0e0" if is_dark else "#333"
        card_bg = "#3a3a3a" if is_dark else "white"
        border_color = "#555" if is_dark else "#ddd"
        label_color = "#aaa" if is_dark else "#666"
        success_color = "#2ecc71"
        change_color = "#e74c3c"
        
        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: {bg_color}; 
            }}
            QLabel {{ 
                color: {text_color}; 
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Icono o Título
        title = QtWidgets.QLabel("¡Venta Exitosa!")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {success_color};")
        layout.addWidget(title)
        
        # Contenedor de Info
        info_frame = QtWidgets.QFrame()
        info_frame.setStyleSheet(f"background: {card_bg}; border-radius: 10px; border: 1px solid {border_color};")
        info_layout = QtWidgets.QVBoxLayout(info_frame)
        
        def add_row(label, value, value_style="font-size: 18px; font-weight: bold;"):
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet(f"font-size: 16px; color: {label_color};")
            val = QtWidgets.QLabel(value)
            val.setStyleSheet(value_style)
            val.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            row.addWidget(lbl)
            row.addWidget(val)
            info_layout.addLayout(row)
            
        add_row("Total:", f"${total:,.2f}")
        add_row("Recibido:", f"${received:,.2f}")
        
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {border_color};")
        info_layout.addWidget(line)
        
        # Cambio Grande
        change_lbl = QtWidgets.QLabel("CAMBIO")
        change_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        change_lbl.setStyleSheet(f"font-size: 14px; color: {label_color}; margin-top: 10px;")
        info_layout.addWidget(change_lbl)
        
        change_val = QtWidgets.QLabel(f"${change:,.2f}")
        change_val.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        change_val.setStyleSheet(f"font-size: 48px; font-weight: 900; color: {change_color};")
        info_layout.addWidget(change_val)
        
        layout.addWidget(info_frame)
        
        # Cliente
        client_lbl = QtWidgets.QLabel(f"Cliente: {customer_name}")
        client_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        client_lbl.setStyleSheet(f"font-size: 14px; color: {label_color};")
        layout.addWidget(client_lbl)
        
        layout.addStretch()
        
        # Botón Cerrar
        btn_close = QtWidgets.QPushButton("Cerrar (Enter)")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        # Auto focus
        btn_close.setFocus()

