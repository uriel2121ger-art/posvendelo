"""
TITAN POS - Auto Sync Service EXHAUSTIVO v4.0 FINAL
Sincronización completa de 79 tablas críticas (77% del sistema)
"""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import logging
import threading
import time

from app.utils.sql_validators import SYNC_TABLES as VALID_SYNC_TABLES, validate_sync_table

logger = logging.getLogger("AUTO_SYNC")

# Lista maestra de 79 tablas sincronizadas
SYNC_TABLES = [
    "sales", "sale_items", "payments", "returns", "return_items", "sale_voids",
    "card_transactions", "sale_cfdi_relation", "customers", "gift_cards",
    "wallet_transactions", "loyalty_ledger", "loyalty_transactions", "loyalty_accounts",
    "loyalty_fraud_log", "loyalty_tier_history", "credit_movements", "credit_history",
    "employee_loans", "loan_payments", "cash_movements", "cash_expenses",
    "cash_extractions", "turn_movements", "turns", "personal_expenses",
    "products", "inventory_movements", "inventory_log", "inventory_transfers",
    "product_lots", "kit_items", "shadow_movements", "branch_inventory",
    "loss_records", "self_consumption", "transfer_items", "warehouse_pickups",
    "purchases", "purchase_orders", "purchase_order_items", "suppliers",
    "layaways", "layaway_items", "layaway_payments",
    "cfdis", "invoices", "pending_invoices", "cfdi_relations", "cross_invoices",
    "promotions", "categories", "online_orders", "order_items", "shipping_addresses",
    "activity_log", "audit_log", "employees", "users", "role_permissions",
    "branches", "emitters", "secuencias", "loyalty_rules", "product_categories",
    "price_change_history", "kit_items", "bin_locations", "purchase_costs",
    "transfer_suggestions", "shelf_reference_photos", "anonymous_wallet",
    "ghost_entries", "ghost_procurements", "ghost_transactions", "ghost_transfers",
    "ghost_wallets", "resurrection_bundles"
]

