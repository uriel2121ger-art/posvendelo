"""
Sistema POS Optimizado con Locks y Cola de Impresión
Garantiza thread-safety y tickets rápidos (<20 segundos)
"""
import threading
import queue
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SaleItem:
    """Item de venta thread-safe"""
    product_id: int
    sku: str
    name: str
    qty: float
    price: float
    base_price: float
    discount: float = 0.0
    is_wholesale: bool = False
    sale_type: str = "unit"
    kit_items: List[Dict] = field(default_factory=list)


@dataclass
class Sale:
    """Venta completada"""
    sale_id: int
    folio: str
    total: float
    subtotal: float
    tax: float
    discount: float
    items: List[SaleItem]
    payment_method: str
    cashier: str
    timestamp: datetime = field(default_factory=datetime.now)


class ResourceLocks:
    """Locks para recursos compartidos"""
    def __init__(self):
        self.printer = threading.Lock()  # Lock para impresora
        self.drawer = threading.Lock()  # Lock para cajón
        self.cart = threading.RLock()  # Reentrant lock para carrito


class PrintQueue:
    """Cola de impresión thread-safe"""
    def __init__(self):
        self.queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stats = {
            'total_printed': 0,
            'total_errors': 0,
            'queue_size': 0
        }
        self._running = False
        self._lock = threading.Lock()
    
    def start_worker(self, print_callback):
        """Iniciar worker thread de impresión"""
        if self._running:
            return
        
        self._running = True
        self._print_callback = print_callback
        
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="Print-Queue-Worker"
        )
        self.worker_thread.start()
        logger.info("🖨️ Cola de impresión iniciada")
    
    def stop_worker(self):
        """Detener worker thread"""
        self._running = False
        if self.worker_thread:
            self.queue.put(None)  # Señal de parada
            self.worker_thread.join(timeout=5)
        logger.info("🛑 Cola de impresión detenida")
    
    def add_print_job(self, sale: Sale, full_ticket: bool = True):
        """Agregar trabajo de impresión a la cola"""
        with self._lock:
            self.stats['queue_size'] = self.queue.qsize() + 1
        
        self.queue.put({
            'sale': sale,
            'full_ticket': full_ticket,
            'timestamp': time.time()
        })
        logger.info(f"📄 Trabajo de impresión agregado a cola: Sale #{sale.sale_id}")
    
    def _worker_loop(self):
        """Loop del worker que procesa la cola"""
        while self._running:
            try:
                # Obtener trabajo de la cola (timeout para poder verificar _running)
                try:
                    job = self.queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                if job is None:  # Señal de parada
                    break
                
                sale = job['sale']
                full_ticket = job['full_ticket']
                
                try:
                    # Imprimir usando callback
                    self._print_callback(sale, full_ticket)
                    
                    with self._lock:
                        self.stats['total_printed'] += 1
                        self.stats['queue_size'] = max(0, self.stats['queue_size'] - 1)
                    
                    logger.info(f"✅ Ticket impreso: Sale #{sale.sale_id}")
                    
                except Exception as e:
                    with self._lock:
                        self.stats['total_errors'] += 1
                        self.stats['queue_size'] = max(0, self.stats['queue_size'] - 1)
                    
                    logger.error(f"❌ Error imprimiendo Sale #{sale.sale_id}: {e}")
                
                finally:
                    self.queue.task_done()
                    
            except Exception as e:
                logger.error(f"Error en worker de impresión: {e}")
                time.sleep(1)
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas de la cola"""
        with self._lock:
            total = self.stats['total_printed'] + self.stats['total_errors']
            success_rate = (self.stats['total_printed'] / total) if total > 0 else 0.0
            
            return {
                'queue_size': self.queue.qsize(),
                'total_printed': self.stats['total_printed'],
                'total_errors': self.stats['total_errors'],
                'success_rate': success_rate
            }


class OptimizedPOSSystem:
    """
    Sistema POS optimizado con:
    - Locks para recursos compartidos
    - Cola de impresión ordenada
    - Comprobante temporal rápido (<20 seg)
    - Ticket completo en background
    """
    
    def __init__(self, print_callback=None, drawer_callback=None):
        """
        Inicializar sistema optimizado
        
        Args:
            print_callback: Función para imprimir tickets (sale, full_ticket) -> None
            drawer_callback: Función para abrir cajón () -> None
        """
        self.locks = ResourceLocks()
        self.cart: List[SaleItem] = []
        self.print_queue = PrintQueue()
        
        # Callbacks
        self._print_callback = print_callback
        self._drawer_callback = drawer_callback
        
        # Iniciar worker de impresión si hay callback
        if print_callback:
            self.print_queue.start_worker(print_callback)
        
        logger.info("🚀 Sistema POS Optimizado inicializado")
    
    # =========================================
    # MÉTODOS DEL CARRITO (Thread-Safe)
    # =========================================
    
    def add_item(self, item: SaleItem) -> None:
        """Agregar item al carrito (thread-safe)"""
        with self.locks.cart:
            # Verificar si ya existe
            existing = None
            for existing_item in self.cart:
                if (existing_item.product_id == item.product_id and 
                    existing_item.sale_type == item.sale_type):
                    existing = existing_item
                    break
            
            if existing:
                existing.qty += item.qty
                logger.debug(f"Item existente actualizado: {existing.name} x{existing.qty}")
            else:
                self.cart.append(item)
                logger.debug(f"Item agregado: {item.name} x{item.qty}")
    
    def remove_item(self, index: int) -> None:
        """Remover item del carrito (thread-safe)"""
        with self.locks.cart:
            if 0 <= index < len(self.cart):
                item = self.cart.pop(index)
                logger.debug(f"Item removido: {item.name}")
    
    def update_quantity(self, index: int, qty: float) -> None:
        """Actualizar cantidad de item (thread-safe)"""
        with self.locks.cart:
            if 0 <= index < len(self.cart):
                self.cart[index].qty = qty
                logger.debug(f"Cantidad actualizada: {self.cart[index].name} x{qty}")
    
    def get_cart_copy(self) -> List[SaleItem]:
        """Obtener copia segura del carrito (thread-safe)"""
        with self.locks.cart:
            return [SaleItem(**item.__dict__) for item in self.cart]
    
    def clear_cart(self) -> None:
        """Limpiar carrito (thread-safe)"""
        with self.locks.cart:
            self.cart.clear()
            logger.debug("Carrito limpiado")
    
    def get_cart_size(self) -> int:
        """Obtener tamaño del carrito (thread-safe)"""
        with self.locks.cart:
            return len(self.cart)
    
    # =========================================
    # FINALIZAR VENTA (Optimizado)
    # =========================================
    
    def finalize_sale(
        self,
        sale_id: int,
        folio: str,
        payment_method: str,
        cashier: str,
        tax_rate: float = 0.16
    ) -> Sale:
        """
        Finalizar venta con comprobante temporal rápido (<20 segundos)
        
        Returns:
            Sale: Objeto de venta completada
        """
        # Obtener copia del carrito
        items = self.get_cart_copy()
        
        if not items:
            raise ValueError("No hay items en el carrito")
        
        # Calcular totales
        subtotal = sum(item.qty * item.price - item.discount for item in items)
        tax = subtotal * tax_rate
        discount = sum(item.discount for item in items)
        total = subtotal + tax - discount
        
        # Crear objeto Sale
        sale = Sale(
            sale_id=sale_id,
            folio=folio,
            total=total,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            items=items,
            payment_method=payment_method,
            cashier=cashier
        )
        
        # IMPRIMIR TICKET COMPLETO (agregado a cola)
        # Este se imprime en background sin bloquear
        if self._print_callback:
            import json
            import os
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.cursor', 'debug.log')
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': time.time() * 1000,
                        'location': 'pos_optimized.py:286',
                        'message': 'Ticket agregado a cola de impresión',
                        'data': {
                            'sale_id': sale_id,
                            'folio': folio,
                            'items_count': len(items),
                            'total': total,
                            'queue_size_before': self.print_queue._queue.qsize()
                        },
                        'sessionId': 'debug-session',
                        'runId': 'test-run',
                        'hypothesisId': 'A'
                    }, f, ensure_ascii=False)
                    f.write('\n')
            except Exception:
                pass
            self.print_queue.add_print_job(sale, full_ticket=True)
            logger.info(f"📋 Ticket agregado a cola: Sale #{sale_id}")
        
        # 3. ABRIR CAJÓN (con lock, en background)
        if self._drawer_callback:
            def open_drawer_safe():
                import json
                import os
                log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.cursor', 'debug.log')
                drawer_start = time.time()
                try:
                    with self.locks.drawer:
                        logger.info("💵 Abriendo cajón de dinero")
                        try:
                            with open(log_path, 'a', encoding='utf-8') as f:
                                json.dump({
                                    'timestamp': drawer_start * 1000,
                                    'location': 'pos_optimized.py:293',
                                    'message': 'Iniciando apertura de cajón',
                                    'data': {'sale_id': sale_id},
                                    'sessionId': 'debug-session',
                                    'runId': 'test-run',
                                    'hypothesisId': 'B'
                                }, f, ensure_ascii=False)
                                f.write('\n')
                        except Exception:
                            pass
                        self._drawer_callback()
                        drawer_elapsed = time.time() - drawer_start
                        try:
                            with open(log_path, 'a', encoding='utf-8') as f:
                                json.dump({
                                    'timestamp': time.time() * 1000,
                                    'location': 'pos_optimized.py:296',
                                    'message': 'Cajón abierto exitosamente',
                                    'data': {'sale_id': sale_id, 'elapsed_ms': drawer_elapsed * 1000},
                                    'sessionId': 'debug-session',
                                    'runId': 'test-run',
                                    'hypothesisId': 'B'
                                }, f, ensure_ascii=False)
                                f.write('\n')
                        except Exception:
                            pass
                        time.sleep(0.5)  # Esperar apertura mecánica
                except Exception as e:
                    logger.error(f"❌ Error abriendo cajón: {e}")
                    try:
                        with open(log_path, 'a', encoding='utf-8') as f:
                            json.dump({
                                'timestamp': time.time() * 1000,
                                'location': 'pos_optimized.py:298',
                                'message': 'Error abriendo cajón',
                                'data': {'sale_id': sale_id, 'error': str(e)},
                                'sessionId': 'debug-session',
                                'runId': 'test-run',
                                'hypothesisId': 'B'
                            }, f, ensure_ascii=False)
                            f.write('\n')
                    except Exception:
                        pass
            
            # Abrir cajón en thread separado para no bloquear
            drawer_thread = threading.Thread(target=open_drawer_safe, daemon=True, name="CashDrawer-Open")
            drawer_thread.start()
        
        # 4. LIMPIAR CARRITO
        self.clear_cart()
        
        return sale
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas del sistema"""
        return {
            'cart_items': self.get_cart_size(),
            'print_queue': self.print_queue.get_stats()
        }
    
    def shutdown(self):
        """Cerrar sistema (detener worker)"""
        self.print_queue.stop_worker()
        logger.info("🛑 Sistema POS Optimizado cerrado")
