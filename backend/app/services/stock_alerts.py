"""
TITAN POS - Stock Alert Service (REFACTORIZADO)

Usa la clase base BackgroundService y decorador @with_retry.
"""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import threading

try:
    import requests
except ImportError:
    requests = None

# Importar utilidades de optimización
try:
    from app.utils.optimization import BackgroundService, with_retry
except ImportError:
    BackgroundService = object
    def with_retry(*args, **kwargs):
        def decorator(f): return f
        return decorator

logger = logging.getLogger(__name__)

@dataclass
class StockAlert:
    """Representa una alerta de stock bajo."""
    sku: str
    name: str
    current_stock: float
    min_stock: float
    shortage: float
    category: Optional[str] = None
    last_sale: Optional[str] = None
    created_at: Optional[str] = None
    severity: str = "warning"

class StockAlertService(BackgroundService):
    """
    Servicio refactorizado de alertas de stock usando BackgroundService.
    """
    
    def __init__(self, pos_core, config: Dict[str, Any]):
        self.core = pos_core
        self.config = config
        
        # Soporta central_url (nuevo) o central_server (legacy)
        self.gateway_url = config.get("central_url", "") or config.get("central_server", "")
        self.terminal_id = config.get("terminal_id", 1)
        self.branch_id = config.get("branch_id", 1)
        self.api_token = config.get("central_token", "") or config.get("api_token", "")
        
        self.critical_threshold = config.get("critical_stock_threshold", 0.25)
        self._callbacks: List[Callable[[List[StockAlert]], None]] = []
        self._callbacks_lock = threading.Lock()
        self._alert_history: Dict[str, datetime] = {}
        self._alert_history_lock = threading.Lock()
        self._cooldown = timedelta(hours=4)
        
        interval = config.get("stock_alert_interval", 300)
        enabled = config.get("stock_alerts_enabled", True)
        
        super().__init__(
            name="StockAlertService",
            interval=interval,
            enabled=enabled,
            max_consecutive_errors=5
        )
    
    def register_callback(self, callback: Callable[[List[StockAlert]], None]):
        """Registrar callback para alertas."""
        with self._callbacks_lock:
            self._callbacks.append(callback)
    
    def check_stock_levels(self) -> List[StockAlert]:
        """Verificar niveles de stock y generar alertas."""
        alerts = []
        
        # INDEX RECOMMENDATION: CREATE INDEX idx_products_stock_alert ON products(is_active, min_stock, stock)
        try:
            rows = self.core.db.execute_query("""
                SELECT
                    sku, name, stock, min_stock, category,
                    (SELECT MAX(created_at) FROM sale_items si
                     JOIN sales s ON si.sale_id = s.id
                     WHERE si.product_id = products.id) as last_sale
                FROM products
                WHERE is_active = 1 AND min_stock > 0 AND stock <= min_stock
                ORDER BY (min_stock - stock) DESC
                LIMIT 1000
            """)
            
            for row in rows:
                sku = row['sku']
                name = row['name']
                stock = row['stock']
                min_stock = row['min_stock']
                category = row['category']
                last_sale = row['last_sale'] if 'last_sale' in row.keys() else None
                
                # Verificar cooldown
                with self._alert_history_lock:
                    last_alert = self._alert_history.get(sku)
                if last_alert and (datetime.now() - last_alert) < self._cooldown:
                    continue
                
                shortage = min_stock - stock
                
                # Determinar severidad
                if stock <= 0:
                    severity = "out_of_stock"
                elif stock <= min_stock * self.critical_threshold:
                    severity = "critical"
                else:
                    severity = "warning"
                
                alert = StockAlert(
                    sku=sku, name=name, current_stock=stock,
                    min_stock=min_stock, shortage=shortage,
                    category=category, last_sale=last_sale,
                    created_at=datetime.now().isoformat(),
                    severity=severity
                )
                
                alerts.append(alert)
                with self._alert_history_lock:
                    self._alert_history[sku] = datetime.now()
                    
        except Exception as e:
            logger.error(f"Error checking stock levels: {e}")
            
        return alerts
    
    @with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    def _send_to_gateway(self, alerts: List[StockAlert]) -> bool:
        """Enviar alertas al gateway con retry."""
        if not requests or not self.gateway_url or not alerts:
            return False
            
        # gateway_url ya incluye protocolo y puerto
        base_url = self.gateway_url.rstrip('/')
        if not base_url.startswith('http'):
            base_url = f"http://{base_url}"
        url = f"{base_url}/api/v1/alerts/stock"
        
        payload = {
            "terminal_id": self.terminal_id,
            "branch_id": self.branch_id,
            "timestamp": datetime.now().isoformat(),
            "alerts": [
                {
                    "sku": a.sku, "name": a.name,
                    "current_stock": a.current_stock,
                    "min_stock": a.min_stock,
                    "severity": a.severity
                }
                for a in alerts
            ]
        }
        
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    
    def _execute(self) -> bool:
        """Ejecutar verificación de stock (llamado por BackgroundService)."""
        alerts = self.check_stock_levels()
        
        if not alerts:
            return True
        
        logger.info(f"📦 {len(alerts)} alertas de stock generadas")
        
        # Ejecutar callbacks locales
        with self._callbacks_lock:
            callbacks_copy = list(self._callbacks)
        for callback in callbacks_copy:
            try:
                callback(alerts)
            except Exception as e:
                logger.error(f"Error en callback de alerta: {e}")
        
        # Enviar al gateway si está configurado
        if self.gateway_url:
            try:
                self._send_to_gateway(alerts)
            except Exception as e:
                logger.debug(f"No se pudo enviar alertas al gateway: {e}")
        
        return True
    
    def _log_alerts(self, alerts: List[StockAlert]):
        """Callback por defecto: loguear alertas."""
        for alert in alerts:
            icon = "🔴" if alert.severity == "out_of_stock" else "🟡" if alert.severity == "critical" else "⚠️"
            logger.warning(
                f"{icon} STOCK [{alert.severity.upper()}]: "
                f"{alert.name} ({alert.sku}) - Stock: {alert.current_stock}/{alert.min_stock}"
            )
    
    def start(self):
        """Iniciar servicio con callback de log por defecto."""
        with self._callbacks_lock:
            has_callbacks = bool(self._callbacks)
        if not has_callbacks:
            self.register_callback(self._log_alerts)
        super().start()
    
    def get_current_alerts(self) -> List[Dict[str, Any]]:
        """Obtener alertas actuales sin callbacks."""
        alerts = self.check_stock_levels()
        return [
            {
                "sku": a.sku, "name": a.name,
                "current_stock": a.current_stock,
                "min_stock": a.min_stock,
                "shortage": a.shortage,
                "severity": a.severity,
                "category": a.category
            }
            for a in alerts
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Obtener resumen de stock."""
        try:
            result_total = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM products WHERE is_active = 1")
            total = result_total[0]['cnt'] if result_total else 0
            
            result_below = self.core.db.execute_query("""
                SELECT COUNT(*) as cnt FROM products 
                WHERE is_active = 1 AND min_stock > 0 AND stock <= min_stock
            """)
            below_min = result_below[0]['cnt'] if result_below else 0
            
            result_out = self.core.db.execute_query("""
                SELECT COUNT(*) as cnt FROM products WHERE is_active = 1 AND stock <= 0
            """)
            out_of_stock = result_out[0]['cnt'] if result_out else 0
            
            return {
                "total_products": total,
                "healthy": total - below_min,
                "below_minimum": below_min,
                "out_of_stock": out_of_stock,
                "timestamp": datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"Error getting stock summary: {e}")
            return {}

def create_stock_alert_service(pos_core, config: Dict[str, Any]) -> Optional[StockAlertService]:
    """Factory function."""
    try:
        return StockAlertService(pos_core, config)
    except Exception as e:
        logger.error(f"Failed to create stock alert service: {e}")
        return None
