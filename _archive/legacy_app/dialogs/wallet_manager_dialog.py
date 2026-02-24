"""
Diálogo de Administración de Monederos Anónimos
Permite consultar, ver historial y ajustar saldos de monederos.
"""

from PyQt6 import QtCore, QtGui, QtWidgets

from app.services.anonymous_loyalty import AnonymousLoyalty
from app.utils.theme_manager import theme_manager


class WalletManagerDialog(QtWidgets.QDialog):
    """Administrador de monederos anónimos."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.loyalty = AnonymousLoyalty(core)
        
        self.setWindowTitle("💰 Administrar Monederos")
        self.setMinimumSize(800, 500)
        self._build_ui()
        self._load_wallets()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Barra de búsqueda
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel("🔍 Buscar:"))
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Teléfono o nickname...")
        self.search_input.textChanged.connect(self._filter_wallets)
        search_layout.addWidget(self.search_input)
        
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh.clicked.connect(self._load_wallets)
        search_layout.addWidget(btn_refresh)
        
        layout.addLayout(search_layout)
        
        # Tabla de monederos
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Teléfono", "Nickname", "Puntos", "Valor $", "Visitas", "Creado"
        ])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._show_wallet_details)
        layout.addWidget(self.table)
        
        # Estadísticas
        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(self.stats_label)
        
        # Botones de acción
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_details = QtWidgets.QPushButton("📋 Ver Detalles")
        btn_details.clicked.connect(self._show_wallet_details)
        btn_layout.addWidget(btn_details)
        
        btn_adjust = QtWidgets.QPushButton("➕ Ajustar Puntos")
        btn_adjust.clicked.connect(self._adjust_points)
        btn_layout.addWidget(btn_adjust)
        
        btn_history = QtWidgets.QPushButton("📜 Historial")
        btn_history.clicked.connect(self._show_history)
        btn_layout.addWidget(btn_history)
        
        btn_layout.addStretch()
        
        # Exportar/Importar
        btn_export = QtWidgets.QPushButton("📤 Exportar")
        btn_export.clicked.connect(self._export_wallets)
        btn_export.setStyleSheet("background: #27ae60; color: white;")
        btn_layout.addWidget(btn_export)
        
        btn_import = QtWidgets.QPushButton("📥 Importar")
        btn_import.clicked.connect(self._import_wallets)
        btn_import.setStyleSheet("background: #3498db; color: white;")
        btn_layout.addWidget(btn_import)
        
        btn_close = QtWidgets.QPushButton("Cerrar")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def _load_wallets(self):
        """Carga todos los monederos."""
        try:
            wallets = list(self.core.db.execute_query("""
                SELECT wallet_id, phone, nickname, points_balance, 
                       total_earned, total_redeemed, visit_count, created_at
                FROM anonymous_wallet
                ORDER BY created_at DESC
            """))
            
            self.all_wallets = [dict(w) for w in wallets]
            self._populate_table(self.all_wallets)
            
            # Estadísticas
            total_pts = sum(w.get('points_balance', 0) for w in self.all_wallets)
            total_value = total_pts * self.loyalty.PESO_PER_POINT
            self.stats_label.setText(
                f"Total: {len(self.all_wallets)} monederos | "
                f"{total_pts:,} puntos | ${total_value:,.2f} en saldo"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
    
    def _populate_table(self, wallets):
        """Puebla la tabla con los monederos."""
        self.table.setRowCount(len(wallets))
        
        for i, w in enumerate(wallets):
            pts = w.get('points_balance', 0)
            value = pts * self.loyalty.PESO_PER_POINT
            
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(w.get('phone', ''))))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(w.get('nickname', '-'))))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{pts:,}"))
            self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"${value:.2f}"))
            self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(w.get('visit_count', 0))))
            
            created = str(w.get('created_at', ''))[:10]
            self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(created))
        
        self.table.resizeColumnsToContents()
    
    def _filter_wallets(self, text):
        """Filtra monederos por texto."""
        if not text:
            self._populate_table(self.all_wallets)
            return
        
        text = text.lower()
        filtered = [
            w for w in self.all_wallets
            if text in str(w.get('phone', '')).lower()
            or text in str(w.get('nickname', '')).lower()
        ]
        self._populate_table(filtered)
    
    def _get_selected_wallet(self):
        """Obtiene el monedero seleccionado."""
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selección", "Seleccione un monedero")
            return None
        
        phone = self.table.item(row, 0).text()
        return self.loyalty.find_wallet(phone)
    
    def _show_wallet_details(self):
        """Muestra detalles del monedero."""
        wallet = self._get_selected_wallet()
        if not wallet:
            return
        
        status = self.loyalty.get_wallet_status(wallet['phone'])
        
        msg = f"""
💰 MONEDERO: {wallet['phone']}

👤 Nickname: {wallet.get('nickname', '-')}
💎 Puntos: {wallet['points_balance']:,}
💵 Valor: ${status.get('redeem_value', 0):.2f}

📊 Estadísticas:
• Total ganado: {wallet.get('total_earned', 0):,} pts
• Total canjeado: {wallet.get('total_redeemed', 0):,} pts
• Visitas: {wallet.get('visit_count', 0)}

