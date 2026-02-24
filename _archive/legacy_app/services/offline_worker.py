"""
Offline Worker - Sistema de resiliencia para timbrado en cola
Mantiene operación continua incluso sin conexión a internet
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import logging
from pathlib import Path
import threading
import time

logger = logging.getLogger(__name__)

class OfflineWorker:
    """
    Worker de background para sincronización offline-first.
    Garantiza que las facturas se timbren aunque no haya internet.
    """
    
    def __init__(self, core):
        self.core = core
        self._running = False
        self._thread = None
        self._sync_interval = 300  # 5 minutos
        self._setup_pending_table()
    
    def _setup_pending_table(self):
        """Crea tabla de facturas pendientes si no existe."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS pending_invoices (
                    id BIGSERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL,
                    customer_email TEXT,
                    invoice_json TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    last_attempt TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    stamped_at TEXT,
                    uuid TEXT,
                    error_message TEXT
                )
            """)
            
            # Índices para búsqueda rápida
            self.core.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_invoices(status)"
            )
        except Exception as e:
            logger.error(f"Error creating pending_invoices table: {e}")
    
    def queue_invoice(self, sale_id: int, invoice_data: Dict, 
                      customer_email: str = None) -> Dict[str, Any]:
        """
        Encola una factura para timbrado posterior.
        Retorna ticket provisional para el cliente.
        """
        try:
            invoice_json = json.dumps(invoice_data, default=str)
            
            self.core.db.execute_write(
                """INSERT INTO pending_invoices 
                   (sale_id, customer_email, invoice_json, status, created_at)
                   VALUES (%s, %s, %s, 'pending', %s)""",
                (sale_id, customer_email, invoice_json, datetime.now().isoformat())
            )
            
            # Get queue position
            result = list(self.core.db.execute_query(
                "SELECT COUNT(*) as pos FROM pending_invoices WHERE status = 'pending'"
            ))
            # FIX 2026-01-30: Validar que result no esté vacío antes de acceder a [0]
            queue_pos = result[0]['pos'] if result else 0
            
            logger.info(f"📋 Factura encolada: venta #{sale_id}, posición {queue_pos}")
            
            return {
                'success': True,
                'queued': True,
                'sale_id': sale_id,
                'queue_position': queue_pos,
                'message': 'Factura en proceso de timbrado',
                'customer_message': (
                    'Su factura está siendo procesada. '
                    'Recibirá el comprobante en su correo en breve.'
                )
            }
            
        except Exception as e:
            logger.error(f"Error queuing invoice: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_pending_count(self) -> int:
        """Retorna cantidad de facturas pendientes."""
        result = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM pending_invoices WHERE status = 'pending'"
        ))
        return result[0]['c'] if result else 0
    
    def get_pending_invoices(self, limit: int = 10) -> List[Dict]:
        """Obtiene facturas pendientes ordenadas por antigüedad."""
        # Validar límite para evitar DoS
        limit = max(1, min(int(limit), 100))
        result = list(self.core.db.execute_query(
            """SELECT * FROM pending_invoices 
               WHERE status = 'pending' 
               ORDER BY created_at ASC 
               LIMIT %s""",
            (limit,)
        ))
        return [dict(r) for r in result]
    
    def check_internet(self) -> bool:
        """Verifica conectividad a internet."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False
    
    def process_pending(self, invoice: Dict) -> Dict[str, Any]:
        """
        Procesa una factura pendiente.
        Intenta timbrar con el PAC.
        """
        try:
            invoice_data = json.loads(invoice['invoice_json'])
            
            # Incrementar intentos
            self.core.db.execute_write(
                """UPDATE pending_invoices 
                   SET attempts = attempts + 1, last_attempt = %s
                   WHERE id = %s""",
                (datetime.now().isoformat(), invoice['id'])
            )
            
            # Intentar timbrar
            from app.fiscal.pac_connector import PACConnector
            pac = PACConnector(self.core)
            
            result = pac.stamp(invoice_data)
            
            if result.get('success'):
                # Actualizar como timbrado
                self.core.db.execute_write(
                    """UPDATE pending_invoices 
                       SET status = 'stamped', stamped_at = %s, uuid = %s
                       WHERE id = %s""",
                    (datetime.now().isoformat(), result.get('uuid'), invoice['id'])
                )
                
                # Enviar email si hay correo
                if invoice.get('customer_email'):
                    self._send_invoice_email(
                        invoice['customer_email'],
                        result
                    )
                
                logger.info(f"✅ Factura #{invoice['sale_id']} timbrada: {result.get('uuid')}")
                return {'success': True, 'uuid': result.get('uuid')}
            else:
                # Registrar error
                self.core.db.execute_write(
                    """UPDATE pending_invoices 
                       SET error_message = %s
                       WHERE id = %s""",
                    (result.get('error', 'Error desconocido'), invoice['id'])
                )
                
                # Marcar como fallido después de 5 intentos
                if invoice['attempts'] >= 4:
                    self.core.db.execute_write(
                        "UPDATE pending_invoices SET status = 'failed' WHERE id = %s",
                        (invoice['id'],)
                    )
                
                return {'success': False, 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"Error processing invoice: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_invoice_email(self, email: str, stamp_result: Dict):
        """Envía factura por email al cliente.

        TODO [MEDIUM]: Implementar envío de email con:
        - Plantilla HTML profesional
        - Adjuntar PDF y XML de la factura
        - Configuración SMTP desde ajustes de la tienda
        - Manejo de errores y reintentos

        Args:
            email: Correo electrónico del destinatario
            stamp_result: Resultado del timbrado con UUID, PDF y XML
        """
        logger.warning(
            f"_send_invoice_email no implementado - email pendiente a {email} "
            f"para UUID {stamp_result.get('uuid', 'N/A')}"
        )
    
    def sync_now(self) -> Dict[str, Any]:
        """Sincroniza todas las facturas pendientes ahora."""
        if not self.check_internet():
            return {'success': False, 'error': 'Sin conexión a internet'}
        
        pending = self.get_pending_invoices(limit=10)
        
        if not pending:
            return {'success': True, 'processed': 0, 'message': 'Sin pendientes'}
        
        processed = 0
        errors = 0
        
        for invoice in pending:
            result = self.process_pending(invoice)
            if result.get('success'):
                processed += 1
            else:
                errors += 1
        
        return {
            'success': True,
            'processed': processed,
            'errors': errors,
            'remaining': self.get_pending_count()
        }
    
    # ==========================================
    # BACKGROUND DAEMON
    # ==========================================
    
    def start_daemon(self):
        """Inicia el daemon de sincronización en background."""
        if self._running:
            logger.warning("Daemon ya está corriendo")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._daemon_loop, daemon=True)
        self._thread.start()
        logger.info("🔄 Daemon de sincronización iniciado")
    
    def stop_daemon(self):
        """Detiene el daemon de sincronización."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("⏹️ Daemon detenido")
    
    def _daemon_loop(self):
        """Loop principal del daemon."""
        while self._running:
            try:
                if self.check_internet():
                    pending_count = self.get_pending_count()
                    if pending_count > 0:
                        logger.info(f"🔄 Sincronizando {pending_count} facturas pendientes...")
                        result = self.sync_now()
                        logger.info(f"   Procesadas: {result.get('processed')}, Errores: {result.get('errors')}")
                else:
                    logger.debug("Sin conexión, esperando...")
            except Exception as e:
                logger.error(f"Error en daemon: {e}")
            
            # Dormir hasta próxima sincronización
            time.sleep(self._sync_interval)
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna estado del worker."""
        return {
            'running': self._running,
            'internet': self.check_internet(),
            'pending': self.get_pending_count(),
            'sync_interval': self._sync_interval
        }
