"""
Ghost Carrier - Traspasos Sombra entre Sucursales
Vales de almacén internos sin impacto fiscal
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class GhostCarrier:
    def __init__(self, db):
        self.db = db

    async def ensure_table(self):
        await self.db.execute("""
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

    async def create_transfer(self, origin: str, destination: str, items: List[Dict],
                               user_id: int, notes: str = "") -> Dict[str, Any]:
        await self.ensure_table()
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        hash_input = f"{origin}{destination}{timestamp}{user_id}"
        transfer_code = f"TR-{hashlib.sha256(hash_input.encode()).hexdigest()[:8].upper()}"

        total_items = sum(item['quantity'] for item in items)
        total_weight = sum(item.get('weight_kg', 0.1) * item['quantity'] for item in items)

        enriched = []
        for item in items:
            product = await self._get_product_tech(item['product_id'])
            enriched.append({
                'sku': product.get('sku', f"SKU-{item['product_id']}"),
                'description': product.get('name', 'Producto'),
                'quantity': item['quantity'],
                'unit': product.get('unit', 'PZA'),
                'weight_kg': product.get('weight_kg', 0.1),
            })

        conn = self.db.connection
        async with conn.transaction():
            await self.db.execute("""
                INSERT INTO ghost_transfers
                (transfer_code, origin_branch, destination_branch, created_by, items_json, total_items, total_weight_kg, notes)
                VALUES (:code, :origin, :dest, :uid, :items, :ti, :tw, :notes)
            """, code=transfer_code, origin=origin, dest=destination, uid=user_id,
                items=json.dumps(enriched), ti=total_items, tw=total_weight, notes=notes)

            for item in items:
                pid, qty = item['product_id'], item['quantity']
                row = await self.db.fetchrow(
                    "SELECT stock FROM products WHERE id = :pid FOR UPDATE", pid=pid)
                if not row or Decimal(row['stock'] or 0) < qty:
                    raise ValueError(f"Stock insuficiente para producto {pid}")
                await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", qty=qty, pid=pid)
                try:
                    await self.db.execute("""
                        INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                        VALUES (:pid, 'OUT', 'ghost_transfer', :qty, 'Envío ghost_carrier', 'ghost_transfer', NOW(), 0)
                    """, pid=pid, qty=qty)
                except Exception:
                    pass

        return {
            'success': True, 'transfer_code': transfer_code, 'origin': origin,
            'destination': destination, 'total_items': total_items,
            'total_weight_kg': round(total_weight, 2), 'status': 'pending'
        }

    async def receive_transfer(self, transfer_code: str, user_id: int) -> Dict[str, Any]:
        await self.ensure_table()
        conn = self.db.connection
        async with conn.transaction():
            row = await self.db.fetchrow(
                "SELECT * FROM ghost_transfers WHERE transfer_code = :code AND status = 'pending' FOR UPDATE",
                code=transfer_code,
            )
            if not row:
                return {'success': False, 'error': 'Traslado no encontrado o ya recibido'}

            items = json.loads(row['items_json'])
            for item in items:
                prod = await self.db.fetchrow(
                    "SELECT id FROM products WHERE sku = :sku LIMIT 1",
                    sku=item['sku']
                )
                if prod:
                    pid, qty = prod['id'], item['quantity']
                    await self.db.execute("UPDATE products SET stock = stock + :qty, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", qty=qty, pid=pid)
                    try:
                        await self.db.execute("""
                            INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                            VALUES (:pid, 'IN', 'ghost_transfer', :qty, :reason, 'ghost_transfer', NOW(), 0)
                        """, pid=pid, qty=qty, reason=f"Recepción {transfer_code}")
                    except Exception:
                        pass

            await self.db.execute(
                "UPDATE ghost_transfers SET status = 'received', received_at = :rat, received_by = :uid WHERE transfer_code = :code",
                rat=datetime.now().isoformat(), uid=user_id, code=transfer_code
            )
        return {'success': True, 'transfer_code': transfer_code, 'received_at': datetime.now().isoformat()}

    async def generate_warehouse_slip(self, transfer_code: str) -> Dict[str, Any]:
        row = await self.db.fetchrow("SELECT * FROM ghost_transfers WHERE transfer_code = :code", code=transfer_code)
        if not row:
            return None

        items = json.loads(row['items_json'])
        return {
            'document_type': 'VALE DE ALMACÉN - USO INTERNO',
            'document_number': transfer_code,
            'date': datetime.fromisoformat(row['created_at']).strftime('%d/%m/%Y') if isinstance(row['created_at'], str) else row['created_at'].strftime('%d/%m/%Y'),
            'origin': row['origin_branch'], 'destination': row['destination_branch'],
            'items': [{'line': i+1, 'sku': it['sku'], 'description': it['description'],
                        'quantity': it['quantity'], 'unit': it['unit']} for i, it in enumerate(items)],
            'totals': {'total_items': row['total_items'], 'total_weight': f"{row['total_weight_kg']:.2f} kg"},
            'footer': 'MOVIMIENTO DE INVENTARIO PROPIO ENTRE BODEGAS'
        }

    async def get_pending_transfers(self, branch: str = None) -> List[Dict]:
        await self.ensure_table()
        if branch:
            rows = await self.db.fetch("SELECT * FROM ghost_transfers WHERE status = 'pending' AND destination_branch = :branch", branch=branch)
        else:
            rows = await self.db.fetch("SELECT * FROM ghost_transfers WHERE status = 'pending'")
        return [dict(r) for r in rows]

    async def _get_product_tech(self, product_id: int) -> Dict:
        row = await self.db.fetchrow("SELECT sku, name FROM products WHERE id = :pid", pid=product_id)
        if row:
            r = dict(row)
            r['unit'] = 'PZA'
            r['weight_kg'] = 0.1
            return r
        return {'sku': f'SKU-{product_id}', 'name': 'Producto', 'unit': 'PZA', 'weight_kg': 0.1}

    async def _update_origin_stock(self, items: List[Dict]):
        for item in items:
            pid, qty = item['product_id'], item['quantity']
            await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", qty=qty, pid=pid)
            try:
                await self.db.execute("""
                    INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                    VALUES (:pid, 'OUT', 'ghost_transfer', :qty, 'Envío ghost_carrier', 'ghost_transfer', NOW(), 0)
                """, pid=pid, qty=qty)
            except Exception:
                pass
