"""
Stealth & Panic Layer (Black Tier)
Phantom Mode, Biometric Kill, and Black Hole (Surgical Deletion).
"""

from typing import Any, Dict, List
from datetime import datetime
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class StealthLayer:
    def __init__(self, db):
        self.db = db
        self.duress_mode = False

    def _hash_pin(self, pin: str) -> str:
        return hashlib.sha256(f"biometric_kill_{pin}".encode()).hexdigest()

    async def configure_pins(self, normal_pin: str, duress_pin: str, wipe_pin: str = None) -> Dict[str, Any]:
        if normal_pin == duress_pin:
            return {'success': False, 'error': 'PINs no pueden ser iguales'}

        await self.db.execute("INSERT INTO config (key, value) VALUES ('normal_pin_hash', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", val=self._hash_pin(normal_pin))
        await self.db.execute("INSERT INTO config (key, value) VALUES ('duress_pin_hash', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", val=self._hash_pin(duress_pin))

        if wipe_pin:
            await self.db.execute("INSERT INTO config (key, value) VALUES ('wipe_pin_hash', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", val=self._hash_pin(wipe_pin))

        return {'success': True, 'message': 'PINs configurados'}

    async def verify_pin(self, pin: str) -> Dict[str, Any]:
        pin_hash = self._hash_pin(pin)

        row_normal = await self.db.fetchrow("SELECT value FROM config WHERE key = 'normal_pin_hash'")
        row_duress = await self.db.fetchrow("SELECT value FROM config WHERE key = 'duress_pin_hash'")
        row_wipe = await self.db.fetchrow("SELECT value FROM config WHERE key = 'wipe_pin_hash'")

        normal_h = row_normal['value'] if row_normal else None
        duress_h = row_duress['value'] if row_duress else None
        wipe_h = row_wipe['value'] if row_wipe else None

        if normal_h and pin_hash == normal_h:
            self.duress_mode = False
            return {'authenticated': True, 'mode': 'normal', 'message': 'Acceso concedido'}
        elif duress_h and pin_hash == duress_h:
            self.duress_mode = True
            await self._trigger_silent_alert()
            return {'authenticated': True, 'mode': 'duress', 'message': 'Modo espejo activado'}
        elif wipe_h and pin_hash == wipe_h:
            return {'authenticated': False, 'mode': 'wipe', 'message': 'Protocolo de emergencia activado'}

        return {'authenticated': False, 'mode': 'denied', 'message': 'PIN incorrecto'}

    async def _trigger_silent_alert(self):
        alert_data = {'type': 'DURESS', 'timestamp': datetime.now().isoformat(), 'message': 'PIN coacción usado'}
        await self.db.execute("INSERT INTO config (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            k=f"duress_{datetime.now().timestamp()}", v=json.dumps(alert_data))

    async def surgical_delete(self, sale_ids: List[int], confirm_phrase: str = None) -> Dict[str, Any]:
        if confirm_phrase != "CONFIRMO ELIMINACION":
            return {'success': False, 'error': 'Confirmación no válida'}
        if not sale_ids:
            return {'success': False, 'error': 'No hay IDs provistos'}

        conn = self.db.connection
        async with conn.transaction():
            for sid in sale_ids:
                items = await self.db.fetch("SELECT product_id, qty FROM sale_items WHERE sale_id = :sid", sid=sid)

                for item in items:
                    await self.db.execute("UPDATE products SET stock = stock + :qty WHERE id = :pid", qty=item['qty'], pid=item['product_id'])
                    try:
                        await self.db.execute("""
                            INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, reference_id, timestamp, synced)
                            VALUES (:pid, 'IN', 'black_hole', :qty, 'Reversión black_hole', 'black_hole', :sid, NOW(), 0)
                        """, pid=item['product_id'], qty=item['qty'], sid=sid)
                    except Exception:
                        pass

                await self.db.execute("DELETE FROM sale_items WHERE sale_id = :sid", sid=sid)
                await self.db.execute("DELETE FROM payments WHERE sale_id = :sid", sid=sid)
                await self.db.execute("DELETE FROM sales WHERE id = :sid AND serie = 'B'", sid=sid)

        return {'success': True, 'deleted_count': len(sale_ids), 'message': f'{len(sale_ids)} tickets Serie B eliminados'}

    async def activate_phantom_mode(self) -> Dict[str, Any]:
        self.duress_mode = True
        return {'success': True, 'message': 'Modo fantasma activado'}

    async def deactivate_phantom_mode(self, pin: str) -> Dict[str, Any]:
        res = await self.verify_pin(pin)
        if res['mode'] == 'normal':
            self.duress_mode = False
            return {'success': True, 'message': 'Modo normal restaurado'}
        return {'success': False, 'error': 'PIN inválido para restauración'}
