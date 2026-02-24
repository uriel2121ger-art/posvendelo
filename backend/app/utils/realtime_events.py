"""
Real-Time Events - Sistema de eventos en tiempo real para TITAN POS
Permite emitir y escuchar eventos entre POS y PWA vía HTTP/WebSocket
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
import queue
import threading

from PyQt6.QtCore import QMetaObject, Qt, QThread
from PyQt6.QtWidgets import QApplication
import requests

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Tipos de eventos soportados."""
    SALE_COMPLETED = "sale_completed"
    SALE_CANCELLED = "sale_cancelled"
    TURN_OPENED = "turn_opened"
    TURN_CLOSED = "turn_closed"
    STOCK_LOW = "stock_low"
    STOCK_OUT = "stock_out"
    PRICE_CHANGED = "price_changed"
    DRAWER_OPENED = "drawer_opened"
    NOTIFICATION = "notification"
    COMMAND_RECEIVED = "command_received"

@dataclass
class Event:
    """Representa un evento del sistema."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: str = None
    source: str = "pos"
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source
        }

class EventEmitter:
    """
    Emisor de eventos - Envía eventos al servidor WebSocket y/o API.
    Funciona de forma asíncrona para no bloquear la UI.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, ws_url: str = None, api_url: str = None):
        if hasattr(self, '_initialized'):
            return
        
        # Auto-detectar URLs si no se proporcionan
        if ws_url is None or api_url is None:
            try:
                from app.utils.network_defaults import get_api_url, get_websocket_url
                ws_url = ws_url or get_websocket_url(use_local=True)
                api_url = api_url or get_api_url(use_local=True)
            except ImportError:
                # Fallback si network_defaults no existe
                from app.utils.network_defaults import DEFAULTS
                ws_url = ws_url or f"http://localhost:{DEFAULTS['websocket_port']}"
                api_url = api_url or f"http://localhost:{DEFAULTS['api_port']}"
        
        self.ws_url = ws_url
        self.api_url = api_url
        self.enabled = True
        self.event_queue = queue.Queue()
        self._listeners: Dict[EventType, List[Callable]] = {}
        self._lock = threading.RLock()
        self._worker_thread = None
        self._running = False

        self._initialized = True
        self._start_worker()
    
    def _start_worker(self):
        """Inicia el worker thread para enviar eventos."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("🚀 EventEmitter worker started")
    
    def _worker_loop(self):
        """Loop del worker que procesa la cola de eventos."""
        while self._running:
            try:
                event = self.event_queue.get(timeout=1)
                self._send_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in event worker: {e}")
    
    def _send_event(self, event: Event):
        """Envía un evento al servidor."""
        try:
            # Intentar enviar al WebSocket server vía HTTP
            response = requests.post(
                f"{self.ws_url}/broadcast",
                json=event.to_dict(),
                timeout=2
            )
            # FIX 2026-02-01: Validar response status code explícitamente
            if response.status_code == 200:
                logger.info(f"Event sent: {event.event_type.value}")
            elif response.ok:
                logger.debug(f"Event sent with status {response.status_code}: {event.event_type.value}")
            else:
                logger.warning(f"Broadcast failed: {response.status_code} - {event.event_type.value}")
        except requests.exceptions.ConnectionError:
            # El servidor WS no está disponible, intentar el API normal
            try:
                requests.post(
                    f"{self.api_url}/api/events/broadcast",
                    json=event.to_dict(),
                    timeout=2
                )
            except Exception:
                pass  # Silently fail if no server available
        except Exception as e:
            logger.debug(f"Could not send event: {e}")
    
    def emit(self, event_type: EventType, data: Dict[str, Any], source: str = "pos"):
        """
        Emite un evento de forma asíncrona.
        
        Args:
            event_type: Tipo de evento
            data: Datos del evento
            source: Origen del evento (pos, pwa, api)
        """
        if not self.enabled:
            return
        
        event = Event(event_type=event_type, data=data, source=source)
        self.event_queue.put(event)
        
        # También notificar a listeners locales
        self._notify_listeners(event)
    
    def _notify_listeners(self, event: Event):
        """Notify listeners, ensuring UI updates happen on main thread."""
        with self._lock:
            listeners_copy = list(self._listeners.get(event.event_type, []))

        app = QApplication.instance()
        is_main_thread = app is not None and QThread.currentThread() == app.thread()

        for callback in listeners_copy:
            try:
                if is_main_thread:
                    callback(event)
                elif app is not None:
                    QMetaObject.invokeMethod(
                        app,
                        lambda cb=callback, ev=event: cb(ev),
                        Qt.ConnectionType.QueuedConnection
                    )
            except Exception as e:
                logger.error(f"Error in event listener: {e}")
    
    def on(self, event_type: EventType, callback: Callable):
        """Registra un listener para un tipo de evento."""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)
    
    def off(self, event_type: EventType, callback: Callable):
        """Elimina un listener."""
        with self._lock:
            if event_type in self._listeners:
                self._listeners[event_type] = [
                    listener for listener in self._listeners[event_type]
                    if listener != callback
                ]
    
    def stop(self):
        """Detiene el worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

