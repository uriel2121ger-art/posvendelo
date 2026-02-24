from pathlib import Path

"""
Ghost-Carrier - Sistema de Traspasos Sombra
Vales de almacén internos sin impacto fiscal
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import logging
import sys

logger = logging.getLogger(__name__)

class GhostCarrier:
    """
    Sistema de logística de traspasos sin fiscalización.
    
    Genera vales de almacén técnicos sin:
    - Precios
    - RFCs
    - Sellos fiscales
    
    Solo contiene: SKU, descripción técnica, pesos, dimensiones.
    """
    
    def __init__(self, core):
        self.core = core
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Crea tablas para traspasos sombra."""
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS ghost_transfers (
                id BIGSERIAL PRIMARY KEY,
                transfer_code TEXT UNIQUE NOT NULL,
                origin_branch TEXT NOT NULL,
                destination_branch TEXT NOT NULL,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                received_at TEXT,
                received_by INTEGER,
                status TEXT DEFAULT 'pending',
                items_json TEXT,
                total_items INTEGER,
                total_weight_kg DOUBLE PRECISION,
                notes TEXT
            )
        """)
    
    def create_transfer(self, 
                       origin: str, 
                       destination: str, 
                       items: List[Dict],
                       user_id: int,
                       notes: str = "") -> Dict[str, Any]:
        """
        Crea un traslado entre sucursales.
        
        Args:
            origin: Sucursal origen
            destination: Sucursal destino
            items: Lista de {product_id, quantity, sku, name}
            user_id: ID del usuario que crea
            notes: Notas adicionales
        
        Returns:
            Datos del traslado con código único
        """
        # Generar código único de traslado
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        hash_input = f"{origin}{destination}{timestamp}{user_id}"
        transfer_code = f"TR-{hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()}"
        
        # Calcular totales
        total_items = sum(item['quantity'] for item in items)
        total_weight = sum(
            item.get('weight_kg', 0.1) * item['quantity'] 
            for item in items
        )
        
        # Enriquecer items con datos técnicos (sin precios)
        enriched_items = []
        for item in items:
            product = self._get_product_tech_data(item['product_id'])
            enriched_items.append({
                'sku': product.get('sku', f"SKU-{item['product_id']}"),
                'description': product.get('name', 'Producto'),
                'quantity': item['quantity'],
                'unit': product.get('unit', 'PZA'),
                'weight_kg': product.get('weight_kg', 0.1),
                'dimensions': product.get('dimensions', 'N/A'),
                # NO incluir precio
            })
        
        # Guardar en base de datos
        self.core.db.execute_query("""
            INSERT INTO ghost_transfers 
            (transfer_code, origin_branch, destination_branch, created_by, 
             items_json, total_items, total_weight_kg, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            transfer_code, origin, destination, user_id,
            json.dumps(enriched_items), total_items, total_weight, notes
        ), commit=True)
        
        # Descontar stock en origen (Serie B shadow)
        self._update_origin_stock(origin, items, 'subtract')
        
        # SECURITY: No loguear operaciones Ghost Transfer
        pass
        
        return {
            'success': True,
            'transfer_code': transfer_code,
            'origin': origin,
            'destination': destination,
            'total_items': total_items,
            'total_weight_kg': round(total_weight, 2),
            'status': 'pending'
        }
    
    def receive_transfer(self, transfer_code: str, user_id: int) -> Dict[str, Any]:
        """
        Marca un traslado como recibido y actualiza stock destino.
        """
        # Obtener traslado
        transfers = list(self.core.db.execute_query("""
            SELECT * FROM ghost_transfers 
            WHERE transfer_code = %s AND status = 'pending'
        """, (transfer_code,)))
        
        if not transfers:
            return {'success': False, 'error': 'Traslado no encontrado o ya recibido'}
        
        transfer = transfers[0]
        items = json.loads(transfer['items_json'])
        
        # Actualizar stock en destino
        for item in items:
            # Buscar producto por SKU
            products = list(self.core.db.execute_query("""
                SELECT id FROM products WHERE sku = %s OR barcode = %s
            """, (item['sku'], item['sku'])))
            
            if products:
                pid = products[0]['id']
                qty = item['quantity']
                self.core.db.execute_query("""
                    UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
                """, (qty, pid), commit=True)
                try:
                    self.core.db.execute_write(
                        """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                           VALUES (%s, 'IN', 'ghost_transfer', %s, %s, 'ghost_transfer', NOW(), 0)""",
                        (pid, qty, f"Recepción {transfer_code}")
                    )
                except Exception as e:
                    logger.debug("ghost_carrier movement: %s", e)
        
        # Marcar como recibido
        self.core.db.execute_query("""
            UPDATE ghost_transfers 
            SET status = 'received', received_at = %s, received_by = %s
            WHERE transfer_code = %s
        """, (datetime.now().isoformat(), user_id, transfer_code), commit=True)
        
        # SECURITY: No loguear recepción de Ghost Transfer
        pass
        
        return {
            'success': True,
            'transfer_code': transfer_code,
            'received_at': datetime.now().isoformat()
        }
    
    def generate_warehouse_slip(self, transfer_code: str) -> Dict[str, Any]:
        """
        Genera datos para PDF de vale de almacén.
        SIN PRECIOS, SIN RFC, SIN SELLOS.
        """
        transfers = list(self.core.db.execute_query("""
            SELECT * FROM ghost_transfers WHERE transfer_code = %s
        """, (transfer_code,)))
        
        if not transfers:
            return None
        
        transfer = transfers[0]
        items = json.loads(transfer['items_json'])
        
        return {
            'document_type': 'VALE DE ALMACÉN - USO INTERNO',
            'document_number': transfer_code,
            'date': datetime.fromisoformat(transfer['created_at']).strftime('%d/%m/%Y'),
            'time': datetime.fromisoformat(transfer['created_at']).strftime('%H:%M'),
            
            'origin': {
                'name': f"Bodega {transfer['origin_branch'].upper()}",
                'address': self._get_branch_address(transfer['origin_branch'])
            },
            'destination': {
                'name': f"Bodega {transfer['destination_branch'].upper()}",
                'address': self._get_branch_address(transfer['destination_branch'])
            },
            
            'items': [
                {
                    'line': i + 1,
                    'sku': item['sku'],
                    'description': item['description'],
                    'quantity': item['quantity'],
                    'unit': item['unit'],
                    'weight': f"{item['weight_kg']:.2f} kg",
                    'dimensions': item.get('dimensions', 'N/A')
                }
                for i, item in enumerate(items)
            ],
            
            'totals': {
                'total_items': transfer['total_items'],
                'total_weight': f"{transfer['total_weight_kg']:.2f} kg"
            },
            
            'notes': transfer.get('notes', ''),
            
            'footer': 'MOVIMIENTO DE INVENTARIO PROPIO ENTRE BODEGAS',
            
            # Campos de firma
            'signatures': {
                'prepared_by': '________________________',
                'transported_by': '________________________',
                'received_by': '________________________'
            }
        }
    
    def _get_product_tech_data(self, product_id: int) -> Dict:
        """Obtiene datos técnicos del producto (sin precios)."""
        products = list(self.core.db.execute_query("""
            SELECT barcode as sku, name, unit, 0.1 as weight_kg
            FROM products WHERE id = %s
        """, (product_id,)))
        
        if products:
            return dict(products[0])
        return {'sku': f'SKU-{product_id}', 'name': 'Producto', 'unit': 'PZA', 'weight_kg': 0.1}
    
    def _get_branch_address(self, branch: str) -> str:
        """Retorna dirección genérica de sucursal."""
        addresses = {
            'centro': 'Av. Principal #123, Centro',
            'norte': 'Calle Norte #456, Col. Norte',
            'poniente': 'Blvd Poniente #789, Fraccionamiento'
        }
        return addresses.get(branch.lower(), 'Mérida, Yucatán')
    
    def _update_origin_stock(self, branch: str, items: List[Dict], operation: str):
        """Actualiza stock en origen (Parte A Fase 1.4: registrar movimiento)."""
        for item in items:
            if operation == 'subtract':
                pid, qty = item['product_id'], item['quantity']
                self.core.db.execute_query("""
                    UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
                """, (qty, pid), commit=True)
                try:
                    self.core.db.execute_write(
                        """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                           VALUES (%s, 'OUT', 'ghost_transfer', %s, %s, 'ghost_transfer', NOW(), 0)""",
                        (pid, qty, f"Envío desde {branch}")
                    )
                except Exception as e:
                    logger.debug("ghost_carrier origin movement: %s", e)
    
    def get_pending_transfers(self, branch: str = None) -> List[Dict]:
        """Lista traspasos pendientes de recibir."""
        query = "SELECT * FROM ghost_transfers WHERE status = 'pending'"
        params = ()
        
        if branch:
            query += " AND destination_branch = %s"
            params = (branch,)
        
        return [dict(t) for t in self.core.db.execute_query(query, params)]

# Función de conveniencia
def create_ghost_transfer(core, origin, destination, items, user_id, notes=""):
    """Wrapper para crear traslado sombra."""
    carrier = GhostCarrier(core)
    return carrier.create_transfer(origin, destination, items, user_id, notes)
