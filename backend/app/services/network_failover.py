"""
Network Failover - Resiliencia de red híbrida para Mérida
Fibra principal + Starlink/5G respaldo con sync priorizado
"""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import socket
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

class ConnectionQuality(Enum):
    """Calidad de conexión detectada."""
    EXCELLENT = 'excellent'   # Fibra óptica normal
    GOOD = 'good'             # Fibra con latencia
    DEGRADED = 'degraded'     # Celular/Starlink
    POOR = 'poor'             # Conexión muy lenta
    OFFLINE = 'offline'       # Sin conexión

class NetworkFailover:
    """
    Balanceador de carga y failover de red inteligente.
    
    Características:
    - Monitoreo de calidad de conexión
    - Priorización de sync por tipo (Serie A primero)
    - Cola degradada para conexiones lentas
    - Failover automático a respaldo
    """
    
    # Configuración de umbrales
    LATENCY_EXCELLENT = 50    # ms
    LATENCY_GOOD = 150        # ms
    LATENCY_DEGRADED = 500    # ms
    BANDWIDTH_MIN = 100       # KB/s mínimo para sync completo
    
    # Servidores de prueba
    TEST_HOSTS = [
        ('8.8.8.8', 53),       # Google DNS
        ('1.1.1.1', 53),       # Cloudflare
        ('208.67.222.222', 53) # OpenDNS
    ]
    
    def __init__(self, core=None):
        self.core = core
        self.current_quality = ConnectionQuality.EXCELLENT
        self.last_check = None
        self.failover_active = False

        # Lock for thread-safe queue operations
        self._queue_lock = threading.Lock()

        # Colas de sync priorizadas (protected by _queue_lock)
        self.priority_queue = []    # Serie A - siempre sync
        self.normal_queue = []      # Serie B - sync cuando hay buen internet
        self.deferred_queue = []    # Fotos/pesados - solo fibra

        # Callbacks
        self.on_quality_change: Optional[Callable] = None
        self.on_failover: Optional[Callable] = None

        # Monitoreo en background
        self._monitor_thread = None
        self._running = False
    
    def start_monitoring(self, interval: int = 30):
        """Inicia monitoreo de red en background."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("🌐 Monitoreo de red iniciado")
    
    def stop_monitoring(self):
        """Detiene el monitoreo."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self, interval: int):
        """Loop de monitoreo."""
        while self._running:
            old_quality = self.current_quality
            self.check_connection()
            
            # Notificar cambio de calidad
            if old_quality != self.current_quality and self.on_quality_change:
                self.on_quality_change(old_quality, self.current_quality)
            
            # Procesar colas según calidad
            self._process_queues()
            
            time.sleep(interval)
    
    def check_connection(self) -> ConnectionQuality:
        """Verifica calidad de conexión actual."""
        latencies = []
        
        for host, port in self.TEST_HOSTS:
            latency = self._ping_host(host, port)
            if latency is not None:
                latencies.append(latency)
        
        self.last_check = datetime.now()
        
        if not latencies:
            self.current_quality = ConnectionQuality.OFFLINE
            return self.current_quality
        
        avg_latency = sum(latencies) / len(latencies)
        
        if avg_latency < self.LATENCY_EXCELLENT:
            self.current_quality = ConnectionQuality.EXCELLENT
        elif avg_latency < self.LATENCY_GOOD:
            self.current_quality = ConnectionQuality.GOOD
        elif avg_latency < self.LATENCY_DEGRADED:
            self.current_quality = ConnectionQuality.DEGRADED
        else:
            self.current_quality = ConnectionQuality.POOR
        
        logger.debug(f"📶 Calidad: {self.current_quality.value} ({avg_latency:.0f}ms)")
        
        return self.current_quality
    
    def _ping_host(self, host: str, port: int, timeout: float = 2.0) -> Optional[float]:
        """Mide latencia a un host."""
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return (time.time() - start) * 1000  # ms
        except Exception:
            return None
    
    def queue_sync(self, data_type: str, data: Any, priority: str = 'normal') -> None:
        """
        Encola datos para sincronizacion. Thread-safe.

        priority:
        - 'critical': Serie A, folios fiscales (siempre sync)
        - 'normal': Serie B, ventas internas (sync cuando hay buen internet)
        - 'deferred': Fotos, archivos pesados (solo con fibra)
        """
        item = {
            'type': data_type,
            'data': data,
            'queued_at': datetime.now().isoformat(),
            'attempts': 0
        }

        with self._queue_lock:
            if priority == 'critical':
                self.priority_queue.append(item)
            elif priority == 'deferred':
                self.deferred_queue.append(item)
            else:
                self.normal_queue.append(item)
    
    def queue_serie_a_sale(self, sale_data: Dict):
        """Encola venta Serie A (prioridad crítica)."""
        self.queue_sync('sale_a', sale_data, 'critical')
    
    def queue_serie_b_sale(self, sale_data: Dict):
        """Encola venta Serie B (prioridad normal)."""
        self.queue_sync('sale_b', sale_data, 'normal')
    
    def queue_merma_photo(self, photo_path: str, merma_id: int):
        """Encola foto de merma (diferida - solo fibra)."""
        self.queue_sync('merma_photo', {
            'path': photo_path,
            'merma_id': merma_id
        }, 'deferred')
    
    def _process_queues(self) -> None:
        """Procesa colas segun calidad de conexion. Thread-safe."""
        quality = self.current_quality

        # Siempre procesar cola critica (Serie A)
        if quality != ConnectionQuality.OFFLINE:
            self._process_queue_safe(self.priority_queue, 'critical')

        # Solo procesar normal si hay buen internet
        if quality in [ConnectionQuality.EXCELLENT, ConnectionQuality.GOOD]:
            self._process_queue_safe(self.normal_queue, 'normal')

        # Solo procesar diferidos si hay fibra
        if quality == ConnectionQuality.EXCELLENT:
            self._process_queue_safe(self.deferred_queue, 'deferred')
    
    def _process_queue_safe(self, queue: List, queue_type: str) -> None:
        """Procesa una cola especifica. Thread-safe."""
        max_per_cycle = 10 if queue_type == 'critical' else 5

        # Extract items to process while holding lock
        with self._queue_lock:
            if not queue:
                return
            items_to_process = []
            while queue and len(items_to_process) < max_per_cycle:
                items_to_process.append(queue.pop(0))

        # Process items without holding lock
        processed = 0
        failed_items = []

        for item in items_to_process:
            try:
                success = self._sync_item(item)
                if success:
                    processed += 1
                else:
                    # Re-encolar con incremento de intentos
                    item['attempts'] += 1
                    if item['attempts'] < 5:
                        failed_items.append(item)
            except Exception as e:
                logger.error(f"Error sync {queue_type}: {e}")
                failed_items.append(item)

        # Re-enqueue failed items while holding lock
        if failed_items:
            with self._queue_lock:
                queue.extend(failed_items)

        if processed > 0:
            logger.info(f"Sincronizados {processed} items ({queue_type})")

    def _process_queue(self, queue: List, queue_type: str) -> None:
        """Alias for backwards compatibility."""
        self._process_queue_safe(queue, queue_type)
    
    def _sync_item(self, item: Dict) -> bool:
        """Sincroniza un item individual."""
        # Aquí iría la lógica de sync real
        # Por ahora, simular éxito
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna estado actual del sistema de red. Thread-safe."""
        with self._queue_lock:
            queue_sizes = {
                'critical': len(self.priority_queue),
                'normal': len(self.normal_queue),
                'deferred': len(self.deferred_queue)
            }

        return {
            'quality': self.current_quality.value,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'failover_active': self.failover_active,
            'queues': queue_sizes
        }
    
    def force_sync_all(self) -> Dict[str, int]:
        """Fuerza sincronizacion de todas las colas. Thread-safe."""
        self._process_queue_safe(self.priority_queue, 'critical')
        self._process_queue_safe(self.normal_queue, 'normal')
        self._process_queue_safe(self.deferred_queue, 'deferred')

        with self._queue_lock:
            return {
                'critical_remaining': len(self.priority_queue),
                'normal_remaining': len(self.normal_queue),
                'deferred_remaining': len(self.deferred_queue)
            }
    
    def configure_interfaces(self, primary: str, backup: str) -> Dict:
        """
        Configura interfaces de red principal y respaldo.
        Requiere permisos de root.
        """
        # Nota: Esta configuración requiere scripts de sistema
        config = {
            'primary': primary,     # ej: 'eth0' (fibra)
            'backup': backup,       # ej: 'wlan0' (Starlink/5G)
            'configured_at': datetime.now().isoformat()
        }
        
        logger.info(f"🔧 Interfaces configuradas: {primary} (pri) / {backup} (bak)")
        
        return config

class PrioritySyncEngine:
    """
    Motor de sincronización con prioridades.
    Integra con Ghost-Sync para manejar degradación de red.
    """
    
    def __init__(self, core, failover: NetworkFailover):
        self.core = core
        self.failover = failover
    
    def sync_sale(self, sale_data: Dict):
        """Sincroniza una venta según su serie."""
        serie = sale_data.get('serie', 'B')
        
        if serie == 'A':
            # Serie A siempre es crítica
            self.failover.queue_serie_a_sale(sale_data)
        else:
            # Serie B es normal
            self.failover.queue_serie_b_sale(sale_data)
    
    def get_pending_critical(self) -> int:
        """Retorna cantidad de items críticos pendientes."""
        return len(self.failover.priority_queue)

# Script de configuración de failover con NetworkManager
FAILOVER_SCRIPT = """#!/bin/bash
# Failover automático para Mérida
# Ejecutar con: sudo ./network_failover.sh

PRIMARY="eth0"    # Fibra óptica
BACKUP="wlan0"    # Starlink/5G

check_primary() {
    ping -I $PRIMARY -c 1 -W 2 8.8.8.8 > /dev/null 2>&1
    return $%s
}

while true; do
    if check_primary; then
        # Fibra disponible - usar como default
        ip route replace default via $(ip route show dev $PRIMARY | grep default | awk '{print $3}')
    else
        # Failover a backup
        ip route replace default via $(ip route show dev $BACKUP | grep default | awk '{print $3}')
        echo "[$(date)] FAILOVER ACTIVADO - Usando $BACKUP"
    fi
    sleep 10
done
"""

def install_failover_script():
    """Instala el script de failover."""
    from pathlib import Path
    
    script_path = Path(__file__).resolve().parent.parent.parent / 'scripts/network_failover.sh'
    script_path.write_text(FAILOVER_SCRIPT)
    script_path.chmod(0o755)
    
    return str(script_path)
