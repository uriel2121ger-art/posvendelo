"""
Stealth & Panic Layer (Black Tier)
Unifies Phantom Mode, Biometric Kill, and Black Hole (Surgical Deletion).
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import hashlib
import json
import secrets
import asyncio

logger = logging.getLogger(__name__)

class StealthLayer:
    """
    Sistema de protección bajo coacción, modo fantasma y eliminación quirúrgica.
    """
    def __init__(self, db):
        self.db = db
        self.duress_mode = False
    
    # ---------------------------------------------------------
    # BIOMETRIC KILL & DURESS PIN
    # ---------------------------------------------------------
    
    def _hash_pin(self, pin: str) -> str:
        return hashlib.sha256(f"biometric_kill_{pin}".encode()).hexdigest()
        
    async def configure_pins(self, normal_pin: str, duress_pin: str, wipe_pin: str = None) -> Dict[str, Any]:
        """Configure the 3 tier PINs: normal, duress (mirror mode), wipe (panic)."""
        if normal_pin == duress_pin:
            return {'success': False, 'error': 'PINs no pueden ser iguales'}
            
        await self.db.execute("INSERT INTO config (key, value) VALUES ('normal_pin_hash', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", {"val": self._hash_pin(normal_pin)})
        await self.db.execute("INSERT INTO config (key, value) VALUES ('duress_pin_hash', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", {"val": self._hash_pin(duress_pin)})
        
        if wipe_pin:
            await self.db.execute("INSERT INTO config (key, value) VALUES ('wipe_pin_hash', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", {"val": self._hash_pin(wipe_pin)})
            
        return {'success': True, 'message': 'PINs configurados'}
        
    async def verify_pin(self, pin: str) -> Dict[str, Any]:
        """Verify the PIN and activate the corresponding system mode."""
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
            # WIPE 
            return {'authenticated': False, 'mode': 'wipe', 'message': 'Protocolo de emergencia activado'}
            
        return {'authenticated': False, 'mode': 'denied', 'message': 'PIN incorrecto'}
        
    async def _trigger_silent_alert(self):
        alert_data = {'type': 'DURESS', 'timestamp': datetime.now().isoformat(), 'message': 'PIN coacción usado'}
        await self.db.execute("INSERT INTO config (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", {"k": f"duress_{datetime.now().timestamp()}", "v": json.dumps(alert_data)})
        
    # ---------------------------------------------------------
    # BLACK HOLE (Surgical Deletion)
    # ---------------------------------------------------------
    
    async def surgical_delete(self, sale_ids: List[int], confirm_phrase: str = None) -> Dict[str, Any]:
        """Elimina transacciones Serie B facturadas a posteriori sin dejar rastro."""
        if confirm_phrase != "CONFIRMO ELIMINACION":
            return {'success': False, 'error': 'Confirmación no válida'}
            
        if not sale_ids:
            return {'success': False, 'error': 'No hay IDs provistos'}
            
        # Execute deletion inside an atomic transaction
        async with self.db.acquire() as conn:
            async with conn.transaction():
                for sid in sale_ids:
                    # Retrieve items for inventory reversal
                    items = await conn.fetch("SELECT product_id, qty FROM sale_items WHERE sale_id = :sid", sid=sid)
                    
                    # Reverse inventory
                    for item in items:
                        await conn.execute("UPDATE products SET stock = stock + :qty WHERE id = :pid", qty=item['qty'], pid=item['product_id'])
                        try:
                            await conn.execute("INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, reference_id, timestamp, synced) VALUES (:pid, 'IN', 'black_hole', :qty, 'Reversión black_hole', 'black_hole', :sid, NOW(), 0)", pid=item['product_id'], qty=item['qty'], sid=sid)
                        except Exception:
                            logger.warning(f"Failed to record inventory movement for black hole erase on product {item['product_id']}")

                    # Delete dependencies
                    await conn.execute("DELETE FROM sale_items WHERE sale_id = :sid", sid=sid)
                    await conn.execute("DELETE FROM payments WHERE sale_id = :sid", sid=sid)
                    await conn.execute("DELETE FROM sales WHERE id = :sid AND serie = 'B'", sid=sid)
        
        return {'success': True, 'deleted_count': len(sale_ids), 'message': f'{len(sale_ids)} tickets Serie B eliminados'}

    # ---------------------------------------------------------
    # AUDIT-SAFE (Phantom Mode & Data Hiding)
    # ---------------------------------------------------------
    
    async def activate_phantom_mode(self) -> Dict[str, Any]:
        """Activa el modo fantasma (oculta datos Serie B a nivel API/Dashboard)."""
        self.duress_mode = True
        return {'success': True, 'message': 'Modo fantasma activado'}

    async def deactivate_phantom_mode(self, pin: str) -> Dict[str, Any]:
        res = await self.verify_pin(pin)
        if res['mode'] == 'normal':
            self.duress_mode = False
            return {'success': True, 'message': 'Modo normal restaurado'}
        return {'success': False, 'error': 'PIN inválido para restauración'}