# Singleton global (thread-safe)
_emitter: Optional[EventEmitter] = None
_emitter_lock = threading.Lock()


def get_emitter() -> EventEmitter:
    """Obtiene la instancia global del emisor de eventos. Thread-safe."""
    global _emitter
    if _emitter is None:
        with _emitter_lock:
            # Double-check after acquiring lock
            if _emitter is None:
                _emitter = EventEmitter()
    return _emitter

# =============================================================================
# FUNCIONES DE CONVENIENCIA
# =============================================================================

def emit_sale_completed(sale_id: int, total: float, items_count: int, 
                         payment_method: str, folio: str = None):
    """Emite evento de venta completada."""
    get_emitter().emit(EventType.SALE_COMPLETED, {
        "sale_id": sale_id,
        "total": total,
        "items_count": items_count,
        "payment_method": payment_method,
        "folio": folio or f"#{sale_id}"
    })

def emit_sale_cancelled(sale_id: int, total: float, reason: str = None):
    """Emite evento de venta cancelada."""
    get_emitter().emit(EventType.SALE_CANCELLED, {
        "sale_id": sale_id,
        "total": total,
        "reason": reason
    })

def emit_turn_opened(turn_id: int, user_name: str, initial_cash: float):
    """Emite evento de turno abierto."""
    get_emitter().emit(EventType.TURN_OPENED, {
        "turn_id": turn_id,
        "user": user_name,
        "initial_cash": initial_cash
    })

def emit_turn_closed(turn_id: int, user_name: str, expected_cash: float, actual_cash: float):
    """Emite evento de turno cerrado."""
    get_emitter().emit(EventType.TURN_CLOSED, {
        "turn_id": turn_id,
        "user": user_name,
        "expected_cash": expected_cash,
        "actual_cash": actual_cash,
        "difference": actual_cash - expected_cash
    })

def emit_stock_low(product_id: int, product_name: str, current_stock: float, min_stock: float):
    """Emite alerta de stock bajo."""
    get_emitter().emit(EventType.STOCK_LOW, {
        "product_id": product_id,
        "product_name": product_name,
        "current_stock": current_stock,
        "min_stock": min_stock,
        "urgency": "critical" if current_stock <= 2 else "warning"
    })

def emit_drawer_opened(source: str = "manual"):
    """Emite evento de cajón abierto."""
    get_emitter().emit(EventType.DRAWER_OPENED, {
        "source": source
    })

def emit_notification(title: str, message: str, priority: str = "normal"):
    """Emite una notificación."""
    get_emitter().emit(EventType.NOTIFICATION, {
        "title": title,
        "message": message,
        "priority": priority
    })
