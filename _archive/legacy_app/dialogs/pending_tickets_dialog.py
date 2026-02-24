"""
Dialog for managing pending/held tickets.
Allows viewing, loading, and deleting tickets that weren't completed.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime
import json
from pathlib import Path

from PyQt6 import QtCore, QtWidgets

from app.core import DATA_DIR
from app.utils.theme_manager import theme_manager

PENDING_TICKETS_FILE = Path(DATA_DIR) / "pending_tickets.json"

class PendingTicketsDialog(QtWidgets.QDialog):
    """
    Dialog for managing pending/held sales tickets.
    
    Features:
    - List all saved pending tickets
    - Load a ticket back to sales tab
    - Delete old/unwanted tickets
    - Search/filter by customer or date
    """
    
    ticket_loaded = QtCore.pyqtSignal(dict)  # Emits ticket data when loaded
    
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.pending_tickets = {}
        self.selected_ticket_id = None
        
        self.setWindowTitle("Tickets en Espera")
        self.setModal(True)
        self.setMinimumSize(800, 500)
        
        self._build_ui()  # Build UI first to create widgets
        self._load_tickets()  # Then load data and refresh table
        self.update_theme()
        
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QtWidgets.QLabel("📋 Tickets en Espera")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        
        # Search Bar
        search_layout = QtWidgets.QHBoxLayout()
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar por cliente o ID...")
        self.search_input.setFixedHeight(35)
        self.search_input.textChanged.connect(self._refresh_table)
        
        search_layout.addWidget(QtWidgets.QLabel("Buscar:"))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Tickets Table
        self.tickets_table = QtWidgets.QTableWidget(0, 6)
        self.tickets_table.setHorizontalHeaderLabels([
            "ID", "Cliente", "Items", "Total", "Fecha", "Hora"
        ])
        self.tickets_table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.tickets_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tickets_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tickets_table.doubleClicked.connect(self._load_selected_ticket)
        self.tickets_table.setMinimumHeight(300)
        layout.addWidget(self.tickets_table)
        
        # Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.load_btn = QtWidgets.QPushButton("📥 Cargar Ticket")
        self.load_btn.clicked.connect(self._load_selected_ticket)
        self.load_btn.setFixedHeight(35)
        self.load_btn.setFixedWidth(150)
        
        self.delete_btn = QtWidgets.QPushButton("🗑 Eliminar")
        self.delete_btn.clicked.connect(self._delete_selected_ticket)
        self.delete_btn.setFixedHeight(35)
        self.delete_btn.setFixedWidth(120)
        
        self.delete_all_btn = QtWidgets.QPushButton("🗑 Eliminar Todo")
        self.delete_all_btn.clicked.connect(self._delete_all_tickets)
        self.delete_all_btn.setFixedHeight(35)
        self.delete_all_btn.setFixedWidth(140)
        
        close_btn = QtWidgets.QPushButton("Cerrar")
        close_btn.clicked.connect(self.reject)
        close_btn.setFixedHeight(35)
        close_btn.setFixedWidth(100)
        
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.delete_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # Status
        self.status_label = QtWidgets.QLabel(f"Total: 0 tickets")
        self.status_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        layout.addWidget(self.status_label)
        
    def _load_tickets(self) -> None:
        """Load pending tickets from JSON file."""
        if not PENDING_TICKETS_FILE.exists():
            self.pending_tickets = {}
            return
            
        try:
            with open(PENDING_TICKETS_FILE, 'r', encoding='utf-8') as f:
                self.pending_tickets = json.load(f)
        except Exception as e:
            print(f"Error loading pending tickets: {e}")
            self.pending_tickets = {}
        
        # Refresh table after loading
        self._refresh_table()
            
    def _save_tickets(self) -> None:
        """Save pending tickets to JSON file."""
        try:
            PENDING_TICKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PENDING_TICKETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.pending_tickets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving pending tickets: {e}")
            
    def _refresh_table(self) -> None:
        """Refresh the tickets table with current data."""
        search_query = self.search_input.text().lower()
        
        # Filter tickets
        filtered_tickets = {}
        for ticket_id, ticket_data in self.pending_tickets.items():
            customer_name = ticket_data.get('customer_name', 'Público General').lower()
            if search_query in ticket_id.lower() or search_query in customer_name:
                filtered_tickets[ticket_id] = ticket_data
                
        self.tickets_table.setRowCount(len(filtered_tickets))
        
        for row_idx, (ticket_id, ticket_data) in enumerate(filtered_tickets.items()):
            cart = ticket_data.get('cart', [])
            total = ticket_data.get('totals', {}).get('total', 0.0)
            customer = ticket_data.get('customer_name', 'Público General')
            timestamp = ticket_data.get('timestamp', datetime.now().isoformat())
            
            # Parse timestamp
            try:
                dt = datetime.fromisoformat(timestamp)
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                date_str = "N/A"
                time_str = "N/A"
                
            items = [
                ticket_id[:8] + "...",  # Shortened ID
                customer,
                str(len(cart)),
                f"${total:.2f}",
                date_str,
                time_str
            ]
            
            for col_idx, text in enumerate(items):
                item = QtWidgets.QTableWidgetItem(str(text))
                item.setData(QtCore.Qt.ItemDataRole.UserRole, ticket_id)  # Store full ID
                self.tickets_table.setItem(row_idx, col_idx, item)
                
        self.status_label.setText(f"Mostrando: {len(filtered_tickets)} de {len(self.pending_tickets)} tickets")
        
    def _load_selected_ticket(self) -> None:
        """Load the selected ticket and emit signal."""
        selected_rows = self.tickets_table.selectedIndexes()
        if not selected_rows:
            QtWidgets.QMessageBox.information(
                self,
                "Sin Selección",
                "Selecciona un ticket para cargar."
            )
            return
            
        row = selected_rows[0].row()
        ticket_id = self.tickets_table.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        
        if ticket_id in self.pending_tickets:
            ticket_data = self.pending_tickets[ticket_id]
            
            # Confirm before loading
            reply = QtWidgets.QMessageBox.question(
                self,
                "Cargar Ticket",
                f"¿Cargar ticket para '{ticket_data.get('customer_name', 'Público General')}'?\n\n"
                f"Items: {len(ticket_data.get('cart', []))}\n"
                f"Total: ${ticket_data.get('totals', {}).get('total', 0.0):.2f}",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Emit signal with ticket data
                self.ticket_loaded.emit(ticket_data)
                
                # Remove from pending
                del self.pending_tickets[ticket_id]
                self._save_tickets()
                
                self.accept()
                
    def _delete_selected_ticket(self) -> None:
        """Delete the selected ticket."""
        selected_rows = self.tickets_table.selectedIndexes()
        if not selected_rows:
            QtWidgets.QMessageBox.information(
                self,
                "Sin Selección",
                "Selecciona un ticket para eliminar."
            )
            return
            
        row = selected_rows[0].row()
        ticket_id = self.tickets_table.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Eliminar Ticket",
            "¿Estás seguro de eliminar este ticket?\n\nEsta acción no se puede deshacer.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            if ticket_id in self.pending_tickets:
                del self.pending_tickets[ticket_id]
                self._save_tickets()
                self._refresh_table()
                
    def _delete_all_tickets(self) -> None:
        """Delete all pending tickets."""
        if not self.pending_tickets:
            QtWidgets.QMessageBox.information(
                self,
                "Sin Tickets",
                "No hay tickets pendientes para eliminar."
            )
            return
            
        reply = QtWidgets.QMessageBox.question(
            self,
            "Eliminar Todos",
            f"¿Eliminar TODOS los {len(self.pending_tickets)} tickets pendientes?\n\n"
            "Esta acción no se puede deshacer.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.pending_tickets = {}
            self._save_tickets()
            self._refresh_table()
            
    def update_theme(self) -> None:
        """Apply minimal theme - use system defaults for visibility."""
        # Don't apply custom theme - just use default Qt styling
        # This ensures all text is visible regardless of theme configuration
        pass

def save_pending_ticket(cart: list, customer_id: int | None, customer_name: str | None, 
                        global_discount: dict | None, totals: dict) -> str:
    """
    Utility function to save a pending ticket.
    Returns the ticket_id.
    """
    import uuid
    
    ticket_id = str(uuid.uuid4())
    ticket_data = {
        "cart": cart,
        "customer_id": customer_id,
        "customer_name": customer_name or "Público General",
        "global_discount": global_discount,
        "totals": totals,
        "timestamp": datetime.now().isoformat()
    }
    
    # Load existing tickets
    pending_tickets = {}
    if PENDING_TICKETS_FILE.exists():
        try:
            with open(PENDING_TICKETS_FILE, 'r', encoding='utf-8') as f:
                pending_tickets = json.load(f)
        except Exception:
            pass
            
    # Add new ticket
    pending_tickets[ticket_id] = ticket_data
    
    # Save
    try:
        PENDING_TICKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PENDING_TICKETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending_tickets, f, indent=2, ensure_ascii=False)
        return ticket_id
    except Exception as e:
        print(f"Error saving pending ticket: {e}")
        return ""
