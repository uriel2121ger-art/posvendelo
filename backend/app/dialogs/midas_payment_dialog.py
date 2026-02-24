"""
MIDAS PAYMENT DIALOG - Enhanced Payment with Loyalty Points
Diálogo de pago mejorado que soporta:
- Efectivo
- Tarjeta
- Puntos de Lealtad
- Pagos Mixtos (Efectivo + Puntos, Tarjeta + Puntos)
"""

from typing import Dict, List, Optional
from decimal import ROUND_HALF_UP, Decimal
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("MIDAS_PAYMENT")

class MidasPaymentDialog(QtWidgets.QDialog):
    """
    Diálogo de pago con soporte completo para el Monedero Electrónico MIDAS.
    
    Permite:
    - Pago 100% efectivo/tarjeta
    - Pago 100% puntos
    - Pago mixto (ej: $300 efectivo + $200 puntos)
    """
    
    def __init__(
        self, 
        total_amount: Decimal, 
        customer_id: Optional[int] = None,
        customer_name: str = "",
        loyalty_engine = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.total_amount = total_amount
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.loyalty_engine = loyalty_engine
        
        # Saldo de puntos disponible
        self.saldo_puntos = Decimal('0.00')
        if customer_id and loyalty_engine:
            self.saldo_puntos = loyalty_engine.get_balance(customer_id)
        
        # Montos de pago
        self.monto_efectivo = Decimal('0.00')
        self.monto_tarjeta = Decimal('0.00')
        self.monto_puntos = Decimal('0.00')
        
        # Resultado del pago
        self.payment_method = "cash"  # cash, card, points, mixed
        self.payment_breakdown = {}  # Desglose detallado
        self.amount_paid = Decimal('0.00')
        self.change = Decimal('0.00')
        
        self.setWindowTitle("💳 Cobrar - MIDAS Payment")
        self.setMinimumWidth(500)
        
        self._build_ui()
        self._update_totales()
    
    def _build_ui(self):
        """Construye la interfaz del diálogo de pago"""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(15)
        
        # ====================================================================
        # HEADER: Total a pagar
        # ====================================================================
        header = QtWidgets.QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #00C851;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        header_layout = QtWidgets.QVBoxLayout()
        
        lbl_total_text = QtWidgets.QLabel("Total a Pagar:")
        lbl_total_text.setStyleSheet("color: white; font-size: 16px;")
        lbl_total_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(lbl_total_text)
        
        self.lbl_total = QtWidgets.QLabel(f"${self.total_amount:.2f}")
        self.lbl_total.setStyleSheet("color: white; font-size: 36px; font-weight: bold;")
        self.lbl_total.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.lbl_total)
        
        header.setLayout(header_layout)
        layout.addWidget(header)
        
        # ====================================================================
        # MONEDERO ELECTRÓNICO (si hay cliente)
        # ====================================================================
        if self.customer_id and self.loyalty_engine:
            wallet_frame = QtWidgets.QFrame()
            wallet_frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                               stop:0 #FFF9E6, stop:1 #FFE6B3);
                    border: 2px solid #FFD700;
                    border-radius: 10px;
                    padding: 10px;
                }
            """)
            wallet_layout = QtWidgets.QVBoxLayout()
            
            lbl_wallet_title = QtWidgets.QLabel(f"💰 Monedero de {self.customer_name}")
            lbl_wallet_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #FF8C00;")
            lbl_wallet_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            wallet_layout.addWidget(lbl_wallet_title)
            
            self.lbl_saldo_disponible = QtWidgets.QLabel(f"Saldo disponible: ${self.saldo_puntos:.2f}")
            self.lbl_saldo_disponible.setStyleSheet("font-size: 18px; font-weight: bold; color: #00C851;")
            self.lbl_saldo_disponible.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            wallet_layout.addWidget(self.lbl_saldo_disponible)
            
            wallet_frame.setLayout(wallet_layout)
            layout.addWidget(wallet_frame)
        
        # ====================================================================
        # MÉTODOS DE PAGO
        # ====================================================================
        payment_group = QtWidgets.QGroupBox("Métodos de Pago")
        payment_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        payment_layout = QtWidgets.QVBoxLayout()
        
        # --- EFECTIVO ---
        efectivo_layout = QtWidgets.QHBoxLayout()
        efectivo_layout.addWidget(QtWidgets.QLabel("💵 Efectivo:"))
        
        self.input_efectivo = QtWidgets.QLineEdit()
        self.input_efectivo.setPlaceholderText("0.00")
        self.input_efectivo.textChanged.connect(self._on_efectivo_changed)
        efectivo_layout.addWidget(self.input_efectivo)
        
        btn_efectivo_total = QtWidgets.QPushButton("Total")
        btn_efectivo_total.clicked.connect(lambda: self._pago_rapido("efectivo"))
        efectivo_layout.addWidget(btn_efectivo_total)
        
        payment_layout.addLayout(efectivo_layout)
        
        # --- TARJETA ---
        tarjeta_layout = QtWidgets.QHBoxLayout()
        tarjeta_layout.addWidget(QtWidgets.QLabel("💳 Tarjeta:"))
        
        self.input_tarjeta = QtWidgets.QLineEdit()
        self.input_tarjeta.setPlaceholderText("0.00")
        self.input_tarjeta.textChanged.connect(self._on_tarjeta_changed)
        tarjeta_layout.addWidget(self.input_tarjeta)
        
        btn_tarjeta_total = QtWidgets.QPushButton("Total")
        btn_tarjeta_total.clicked.connect(lambda: self._pago_rapido("tarjeta"))
        tarjeta_layout.addWidget(btn_tarjeta_total)
        
        payment_layout.addLayout(tarjeta_layout)
        
        # --- PUNTOS (solo si hay cliente con saldo) ---
        if self.customer_id and self.saldo_puntos > 0:
            puntos_layout = QtWidgets.QHBoxLayout()
            puntos_layout.addWidget(QtWidgets.QLabel("🎁 Puntos:"))
            
            self.input_puntos = QtWidgets.QLineEdit()
            self.input_puntos.setPlaceholderText("0.00")
            self.input_puntos.textChanged.connect(self._on_puntos_changed)
            puntos_layout.addWidget(self.input_puntos)
            
            btn_puntos_total = QtWidgets.QPushButton("Todo")
            btn_puntos_total.clicked.connect(lambda: self._pago_rapido("puntos"))
            puntos_layout.addWidget(btn_puntos_total)
            
            btn_puntos_disponible = QtWidgets.QPushButton("Disponible")
            btn_puntos_disponible.clicked.connect(self._usar_todo_disponible)
            puntos_layout.addWidget(btn_puntos_disponible)
            
            payment_layout.addLayout(puntos_layout)
        
        payment_group.setLayout(payment_layout)
        layout.addWidget(payment_group)
        
        # ====================================================================
        # RESUMEN DE PAGO
        # ====================================================================
        resumen_frame = QtWidgets.QFrame()
        resumen_frame.setStyleSheet("""
            QFrame {
                background-color: #F5F5F5;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        resumen_layout = QtWidgets.QVBoxLayout()
        
        self.lbl_total_pagado = QtWidgets.QLabel("Total Recibido: $0.00")
        self.lbl_total_pagado.setStyleSheet("font-size: 14px; font-weight: bold;")
        resumen_layout.addWidget(self.lbl_total_pagado)
        
        self.lbl_faltante = QtWidgets.QLabel("Faltante: $0.00")
        self.lbl_faltante.setStyleSheet("font-size: 14px; color: #FF4444; font-weight: bold;")
        resumen_layout.addWidget(self.lbl_faltante)
        
        self.lbl_cambio = QtWidgets.QLabel("Cambio: $0.00")
        self.lbl_cambio.setStyleSheet("font-size: 16px; color: #2196F3; font-weight: bold;")
        resumen_layout.addWidget(self.lbl_cambio)
        
        resumen_frame.setLayout(resumen_layout)
        layout.addWidget(resumen_frame)
        
        # ====================================================================
        # BOTONES DE ACCIÓN
        # ====================================================================
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_cobrar = QtWidgets.QPushButton("✅ COBRAR (Enter)")
        self.btn_cobrar.setStyleSheet("""
            QPushButton {
                background-color: #00C851;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
            }
            QPushButton:hover:!disabled {
                background-color: #00E65B;
            }
        """)
        self.btn_cobrar.clicked.connect(self._validar_y_cobrar)
        self.btn_cobrar.setEnabled(False)
        btn_layout.addWidget(self.btn_cobrar)
        
        btn_cancelar = QtWidgets.QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self, self._validar_y_cobrar)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self, self.reject)
    
    # ========================================================================
    # LÓGICA DE CÁLCULO
    # ========================================================================
    
    def _on_efectivo_changed(self):
        """Callback cuando cambia el monto de efectivo"""
        try:
            texto = self.input_efectivo.text().strip()
            self.monto_efectivo = Decimal(texto) if texto else Decimal('0.00')
        except Exception:
            self.monto_efectivo = Decimal('0.00')
        self._update_totales()
    
    def _on_tarjeta_changed(self):
        """Callback cuando cambia el monto de tarjeta"""
        try:
            texto = self.input_tarjeta.text().strip()
            self.monto_tarjeta = Decimal(texto) if texto else Decimal('0.00')
        except Exception:
            self.monto_tarjeta = Decimal('0.00')
        self._update_totales()
    
    def _on_puntos_changed(self):
        """Callback cuando cambia el monto de puntos"""
        try:
            texto = self.input_puntos.text().strip()
            monto = Decimal(texto) if texto else Decimal('0.00')
            
            # Validar que no exceda el saldo disponible
            if monto > self.saldo_puntos:
                self.monto_puntos = self.saldo_puntos
                self.input_puntos.setText(str(self.saldo_puntos))
            else:
                self.monto_puntos = monto
        except Exception:
            self.monto_puntos = Decimal('0.00')
        self._update_totales()
    
    def _update_totales(self):
        """Actualiza los totales y valida el pago"""
        # Calcular total recibido
        total_recibido = self.monto_efectivo + self.monto_tarjeta + self.monto_puntos
        
        # Calcular faltante o cambio
        diferencia = total_recibido - self.total_amount
        
        # Actualizar labels
        self.lbl_total_pagado.setText(f"Total Recibido: ${total_recibido:.2f}")
        
        if diferencia < 0:
            # Falta dinero
            self.lbl_faltante.setText(f"Faltante: ${abs(diferencia):.2f}")
            self.lbl_faltante.show()
            self.lbl_cambio.setText("Cambio: $0.00")
            self.lbl_cambio.setStyleSheet("font-size: 16px; color: #2196F3; font-weight: bold;")
            self.btn_cobrar.setEnabled(False)
        else:
            # Pago completo
            self.lbl_faltante.hide()
            
            # Calcular cambio (solo del efectivo, no de puntos ni tarjeta)
            if self.monto_efectivo > 0:
                # El cambio solo se da del efectivo
                # Si pagó $100 efectivo + $50 puntos para un total de $120,
                # el cambio es $100 - ($120 - $50) = $30
                monto_a_cubrir_efectivo = self.total_amount - (self.monto_tarjeta + self.monto_puntos)
                cambio_efectivo = max(Decimal('0.00'), self.monto_efectivo - monto_a_cubrir_efectivo)
                self.change = cambio_efectivo
            else:
                self.change = Decimal('0.00')
            
            self.lbl_cambio.setText(f"Cambio: ${self.change:.2f}")
            
            if self.change > 0:
                self.lbl_cambio.setStyleSheet("font-size: 16px; color: #FF9800; font-weight: bold;")
            else:
                self.lbl_cambio.setStyleSheet("font-size: 16px; color: #00C851; font-weight: bold;")
            
            self.btn_cobrar.setEnabled(True)
    
    def _pago_rapido(self, metodo: str):
        """
        Botones de pago rápido: completa el total con un solo método.
        
        Args:
            metodo: 'efectivo', 'tarjeta', o 'puntos'
        """
        # Limpiar otros métodos
        self.input_efectivo.setText("")
        self.input_tarjeta.setText("")
        if hasattr(self, 'input_puntos'):
            self.input_puntos.setText("")
        
        # Establecer el total en el método seleccionado
        if metodo == "efectivo":
            self.input_efectivo.setText(str(self.total_amount))
        elif metodo == "tarjeta":
            self.input_tarjeta.setText(str(self.total_amount))
        elif metodo == "puntos":
            # Usar puntos hasta donde alcance
            monto_puntos = min(self.total_amount, self.saldo_puntos)
            self.input_puntos.setText(str(monto_puntos))
    
    def _usar_todo_disponible(self):
        """Usa todos los puntos disponibles"""
        if hasattr(self, 'input_puntos'):
            monto_a_usar = min(self.total_amount, self.saldo_puntos)
            self.input_puntos.setText(str(monto_a_usar))
    
    def _validar_y_cobrar(self):
        """Valida el pago y cierra el diálogo"""
        total_recibido = self.monto_efectivo + self.monto_tarjeta + self.monto_puntos
        
        if total_recibido < self.total_amount:
            QtWidgets.QMessageBox.warning(
                self,
                "Pago Incompleto",
                f"El total recibido (${total_recibido:.2f}) es menor al total a pagar (${self.total_amount:.2f})"
            )
            return
        
        # Validar saldo de puntos
        if self.monto_puntos > self.saldo_puntos:
            QtWidgets.QMessageBox.critical(
                self,
                "Saldo Insuficiente",
                f"No hay suficientes puntos. Disponible: ${self.saldo_puntos:.2f}, Solicitado: ${self.monto_puntos:.2f}"
            )
            return
        
        # Determinar método de pago principal
        if self.monto_puntos > 0 and self.monto_efectivo == 0 and self.monto_tarjeta == 0:
            self.payment_method = "points"
        elif self.monto_efectivo > 0 and self.monto_tarjeta == 0 and self.monto_puntos == 0:
            self.payment_method = "cash"
        elif self.monto_tarjeta > 0 and self.monto_efectivo == 0 and self.monto_puntos == 0:
            self.payment_method = "card"
        else:
            self.payment_method = "mixed"
        
        # Preparar desglose
        self.payment_breakdown = {
            "efectivo": float(self.monto_efectivo),
            "tarjeta": float(self.monto_tarjeta),
            "puntos": float(self.monto_puntos),
            "cambio": float(self.change)
        }
        
        self.amount_paid = total_recibido
        
        logger.info(f"💳 Pago procesado: {self.payment_method} - Total: ${self.amount_paid:.2f} - Desglose: {self.payment_breakdown}")
        
        self.accept()
    
    def get_payment_info(self) -> Dict:
        """
        Obtiene la información del pago para registrar en la venta.
        
        Returns:
            Diccionario con toda la información del pago
        """
        return {
            "total_amount": float(self.total_amount),
            "payment_method": self.payment_method,
            "amount_paid": float(self.amount_paid),
            "change": float(self.change),
            "breakdown": self.payment_breakdown,
            "customer_id": self.customer_id
        }

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