📅 Creado: {str(wallet.get('created_at', ''))[:10]}
        """
        
        QtWidgets.QMessageBox.information(self, "Detalles", msg)
    
    def _adjust_points(self):
        """Ajusta puntos del monedero."""
        wallet = self._get_selected_wallet()
        if not wallet:
            return
        
        current = wallet['points_balance']
        
        amount, ok = QtWidgets.QInputDialog.getInt(
            self,
            "Ajustar Puntos",
            f"Saldo actual: {current} pts\n\n"
            "Ingrese cantidad a añadir (positivo)\n"
            "o quitar (negativo):",
            0, -current, 999999
        )
        
        if not ok or amount == 0:
            return
        
        reason, ok = QtWidgets.QInputDialog.getText(
            self,
            "Motivo",
            "Ingrese el motivo del ajuste:"
        )
        
        if not ok:
            return
        
        try:
            if amount > 0:
                # Añadir puntos
                self.loyalty.earn_points(wallet['wallet_id'], amount, None)
            else:
                # Quitar puntos
                self.loyalty.redeem_points(wallet['wallet_id'], abs(amount))
            
            QtWidgets.QMessageBox.information(
                self, "✅ Ajustado",
                f"Se ajustaron {amount:+d} puntos.\n"
                f"Nuevo saldo: {current + amount} pts"
            )
            self._load_wallets()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
    
    def _show_history(self):
        """Muestra historial de transacciones."""
        wallet = self._get_selected_wallet()
        if not wallet:
            return
        
        try:
            transactions = list(self.core.db.execute_query("""
                SELECT type, points, description, created_at
                FROM wallet_transactions
                WHERE wallet_id = %s
                ORDER BY created_at DESC
                LIMIT 20
            """, (wallet['wallet_id'],)))
            
            if not transactions:
                QtWidgets.QMessageBox.information(
                    self, "Historial",
                    f"No hay transacciones para {wallet['phone']}"
                )
                return
            
            msg = f"📜 Últimas transacciones de {wallet['phone']}:\n\n"
            for t in transactions:
                pts = t['points']
                sign = "+" if pts > 0 else ""
                date = str(t['created_at'])[:16]
                msg += f"{date} | {sign}{pts} pts | {t['description']}\n"
            
            QtWidgets.QMessageBox.information(self, "Historial", msg)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", str(e))
    
    def _export_wallets(self):
        """Exporta monederos y su historial a JSON."""
        from datetime import datetime
        import json
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar Monederos", 
            f"monederos_anonimos_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON (*.json)"
        )
        
        if not path:
            return
        
        try:
            # Obtener monederos
            wallets = list(self.core.db.execute_query("""
                SELECT * FROM anonymous_wallet
            """))
            
            # Obtener transacciones
            transactions = list(self.core.db.execute_query("""
                SELECT * FROM wallet_transactions
            """))
            
            data = {
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "wallets": [dict(w) for w in wallets],
                "transactions": [dict(t) for t in transactions]
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            
            QtWidgets.QMessageBox.information(
                self, "✅ Exportado",
                f"Se exportaron {len(wallets)} monederos\n"
                f"y {len(transactions)} transacciones\n\n"
                f"Archivo: {path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
    
    def _import_wallets(self):
        """Importa monederos desde JSON."""
        import json
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Importar Monederos", "",
            "JSON (*.json)"
        )
        
        if not path:
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            wallets = data.get('wallets', [])
            transactions = data.get('transactions', [])
            
            if not wallets:
                QtWidgets.QMessageBox.warning(self, "Vacío", "No hay monederos en el archivo")
                return
            
            reply = QtWidgets.QMessageBox.question(
                self, "Confirmar Importación",
                f"Se importarán:\n"
                f"• {len(wallets)} monederos\n"
                f"• {len(transactions)} transacciones\n\n"
                f"¿Desea continuar?\n"
                f"(Los duplicados serán ignorados)",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            
            imported = 0
            for w in wallets:
                try:
                    self.core.db.execute_write("""
                        INSERT INTO anonymous_wallet
                        (wallet_id, phone, nickname, points_balance, total_earned,
                         total_redeemed, visit_count, created_at, synced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
                        ON CONFLICT (wallet_id) DO NOTHING
                    """, (
                        w.get('wallet_id'), w.get('phone'), w.get('nickname'),
                        w.get('points_balance', 0), w.get('total_earned', 0),
                        w.get('total_redeemed', 0), w.get('visit_count', 0),
                        w.get('created_at')
                    ))
                    imported += 1
                except Exception:
                    pass
            
            trans_imported = 0
            for t in transactions:
                try:
                    self.core.db.execute_write("""
                        INSERT INTO wallet_transactions
                        (id, wallet_id, type, points, description, sale_id, created_at, synced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                        ON CONFLICT (id) DO NOTHING
                    """, (
                        t.get('id'), t.get('wallet_id'), t.get('type'),
                        t.get('points'), t.get('description'),
                        t.get('sale_id'), t.get('created_at')
                    ))
                    trans_imported += 1
                except Exception:
                    pass
            
            QtWidgets.QMessageBox.information(
                self, "✅ Importado",
                f"Se importaron:\n"
                f"• {imported} monederos\n"
                f"• {trans_imported} transacciones"
            )
            self._load_wallets()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
