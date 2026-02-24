"""
Diálogo de Lealtad Anónima - Para agregar puntos a monedero sin registro fiscal
"""

from PyQt6 import QtCore, QtGui, QtWidgets

from app.services.anonymous_loyalty import AnonymousLoyalty
from app.utils.theme_manager import theme_manager


class AnonymousLoyaltyDialog(QtWidgets.QDialog):
    """Diálogo para gestionar monedero anónimo después de venta Serie B."""
    
    def __init__(self, core, sale_total: float, sale_id: int = None, parent=None):
        super().__init__(parent)
        self.core = core
        self.sale_total = sale_total
        self.sale_id = sale_id
        self.loyalty = AnonymousLoyalty(core)
        self.result_data = None
        
        self.setWindowTitle("🎁 Monedero de Puntos")
        self.setMinimumWidth(450)
        self._build_ui()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Tema
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        self.setStyleSheet(f"""
            QDialog {{
                background: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QLineEdit {{
                padding: 10px;
                border: 1px solid {c['border']};
                border-radius: 5px;
                font-size: 16px;
                background: {c['input_bg']};
                color: {c['text_primary']};
            }}
            QPushButton {{
                padding: 12px 20px;
                border-radius: 5px;
                font-weight: bold;
            }}
        """)
        
        # Header
        header = QtWidgets.QLabel("🎁 Acumula puntos por tu compra")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        
        # Info de compra - usar mismo cálculo que earn_points (% de cashback)
        # Obtener % de cashback de la regla MIDAS
        cashback_percent = 1.0  # Default 1%
        try:
            rules = list(self.core.db.execute_query("""
                SELECT multiplicador FROM loyalty_rules 
                WHERE activo = 1 AND condicion_tipo = 'GLOBAL'
                ORDER BY prioridad DESC LIMIT 1
            """))
            if rules:
                cashback_percent = float(rules[0]['multiplicador']) * 100
        except Exception:
            pass
        
        # Use round() instead of int() to avoid truncation
        points_to_earn = round(self.sale_total * (cashback_percent / 100))
        info = QtWidgets.QLabel(
            f"Compra: ${self.sale_total:.2f}\n"
            f"Puntos a ganar: {points_to_earn} pts ({cashback_percent}%)\n"
            f"Valor: ${points_to_earn * self.loyalty.PESO_PER_POINT:.2f}"
        )
        info.setStyleSheet(f"background: {c['bg_card']}; padding: 15px; border-radius: 8px;")
        layout.addWidget(info)
        
        # Input teléfono/ID
        layout.addWidget(QtWidgets.QLabel("Teléfono o ID de monedero:"))
        self.phone_input = QtWidgets.QLineEdit()
        self.phone_input.setPlaceholderText("Ej: 5551234567 o ABCD1234")
        self.phone_input.textChanged.connect(self._on_phone_change)
        layout.addWidget(self.phone_input)
        
        # Status del monedero
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Opción de crear nuevo
        self.create_new_check = QtWidgets.QCheckBox("Crear nuevo monedero si no existe")
        self.create_new_check.setChecked(True)
        layout.addWidget(self.create_new_check)
        
        # Apodo (opcional)
        self.nickname_layout = QtWidgets.QHBoxLayout()
        self.nickname_layout.addWidget(QtWidgets.QLabel("Apodo (opcional):"))
        self.nickname_input = QtWidgets.QLineEdit()
        self.nickname_input.setPlaceholderText("Ej: Juan del Mercado")
        self.nickname_layout.addWidget(self.nickname_input)
        layout.addLayout(self.nickname_layout)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        skip_btn = QtWidgets.QPushButton("Omitir")
        skip_btn.clicked.connect(self.reject)
        skip_btn.setStyleSheet(f"background: {c['bg_secondary']}; color: {c['text_secondary']};")
        btn_layout.addWidget(skip_btn)
        
        self.add_btn = QtWidgets.QPushButton(f"🎁 Agregar {points_to_earn} puntos")
        self.add_btn.clicked.connect(self._add_points)
        self.add_btn.setStyleSheet(f"background: {c['btn_success']}; color: white;")
        btn_layout.addWidget(self.add_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_phone_change(self, text: str):
        """Busca el monedero cuando cambia el teléfono."""
        if len(text) < 5:
            self.status_label.setText("")
            return
        
        wallet = self.loyalty.find_wallet(text)
        if wallet:
            self.status_label.setText(
                f"✅ Monedero encontrado\n"
                f"👤 {wallet.get('nickname', 'Cliente')}\n"
                f"💰 Saldo: {wallet['points_balance']} pts = ${wallet['points_balance'] * self.loyalty.PESO_PER_POINT:.2f}\n"
                f"🛒 Visitas: {wallet['visit_count']}"
            )
            self.status_label.setStyleSheet("color: #27ae60; padding: 10px; background: rgba(39, 174, 96, 0.1); border-radius: 5px;")
            self.create_new_check.setVisible(False)
            self.nickname_input.setVisible(False)
        else:
            self.status_label.setText("🆕 Cliente nuevo - Se creará monedero")
            self.status_label.setStyleSheet("color: #f39c12; padding: 10px;")
            self.create_new_check.setVisible(True)
            self.nickname_input.setVisible(True)
    
    def _add_points(self):
        """Agrega puntos al monedero."""
        phone = self.phone_input.text().strip()
        
        if not phone:
            QtWidgets.QMessageBox.warning(self, "Error", "Ingresa un teléfono o ID")
            return
        
        # Buscar o crear
        wallet = self.loyalty.find_wallet(phone)
        
        if not wallet:
            if not self.create_new_check.isChecked():
                QtWidgets.QMessageBox.warning(self, "Error", "Monedero no encontrado")
                return
            
            # Crear nuevo
            result = self.loyalty.create_wallet(
                phone=phone if phone.isdigit() else None,
                nickname=self.nickname_input.text() or None
            )
            wallet_id = result['wallet_id']
            QtWidgets.QMessageBox.information(
                self, "Nuevo Monedero",
                f"✅ Monedero creado: {wallet_id[:8]}...\n\n"
                f"El cliente puede usar su teléfono para identificarse en futuras compras."
            )
        else:
            wallet_id = wallet['wallet_id']
        
        # Acumular puntos (Serie B)
        result = self.loyalty.earn_points(
            wallet_id=wallet_id,
            sale_total=self.sale_total,
            sale_id=self.sale_id,
            serie='B'
        )
        
        if result.get('success'):
            self.result_data = result
            QtWidgets.QMessageBox.information(
                self, "🎉 Puntos Agregados",
                f"✅ +{result['points_earned']} puntos!\n\n"
                f"Nuevo saldo: {result['new_balance']} pts\n"
                f"Valor: ${result['redeem_value']:.2f}"
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", result.get('reason', 'Error desconocido'))

class RedeemPointsDialog(QtWidgets.QDialog):
    """Diálogo para canjear puntos del monedero anónimo."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.loyalty = AnonymousLoyalty(core)
        self.discount_value = 0.0
        
        self.setWindowTitle("💰 Canjear Puntos")
        self.setMinimumWidth(400)
        self._build_ui()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Apply theme
        from app.utils.theme_manager import theme_manager
        c = theme_manager.get_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QLabel {{
                color: {c['text_primary']};
                background: transparent;
            }}
            QLineEdit {{
                background: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                padding: 10px;
                border-radius: 5px;
            }}
            QSpinBox {{
                background: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                padding: 8px;
            }}
            QPushButton {{
                background: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                padding: 10px 20px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
        """)
        
        # Input
        layout.addWidget(QtWidgets.QLabel("Teléfono o ID de monedero:"))
        self.phone_input = QtWidgets.QLineEdit()
        self.phone_input.setPlaceholderText("Ej: 5551234567")
        self.phone_input.returnPressed.connect(self._search_wallet)
        layout.addWidget(self.phone_input)
        
        # Buscar
        search_btn = QtWidgets.QPushButton("🔍 Buscar")
        search_btn.clicked.connect(self._search_wallet)
        layout.addWidget(search_btn)
        
        # Info del monedero
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # Puntos a canjear
        points_layout = QtWidgets.QHBoxLayout()
        points_layout.addWidget(QtWidgets.QLabel("Puntos a canjear:"))
        self.points_input = QtWidgets.QSpinBox()
        self.points_input.setRange(0, 999999)
        self.points_input.valueChanged.connect(self._update_value)
        points_layout.addWidget(self.points_input)
        layout.addLayout(points_layout)
        
        # Valor
        self.value_label = QtWidgets.QLabel("Descuento: $0.00")
        self.value_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60;")
        layout.addWidget(self.value_label)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.redeem_btn = QtWidgets.QPushButton("💰 Canjear")
        self.redeem_btn.clicked.connect(self._redeem)
        self.redeem_btn.setEnabled(False)
        btn_layout.addWidget(self.redeem_btn)
        layout.addLayout(btn_layout)
        
        self.current_wallet = None
        self.source_type = None  # 'midas' or 'anonymous'
        self.midas_customer_id = None
    
    def _search_wallet(self):
        phone = self.phone_input.text().strip()
        if not phone:
            return
        
        self.source_type = None
        self.midas_customer_id = None
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 1: Buscar en MIDAS (clientes registrados) - PRIORIDAD
        # ═══════════════════════════════════════════════════════════════════
        midas_result = self._search_midas(phone)
        
        if midas_result:
            self.source_type = 'midas'
            self.midas_customer_id = midas_result['customer_id']
            balance = int(midas_result['balance'])
            
            self.info_label.setText(
                f"🌟 CLIENTE REGISTRADO (MIDAS)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {midas_result['name']}\n"
                f"💰 Saldo: {balance} pts = ${balance:.2f}\n"
                f"🏅 Nivel: {midas_result['tier']}"
            )
            self.info_label.setStyleSheet("color: #f39c12; font-weight: bold;")
            
            self.points_input.setMaximum(balance)
            self.points_input.setValue(min(balance, int(self.core.loyalty_engine.get_balance(midas_result['customer_id']))))
            self.redeem_btn.setEnabled(balance >= 100)
            self.redeem_btn.setText("💰 Usar Puntos MIDAS")
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 2: Buscar en Monedero Anónimo
        # ═══════════════════════════════════════════════════════════════════
        status = self.loyalty.get_wallet_status(phone)
        
        if status.get('found'):
            self.source_type = 'anonymous'
            self.current_wallet = self.loyalty.find_wallet(phone)
            balance = status['points_balance']
            
            self.info_label.setText(
                f"🎁 MONEDERO ANÓNIMO\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {status.get('nickname', 'Cliente')}\n"
                f"💰 Saldo: {balance} pts = ${status['redeem_value']:.2f}\n"
                f"📊 Visitas: {status['visit_count']}"
            )
            self.info_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            
            self.points_input.setMaximum(balance)
            self.points_input.setValue(balance)
            self.redeem_btn.setEnabled(balance >= self.loyalty.MIN_REDEEM)
            self.redeem_btn.setText("💰 Canjear Puntos")
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 3: No encontrado en ninguno - ofrecer crear anónimo
        # ═══════════════════════════════════════════════════════════════════
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "No Encontrado",
            f"No se encontró '{phone}' en:\n"
            f"• Clientes registrados (MIDAS)\n"
            f"• Monedero anónimo\n\n"
            f"¿Desea crear un monedero anónimo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.loyalty.create_wallet(phone)
            if result.get('wallet_id'):
                self.info_label.setText(
                    f"✅ Monedero anónimo creado\n"
                    f"ID: {result['wallet_id'][:8]}...\n\n"
                    f"💡 Acumula puntos en compras Sin Factura"
                )
                self.info_label.setStyleSheet("color: #27ae60;")
        else:
            self.info_label.setText(
                f"❌ No encontrado\n\n"
                f"💡 El cliente puede:\n"
                f"• Registrarse como cliente para MIDAS\n"
                f"• Crear un monedero anónimo"
            )
            self.info_label.setStyleSheet("color: #e74c3c;")
        
        self.current_wallet = None
        self.redeem_btn.setEnabled(False)
    
    def _search_midas(self, phone: str):
        """Busca cliente en MIDAS por teléfono."""
        try:
            # Buscar cliente por teléfono
            result = list(self.core.db.execute_query(
                "SELECT id, name FROM customers WHERE phone = %s AND is_active = 1 LIMIT 1",
                (phone,)
            ))
            
            if not result:
                return None
            
            customer_id = result[0]['id']
            customer_name = result[0]['name']
            
            # Buscar cuenta de lealtad
            loyalty = list(self.core.db.execute_query(
                "SELECT saldo_actual, nivel_lealtad FROM loyalty_accounts WHERE customer_id = %s",
                (customer_id,)
            ))
            
            if not loyalty:
                return None
            
            return {
                'customer_id': customer_id,
                'name': customer_name,
                'balance': float(loyalty[0]['saldo_actual'] or 0),
                'tier': loyalty[0]['nivel_lealtad'] or 'BRONCE'
            }
        except Exception as e:
            return None
    
    def _update_value(self, points: int):
        # MIDAS usa 1:1, anónimo usa PESO_PER_POINT
        if self.source_type == 'midas':
            value = float(points)  # 1 punto = $1
        else:
            value = points * self.loyalty.PESO_PER_POINT
        self.value_label.setText(f"Descuento: ${value:.2f}")
        self.discount_value = value
    
    def _redeem(self):
        points = self.points_input.value()
        
        # ═══════════════════════════════════════════════════════════════════
        # REDIMIR DE MIDAS (clientes registrados)
        # ═══════════════════════════════════════════════════════════════════
        if self.source_type == 'midas' and self.midas_customer_id:
            try:
                from decimal import Decimal
                success = self.core.loyalty_engine.redimir_puntos(
                    customer_id=self.midas_customer_id,
                    monto=Decimal(str(points)),
                    descripcion="Canje desde Monedero"
                )
                
                if success:
                    self.discount_value = float(points)  # 1:1 en MIDAS
                    new_balance = self.core.loyalty_engine.get_balance(self.midas_customer_id)
                    QtWidgets.QMessageBox.information(
                        self, "✅ Canje MIDAS Exitoso",
                        f"Usaste {points} puntos MIDAS\n"
                        f"Descuento: ${points:.2f}\n\n"
                        f"Nuevo saldo: ${float(new_balance):.2f}"
                    )
                    self.accept()
                else:
                    QtWidgets.QMessageBox.warning(self, "Error", "No se pudieron redimir los puntos MIDAS")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # REDIMIR DE MONEDERO ANÓNIMO
        # ═══════════════════════════════════════════════════════════════════
        if not self.current_wallet:
            return
        
        result = self.loyalty.redeem_points(self.current_wallet['wallet_id'], points)
        
        if result.get('success'):
            self.discount_value = result['discount_value']
            QtWidgets.QMessageBox.information(
                self, "✅ Canje Exitoso",
                f"Canjeaste {result['points_redeemed']} puntos\n"
                f"Descuento: ${result['discount_value']:.2f}\n\n"
                f"Saldo restante: {result['remaining_balance']} pts"
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", result.get('reason', 'Error'))
