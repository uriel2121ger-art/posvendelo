"""
Ghost-Sync Engine - Sincronización cifrada por lotes
Arquitectura distribuida para multi-sucursal con nodo maestro local
"""

from typing import Any, Dict, List, Optional
import base64
from datetime import datetime, timedelta
import gzip
import hashlib
import json
import logging
import os  # SECURITY: For cryptographically secure random IV
from pathlib import Path
import queue
import sys
import threading
import time
import uuid

logger = logging.getLogger(__name__)

# Intentar importar cryptography para AES
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography no instalado - usando fallback")

class GhostSyncEngine:
    """
    Motor de sincronización fantasma para arquitectura distribuida.
    
    Características:
    - Sincronización por lotes (batching) para evitar patrones de tráfico
    - Cifrado AES-256 de payloads
    - Resolución de conflictos por timestamp
    - Cola de sincronización en memoria (zero disk footprint)
    """
    
    BATCH_SIZE = 50  # Ventas por paquete
    SYNC_INTERVAL = 300  # 5 minutos entre sincronizaciones
    
    def __init__(self, core, branch_id: int = 1, pos_id: int = 1):
        self.core = core
        self.branch_id = branch_id
        self.pos_id = pos_id
        self.node_id = f"{branch_id}-{pos_id}-{uuid.uuid4().hex[:8]}"

        # Cola de sincronizacion (en RAM + BD persistente)
        # queue.Queue is already thread-safe
        self.sync_queue = queue.Queue()

        # Lock for pending_count (atomic operations)
        self._pending_lock = threading.Lock()
        self._pending_count = 0

        # FIX 2026-02-01: Cargar items pendientes de la BD al iniciar
        self._load_pending_from_db()

        # Configuracion de sincronizacion
        self.central_url = None  # Se configura con set_central_server
        self.encryption_key = None

        # Estado
        self.last_sync = None
        self._state_lock = threading.Lock()
        self._sync_active = False
        self._sync_thread = None

    @property
    def pending_count(self) -> int:
        """Thread-safe access to pending count."""
        with self._pending_lock:
            return self._pending_count

    @property
    def sync_active(self) -> bool:
        """Thread-safe access to sync_active flag."""
        with self._state_lock:
            return self._sync_active

    @sync_active.setter
    def sync_active(self, value: bool) -> None:
        """Thread-safe setter for sync_active flag."""
        with self._state_lock:
            self._sync_active = value

    def _increment_pending(self, delta: int = 1) -> None:
        """Thread-safe increment of pending count."""
        with self._pending_lock:
            self._pending_count += delta

    def _decrement_pending(self, delta: int = 1) -> None:
        """Thread-safe decrement of pending count."""
        with self._pending_lock:
            self._pending_count = max(0, self._pending_count - delta)

    def _load_pending_from_db(self):
        """Carga items pendientes de sync_queue al iniciar."""
        try:
            rows = self.core.db.execute_query(
                """SELECT id, table_name, record_id, payload, node_id, created_at
                   FROM sync_queue
                   WHERE synced = FALSE
                   ORDER BY created_at ASC
                   LIMIT 1000"""
            )
            if rows:
                for row in rows:
                    item = {
                        'db_id': row['id'],
                        'table': row['table_name'],
                        'id': row['record_id'],
                        'data': json.loads(row['payload']) if row['payload'] else {},
                        'timestamp': row['created_at'],
                        'node_id': row['node_id'] or self.node_id
                    }
                    self.sync_queue.put(item)
                    self._increment_pending()
                logger.info("Loaded %d pending sync items from database", len(rows))
        except Exception as e:
            # Si la tabla no existe aún, ignorar
            logger.debug("Could not load from sync_queue (may not exist yet): %s", e)
    
    def configure(self, central_url: str, encryption_key: bytes):
        """Configura el servidor central y la llave de cifrado."""
        self.central_url = central_url
        self.encryption_key = encryption_key
        # SECURITY: No loguear configuración de sync
        pass
    
    def start_background_sync(self):
        """Inicia el thread de sincronización en background."""
        with self._state_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                return
            self._sync_active = True
            self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self._sync_thread.start()
        # SECURITY: No loguear inicio de Ghost-Sync
        pass

    def stop_sync(self):
        """Detiene la sincronización y espera que termine."""
        self.sync_active = False
        with self._state_lock:
            thread = self._sync_thread
        if thread:
            # Esperar más tiempo para que termine de procesar la cola
            thread.join(timeout=30)
            if thread.is_alive():
                logger.warning("Sync thread did not stop gracefully")
        # SECURITY: No loguear detención de Ghost-Sync
        pass
    
    def _sync_loop(self):
        """Loop principal de sincronización."""
        while self.sync_active:
            try:
                self.sync_pending()
            except Exception as e:
                logger.error("Error en sync loop: %s", e)

            time.sleep(self.SYNC_INTERVAL)

        # Al detenerse, procesar items pendientes en cola
        try:
            if not self.sync_queue.empty():
                logger.info("Processing %d remaining items before shutdown...", self.sync_queue.qsize())
                self.sync_pending()
        except Exception as e:
            logger.error("Error processing remaining sync items: %s", e)
    
    def queue_for_sync(self, table: str, record_id: int, data: Dict):
        """Añade un registro a la cola de sincronización (RAM + BD persistente)."""
        item = {
            'table': table,
            'id': record_id,
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'node_id': self.node_id
        }
        try:
            db_id = self.core.db.execute_write(
                """INSERT INTO sync_queue (table_name, record_id, payload, node_id)
                   VALUES (%s, %s, %s, %s)""",
                (table, record_id, json.dumps(data), self.node_id)
            )
            if db_id:
                item['db_id'] = int(db_id)
        except Exception as e:
            logger.debug("Could not persist to sync_queue: %s", e)
        self.sync_queue.put(item)
        self._increment_pending()
    
    def sync_pending(self) -> Dict[str, Any]:
        """Sincroniza registros pendientes al servidor central."""
        if not self.central_url:
            return {'error': 'No central server configured'}
        
        # Recolectar batch
        batch = []
        while len(batch) < self.BATCH_SIZE and not self.sync_queue.empty():
            try:
                batch.append(self.sync_queue.get_nowait())
            except queue.Empty:
                break
        
        if not batch:
            return {'synced': 0}
        
        # Cifrar payload
        payload = self._encrypt_payload(batch)
        
        # Enviar al central
        try:
            import urllib.request
            
            req = urllib.request.Request(
                f"{self.central_url}/api/sync/receive",
                data=payload,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'X-Node-ID': self.node_id,
                    'X-Branch-ID': str(self.branch_id)
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    self.last_sync = datetime.now()
                    self._decrement_pending(len(batch))

                    # B.5: Marcar solo IDs confirmados por el servidor si la respuesta los incluye
                    sale_ids_to_mark = None
                    try:
                        body = response.read()
                        if body:
                            data = json.loads(body.decode())
                            sale_ids_to_mark = data.get('accepted_ids') or data.get('accepted_sale_ids')
                    except Exception as e:
                        logger.warning(f"Could not parse sync response body: {e}")
                    if sale_ids_to_mark is None:
                        sale_ids_to_mark = [r['id'] for r in batch if r.get('table') == 'sales']
                    if sale_ids_to_mark:
                        self._mark_synced(sale_ids_to_mark)

                    self._mark_queue_items_synced(batch)

                    logger.info("Sincronizados %d registros", len(batch))
                    return {'synced': len(batch)}

        except Exception as e:
            # FIX 2026-02-01: Incrementar retry_count en sync_queue
            self._mark_queue_items_failed(batch, str(e))

            # Re-encolar los fallidos (solo en RAM, ya están en BD)
            for item in batch:
                self.sync_queue.put(item)

            logger.error("Error de sync: %s", e)
            return {'error': str(e)}
        
        return {'synced': 0}
    
    def get_unsynced_sales(self, limit: int = 100) -> List[Dict]:
        """Obtiene ventas no sincronizadas de la BD."""
        # Validar límite para evitar DoS
        limit = max(1, min(int(limit), 1000))
        sql = """
            SELECT id, branch_id, pos_id, serie, folio_visible, total,
                   customer_id, payment_method, timestamp
            FROM sales
            WHERE synced = 0 OR synced IS NULL
            ORDER BY timestamp ASC
            LIMIT %s
        """
        return list(self.core.db.execute_query(sql, (limit,)))
    
    def sync_sales_batch(self) -> Dict[str, Any]:
        """Sincroniza un lote de ventas directamente desde la BD."""
        unsynced = self.get_unsynced_sales(self.BATCH_SIZE)
        
        if not unsynced:
            return {'synced': 0, 'message': 'No pending sales'}
        
        # Preparar payload
        payload_data = {
            'type': 'sales_batch',
            'branch_id': self.branch_id,
            'pos_id': self.pos_id,
            'timestamp': datetime.now().isoformat(),
            'records': unsynced
        }
        
        # Cifrar y enviar
        encrypted = self._encrypt_payload(payload_data)
        
        # Por ahora, simular envío exitoso
        logger.info("Prepared batch of %d sales (%d bytes)", len(unsynced), len(encrypted))
        
        return {
            'prepared': len(unsynced),
            'payload_size': len(encrypted),
            'encrypted': True
        }
    
    def _encrypt_payload(self, data: Any) -> bytes:
        """Cifra el payload con AES-256."""
        json_data = json.dumps(data, default=str)
        compressed = gzip.compress(json_data.encode())
        
        if HAS_CRYPTO and self.encryption_key:
            # AES-256-GCM with cryptographically secure random IV
            # SECURITY: NEVER use predictable IVs (like time-based) for GCM mode
            # Using same IV twice with same key completely breaks GCM security
            iv = os.urandom(16)  # SECURITY: Cryptographically secure random IV
            cipher = Cipher(
                algorithms.AES(self.encryption_key[:32]),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(compressed) + encryptor.finalize()

            # IV + Tag + Ciphertext
            return iv + encryptor.tag + ciphertext
        else:
            # SECURITY: Encryption key is REQUIRED - no fallback to weak crypto
            raise ValueError(
                "SECURITY ERROR: Encryption key is required for sync operations. "
                "Configure encryption_key via configure() before syncing. "
                "XOR fallback has been removed as it provides no real security."
            )
    
    def _decrypt_payload(self, encrypted: bytes) -> Any:
        """Descifra el payload."""
        if HAS_CRYPTO and self.encryption_key:
            iv = encrypted[:16]
            tag = encrypted[16:32]
            ciphertext = encrypted[32:]
            
            cipher = Cipher(
                algorithms.AES(self.encryption_key[:32]),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            compressed = decryptor.update(ciphertext) + decryptor.finalize()
        else:
            # SECURITY: Encryption key is REQUIRED - no fallback to weak crypto
            raise ValueError(
                "SECURITY ERROR: Cannot decrypt without proper encryption key. "
                "XOR fallback has been removed as it provides no real security."
            )
        
        json_data = gzip.decompress(compressed).decode()
        return json.loads(json_data)
    
    def _mark_synced(self, sale_ids: List[int]):
        """Marca ventas como sincronizadas."""
        if not sale_ids:
            return

        placeholders = ','.join(['%s'] * len(sale_ids))
        self.core.db.execute_write(
            f"UPDATE sales SET synced = 1 WHERE id IN ({placeholders})",
            tuple(sale_ids)
        )

    def _mark_queue_items_synced(self, batch: List[Dict]):
        """FIX 2026-02-01: Marca items de sync_queue como sincronizados."""
        db_ids = [item.get('db_id') for item in batch if item.get('db_id')]
        if not db_ids:
            return
        try:
            placeholders = ','.join(['%s'] * len(db_ids))
            self.core.db.execute_write(
                f"""UPDATE sync_queue
                    SET synced = TRUE, processed_at = NOW()
                    WHERE id IN ({placeholders})""",
                tuple(db_ids)
            )
        except Exception as e:
            logger.debug("Could not mark sync_queue items as synced: %s", e)

    def _mark_queue_items_failed(self, batch: List[Dict], error: str):
        """FIX 2026-02-01: Incrementa retry_count y registra error en sync_queue."""
        db_ids = [item.get('db_id') for item in batch if item.get('db_id')]
        if not db_ids:
            return
        try:
            placeholders = ','.join(['%s'] * len(db_ids))
            self.core.db.execute_write(
                f"""UPDATE sync_queue
                    SET retry_count = retry_count + 1,
                        last_error = %s
                    WHERE id IN ({placeholders})""",
                (error[:500],) + tuple(db_ids)
            )
        except Exception as e:
            logger.debug("Could not update sync_queue retry count: %s", e)

    def receive_from_central(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Recibe y procesa datos del servidor central."""
        try:
            data = self._decrypt_payload(encrypted_data)
            
            # Procesar según tipo
            if data.get('type') == 'price_update':
                return self._apply_price_updates(data['updates'])
            elif data.get('type') == 'inventory_transfer':
                return self._apply_transfer(data)
            elif data.get('type') == 'config_update':
                return self._apply_config(data)
            
            return {'processed': True}
            
        except Exception as e:
            logger.error("Error procesando datos centrales: %s", e)
            return {'error': str(e)}
    
    def _apply_price_updates(self, updates: List[Dict]) -> Dict:
        """Aplica actualizaciones de precio del central usando transacción atómica."""
        updated = 0

        # SECURITY: Pre-validate all updates before starting transaction
        # FIX 2026-02-04: Use FOR UPDATE to prevent race conditions during validation
        valid_updates = []
        for u in updates:
            if not u.get('sku') or not u.get('price') or not u.get('timestamp'):
                logger.warning("Skipping invalid price update: missing required fields")
                continue

            # Verificar timestamp para conflictos con FOR UPDATE para evitar race conditions
            local = list(self.core.db.execute_query(
                "SELECT price, updated_at FROM products WHERE sku = %s FOR UPDATE",
                (u['sku'],)
            ))

            if local:
                local_time = local[0].get('updated_at', '1970-01-01')
                if u['timestamp'] > str(local_time):
                    valid_updates.append(u)

        if not valid_updates:
            return {'updated': 0}

        # Execute all updates in a single atomic transaction
        # FIX 2026-02-04: Set synced = 1 after applying central update to prevent infinite sync loop
        # (central update should not trigger re-sync back to central)
        operations = [
            (
                "UPDATE products SET price = %s, updated_at = %s, synced = 1 WHERE sku = %s",
                (u['price'], u['timestamp'], u['sku'])
            )
            for u in valid_updates
        ]

        try:
            result = self.core.db.execute_transaction(operations)
            updated = len(valid_updates)
            logger.info("Applied %d price updates atomically", updated)
        except Exception as e:
            logger.error("Failed to apply price updates: %s", e)
            return {'error': str(e), 'updated': 0}

        return {'updated': updated}
    
    def _apply_transfer(self, data: Dict) -> Dict:
        """Aplica transferencia de inventario usando transacción atómica."""
        # Solo procesar si somos el destino
        if data.get('to_branch') != self.branch_id:
            return {'skipped': 'not destination'}

        items = data.get('items', [])
        if not items:
            return {'received': 0}

        # SECURITY: Validate all items before transaction
        valid_items = []
        for item in items:
            if not item.get('sku') or item.get('quantity') is None:
                logger.warning("Skipping invalid transfer item: missing sku or quantity")
                continue
            # SECURITY: Prevent negative quantities (inventory theft via negative transfer)
            if item['quantity'] < 0:
                logger.warning("Skipping negative quantity transfer for %s", item.get('sku'))
                continue
            valid_items.append(item)

        if not valid_items:
            return {'received': 0, 'skipped': 'no valid items'}

        # Execute all inventory updates + movements in a single atomic transaction (Parte A Fase 1)
        operations = []
        for item in valid_items:
            qty = item['quantity']
            sku = item['sku']
            operations.append((
                "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE sku = %s",
                (qty, sku)
            ))
            # Registrar movimiento para delta sync (reference_type='transfer')
            operations.append((
                """INSERT INTO inventory_movements
                (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                VALUES ((SELECT id FROM products WHERE sku = %s LIMIT 1), 'IN', 'transfer', %s, %s, 'transfer', NOW(), 0)""",
                (sku, qty, f"Transferencia SKU:{sku}")
            ))

        try:
            result = self.core.db.execute_transaction(operations)
            logger.info("Applied %d inventory transfers atomically", len(valid_items))
            return {'received': len(valid_items)}
        except Exception as e:
            logger.error("Failed to apply inventory transfer: %s", e)
            return {'error': str(e), 'received': 0}
    
    def _apply_config(self, data: Dict) -> Dict:
        """Aplica cambios de configuración."""
        # Implementar según necesidades
        return {'applied': True}
    
    def get_synced(self) -> Dict[str, Any]:
        """Retorna el estado actual de sincronización."""
        return {
            'node_id': self.node_id,
            'branch_id': self.branch_id,
            'pos_id': self.pos_id,
            'pending_count': self.pending_count,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'sync_active': self.sync_active,
            'central_configured': self.central_url is not None
        }

class BranchNode:
    """
    Nodo de sucursal - Puede ser maestro o esclavo.
    """
    
    def __init__(self, core, branch_id: int, is_master: bool = False):
        self.core = core
        self.branch_id = branch_id
        self.is_master = is_master
        self.connected_slaves: List[str] = []
        self.sync_engine = GhostSyncEngine(core, branch_id)
    
    def register_slave(self, slave_id: str, slave_ip: str):
        """Registra un nodo esclavo (solo para maestros)."""
        if not self.is_master:
            raise ValueError("Solo nodos maestros pueden registrar esclavos")
        
        self.connected_slaves.append({
            'id': slave_id,
            'ip': slave_ip,
            'registered_at': datetime.now().isoformat()
        })
    
    def get_branch_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de la sucursal."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Ventas de hoy
        sales = list(self.core.db.execute_query(
            """SELECT serie, COUNT(*) as count, COALESCE(SUM(total), 0) as total
               FROM sales WHERE timestamp::date = %s AND branch_id = %s
               GROUP BY serie""",
            (today, self.branch_id)
        ))
        
        # Efectivo en caja
        cash = list(self.core.db.execute_query(
            """SELECT COALESCE(SUM(CASE WHEN type='IN' THEN amount ELSE -amount END), 0) as balance
               FROM cash_movements WHERE timestamp::date = %s AND branch_id = %s""",
            (today, self.branch_id)
        ))
        
        return {
            'branch_id': self.branch_id,
            'is_master': self.is_master,
            'slaves_connected': len(self.connected_slaves),
            'sales_today': sales,
            'cash_balance': float(cash[0]['balance']) if cash else 0,
            'synced': self.sync_engine.get_synced()
        }

# Función para inicializar la sincronización
def init_sync(core, branch_id: int = 1, pos_id: int = 1) -> GhostSyncEngine:
    """Inicializa el motor de sincronización."""
    engine = GhostSyncEngine(core, branch_id, pos_id)
    return engine

# Alias para compatibilidad
SyncEngine = GhostSyncEngine