class AutoSyncServiceExhaustive:
    """
    Servicio de sincronización exhaustiva con el servidor central.
    Cubre las 79 tablas críticas del sistema TITAN POS.
    """
    
    def __init__(self, core, on_sync_complete: Optional[Callable] = None):
        self.core = core
        self.on_sync_complete = on_sync_complete
        self._running = False
        self._thread = None
        self._interval = 30
        self._last_sync = None
        self._sync_count = 0
        self._error_count = 0
        
    def configure(self):
        """Lee configuración desde el archivo."""
        cfg = self.core.get_app_config() or {}
        
        self.enabled = cfg.get("central_enabled", False) and cfg.get("auto_sync_enabled", True)
        self.central_url = cfg.get("central_url", "")
        self.central_token = cfg.get("central_token", "")
        self._interval = cfg.get("sync_interval", 30)
        
        self.branch_id = cfg.get("branch_id", 1)
        self.terminal_id = cfg.get("terminal_id", 1)
        
        return self.enabled and bool(self.central_url)
    
    def start(self):
        """Inicia la sincronización automática."""
        if not self.configure():
            logger.info("Sincro automática deshabilitada o no configurada")
            return False
        
        if self._running:
            logger.warning("Sincronización automática ya está corriendo")
            return True
        
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"✅ Sync exhaustivo v4.0 FINAL iniciado (cada {self._interval}s) - 79 tablas (77% del sistema)")
        return True
    
    def stop(self):
        """Detiene la sincronización automática."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Sincronización automática detenida")
    
    def _sync_loop(self):
        """Loop principal de sincronización."""
        while self._running:
            try:
                self._do_sync()
            except Exception as e:
                self._error_count += 1
                logger.error(f"Error en sync: {e}")
            
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _do_sync(self):
        """Ejecuta sincronización exhaustiva."""
        import requests
        
        if not self.central_url:
            return
        
        headers = {}
        if self.central_token:
            headers["Authorization"] = f"Bearer {self.central_token}"
        
        # Preparar batch exhaustivo
        batch = {
            "branch_id": self.branch_id,
            "terminal_id": self.terminal_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Recolectar TODAS las 79 tablas
        limits = {
            "sales": 100, "sale_items": 500, "payments": 100, "returns": 50,
            "return_items": 100, "sale_voids": 20, "card_transactions": 100,
            "sale_cfdi_relation": 100, "customers": 100, "gift_cards": 50,
            "wallet_transactions": 200, "loyalty_ledger": 200, "loyalty_transactions": 100,
            "loyalty_accounts": 50, "loyalty_fraud_log": 50, "loyalty_tier_history": 100,
            "credit_movements": 100, "credit_history": 100, "employee_loans": 30,
            "loan_payments": 50, "cash_movements": 100, "cash_expenses": 100,
            "cash_extractions": 50, "turn_movements": 100, "turns": 50,
            "personal_expenses": 50, "products": 500, "inventory_movements": 200,
            "inventory_log": 200, "inventory_transfers": 50, "product_lots": 100,
            "shadow_movements": 100, "branch_inventory": 500,
            "loss_records": 50, "self_consumption": 50, "transfer_items": 200,
            "warehouse_pickups": 50, "purchases": 50, "purchase_orders": 50,
            "purchase_order_items": 200, "suppliers": 100, "layaways": 30,
            "layaway_items": 100, "layaway_payments": 50, "cfdis": 100,
            "invoices": 100, "pending_invoices": 50, "cfdi_relations": 100,
            "cross_invoices": 50, "promotions": 50, "categories": 100,
            "online_orders": 50, "order_items": 200, "shipping_addresses": 100,
            "activity_log": 500, "audit_log": 500, "employees": 200,
            "users": 100, "role_permissions": 100, "branches": 50,
            "emitters": 20, "secuencias": 100, "loyalty_rules": 50,
            "product_categories": 200, "price_change_history": 500, "kit_items": 200,
            "bin_locations": 300, "purchase_costs": 200, "transfer_suggestions": 100,
            "shelf_reference_photos": 100, "anonymous_wallet": 500, "ghost_entries": 100,
            "ghost_procurements": 100, "ghost_transactions": 200, "ghost_transfers": 100,
            "ghost_wallets": 100, "resurrection_bundles": 50
        }
        
        for table in SYNC_TABLES:
            limit = limits.get(table, 100)
            batch[table] = self._get_unsynced(table, limit=limit)
        
        # Eliminar vacíos
        batch = {k: v for k, v in batch.items() if v}
        
        # Enviar si hay datos
        if len(batch) > 3:  # Más que solo metadata
            try:
                response = requests.post(
                    f"{self.central_url}/api/v1/sync",
                    json=batch,
                    headers=headers,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self._sync_count += 1
                    self._last_sync = datetime.now()
                    
                    # B.5: Marcar solo los IDs confirmados por el servidor (accepted)
                    # CRITICAL FIX 2026-02-03: NUNCA marcar como synced sin confirmación explícita
                    # El fallback anterior marcaba TODO aunque el servidor no confirmara,
                    # causando pérdida permanente de datos que nunca se sincronizarían
                    accepted = result.get("accepted") if isinstance(result, dict) else None
                    for table in SYNC_TABLES:
                        if not batch.get(table):
                            continue
                        if accepted and isinstance(accepted, dict) and table in accepted and accepted[table] is not None:
                            ids = accepted[table]
                            self._mark_synced(table, [{"id": i} for i in ids])
                            logger.debug(f"✅ Marked {len(ids)} {table} as synced (server confirmed)")
                        else:
                            # CRITICAL: NO marcar como synced sin confirmación del servidor
                            # Los registros mantendrán synced=0 y se reintentarán
                            logger.warning(
                                f"⚠️ Server did NOT confirm {table} sync - keeping {len(batch.get(table, []))} records with synced=0. "
                                f"They will be retried on next sync cycle."
                            )
                    
                    logger.info(f"✅ Sync #{self._sync_count}: {len(batch)-3} tipos de datos sincronizados")
                    
                    if self.on_sync_complete:
                        self.on_sync_complete(result)
                else:
                    self._error_count += 1
                    logger.warning(f"Error en sync: HTTP {response.status_code}")
                    
            except Exception as e:
                self._error_count += 1
                logger.warning(f"Error de conexión en sync: {e}")
    
    def _get_unsynced(self, table: str, limit: int = 100) -> List[Dict]:
        """Obtiene registros no sincronizados de cualquier tabla."""
        # SECURITY: Validate table against whitelist
        try:
            validated_table = validate_sync_table(table)
        except ValueError as e:
            logger.warning(f"Tabla no permitida para sync: {table} - {e}")
            return []

        # SECURITY: Enforce limit bounds
        limit = max(1, min(int(limit), 1000))

        try:
            # Usar execute_query en lugar de db_lock para evitar deadlocks
            query = f"SELECT * FROM {validated_table} WHERE synced = 0 OR synced IS NULL ORDER BY id LIMIT %s"
            rows = self.core.db.execute_query(query, (limit,))
            
            if not rows:
                return []
            
            # Obtener nombres de columnas del primer resultado
            # execute_query retorna sqlite3.Row objects que soportan dict()
            return [dict(row) for row in rows]
                
        except Exception as e:
            logger.debug(f"Error obteniendo {table}: {e}")
            return []
    
    def _mark_synced(self, table: str, records: List[Dict]):
        """Marca registros como sincronizados."""
        if not records:
            return

        # SECURITY: Validate table against whitelist
        try:
            validated_table = validate_sync_table(table)
        except ValueError as e:
            logger.warning(f"Tabla no permitida para mark_synced: {table} - {e}")
            return

        try:
            ids = [r.get("id") for r in records if r.get("id")]
            if not ids:
                return

            # Batching para evitar límite de placeholders
            batch_size = 800
            for i in range(0, len(ids), batch_size):
                batch = ids[i:i+batch_size]
                placeholders = ",".join(["%s"] * len(batch))

                # USA execute_write como GhostSyncEngine (sin lock explícito)
                # execute_write tiene su propio retry logic interno
                self.core.db.execute_write(
                    f"UPDATE {validated_table} SET synced = 1 WHERE id IN ({placeholders})",
                    tuple(batch)
                )
                
        except Exception as e:
            logger.error(f"Error marcando {table} como synced: {e}")
    
    def get_status(self):
        """Retorna estado del servicio."""
        return {
            "running": self._running,
            "enabled": getattr(self, 'enabled', False),
            "central_url": getattr(self, 'central_url', ''),
            "interval": self._interval,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "sync_count": self._sync_count,
            "error_count": self._error_count
        }
    
    def force_sync(self):
        """Fuerza sincronización inmediata."""
        if not self.configure():
            return {"success": False, "error": "No configurado"}
        
        try:
            self._do_sync()
            return {"success": True, "last_sync": self._last_sync.isoformat() if self._last_sync else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Singleton global (thread-safe)
_sync_service = None
_sync_service_lock = threading.Lock()


def get_sync_service(core=None) -> AutoSyncServiceExhaustive | None:
    """Obtiene o crea el servicio de sincronización. Thread-safe."""
    global _sync_service
    with _sync_service_lock:
        if _sync_service is None and core:
            _sync_service = AutoSyncServiceExhaustive(core)
        return _sync_service

def start_auto_sync(core):
    """Inicia el servicio de sincronización automática."""
    service = get_sync_service(core)
    if service:
        return service.start()
    return False

def stop_auto_sync():
    """Detiene el servicio de sincronización automática."""
    global _sync_service
    with _sync_service_lock:
        if _sync_service:
            _sync_service.stop()
