from pathlib import Path

"""
Auto-Proxy CFDI - Rotación de IPs para Timbrado
Rompe el vínculo geográfico entre múltiples RFCs
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import json
import logging
import secrets
_rng = secrets.SystemRandom()  # Cryptographically secure random
import sys
import urllib.request

logger = logging.getLogger(__name__)

class CFDIProxyRotator:
    """
    Rotador de Proxies para timbrado CFDI.
    
    El SAT puede detectar que múltiples RFCs timbran desde la misma IP.
    Este módulo rota IPs para cada timbrado, rompiendo el patrón.
    """
    
    # Proveedores de proxy (configurables)
    PROXY_PROVIDERS = {
        'residential': [
            # Proxies residenciales (más caros pero más seguros)
            'http://user:pass@proxy1.example.com:8080',
            'http://user:pass@proxy2.example.com:8080',
        ],
        'datacenter': [
            # Proxies de datacenter (más rápidos)
            'http://user:pass@dc1.example.com:8080',
            'http://user:pass@dc2.example.com:8080',
        ],
        'tor': [
            # Salida por Tor (máxima anonimidad, más lento)
            'socks5://127.0.0.1:9050',
        ]
    }
    
    # Mapeo de RFC a proxy preferido (para consistencia parcial)
    RFC_PROXY_MAP = {}
    
    def __init__(self, core=None):
        self.core = core
        self.current_proxy_index = 0
        self.proxies = []
        self._load_proxies()
    
    def _load_proxies(self):
        """Carga proxies de configuración."""
        if not self.core:
            # Usar proxies de ejemplo en desarrollo
            self.proxies = [
                {'url': None, 'type': 'direct', 'location': 'Mérida'},
            ]
            return
        
        try:
            proxies = list(self.core.db.execute_query(
                "SELECT value FROM config WHERE key = 'cfdi_proxies'"
            ))
            
            if proxies and len(proxies) > 0 and proxies[0] and proxies[0].get('value'):
                self.proxies = json.loads(proxies[0].get('value'))
            else:
                # Configuración por defecto: conexión directa
                self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.debug(f"Using default proxy config: {e}")
            self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]
        except Exception as e:
            logger.warning(f"Error loading proxy config: {e}")
            self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]
    
    def get_proxy_for_rfc(self, rfc: str) -> Dict[str, Any]:
        """
        Obtiene un proxy para un RFC específico.
        
        Estrategia:
        - Rota entre proxies disponibles
        - Intenta no usar el mismo proxy consecutivamente
        - Registra uso para análisis
        """
        if not self.proxies:
            return {'url': None, 'location': 'Direct'}
        
        # Si hay mapeo fijo para este RFC, usarlo (consistencia geográfica)
        if rfc in self.RFC_PROXY_MAP:
            return self.RFC_PROXY_MAP[rfc]
        
        # Rotar al siguiente proxy
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        proxy = self.proxies[self.current_proxy_index]
        
        # Registrar uso
        self._log_proxy_use(rfc, proxy)
        
        return proxy
    
    def _log_proxy_use(self, rfc: str, proxy: Dict):
        """Registra uso de proxy para análisis."""
        if not self.core:
            return
        
        try:
            self.core.db.execute_write("""
                INSERT INTO config (key, value) 
                VALUES (%s, %s)
            """, (f'proxy_log_{datetime.now().timestamp()}',
                  json.dumps({
                      'rfc': rfc[-4:],  # Solo últimos 4 chars
                      'location': proxy.get('location', 'Unknown'),
                      'timestamp': datetime.now().isoformat()
                  })))
        except Exception:
            pass  # Non-critical logging, OK to fail silently
    
    def create_proxied_opener(self, proxy: Dict) -> urllib.request.OpenerDirector:
        """Crea un opener de urllib con el proxy configurado."""
        if not proxy.get('url'):
            return urllib.request.build_opener()
        
        proxy_url = proxy['url']
        
        if proxy_url.startswith('socks'):
            # Para SOCKS necesitamos PySocks
            try:
                import socket

                import socks

                # Configurar SOCKS
                socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
                socket.socket = socks.socksocket
                return urllib.request.build_opener()
            except ImportError:
                # SECURITY: No loguear fallback de conexión
                pass
                return urllib.request.build_opener()
        else:
            # HTTP/HTTPS proxy
            proxy_handler = urllib.request.ProxyHandler({
                'http': proxy_url,
                'https': proxy_url
            })
            return urllib.request.build_opener(proxy_handler)
    
    def timbrar_con_proxy(self, xml_data: str, rfc: str, 
                         pac_url: str) -> Dict[str, Any]:
        """
        Timbra un CFDI a través de un proxy rotativo.
        """
        proxy = self.get_proxy_for_rfc(rfc)
        opener = self.create_proxied_opener(proxy)
        
        try:
            request = urllib.request.Request(
                pac_url,
                data=xml_data.encode(),
                headers={
                    'Content-Type': 'application/xml',
                    'User-Agent': self._get_random_user_agent()
                }
            )
            
            with opener.open(request, timeout=30) as response:
                result = response.read().decode()

            # SECURITY: No loguear rutas de timbrado
            pass

            return {
                'success': True,
                'response': result,
                'proxy_used': proxy.get('location', 'Direct')
            }
            
        except Exception as e:
            logger.error(f"Error en timbrado: {e}")
            return {
                'success': False,
                'error': str(e),
                'proxy_used': proxy.get('location', 'Direct')
            }
    
    def _get_random_user_agent(self) -> str:
        """Genera un User-Agent aleatorio."""
        agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101',
        ]
        return _rng.choice(agents)
    
    def configure_proxies(self, proxies: List[Dict]) -> Dict:
        """
        Configura la lista de proxies.
        
        proxies: Lista de dicts con keys 'url', 'type', 'location'
        """
        self.proxies = proxies
        
        if self.core:
            self.core.db.execute_write(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                ('cfdi_proxies', json.dumps(proxies))
            )
        
        # SECURITY: No loguear configuración de proxies
        pass
        
        return {'configured': len(proxies)}
    
    def assign_rfc_to_proxy(self, rfc: str, proxy: Dict):
        """Asigna un RFC a un proxy específico para consistencia."""
        self.RFC_PROXY_MAP[rfc] = proxy
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Estadísticas de uso de proxies."""
        if not self.core:
            return {'stats': 'No disponible'}
        
        # Buscar logs de proxy
        logs = list(self.core.db.execute_query("""
            SELECT value FROM config 
            WHERE key LIKE 'proxy_log_%'
            ORDER BY key DESC
            LIMIT 100
        """))
        
        locations = {}
        for log in logs:
            try:
                data = json.loads(log['value'])
                loc = data.get('location', 'Unknown')
                locations[loc] = locations.get(loc, 0) + 1
            except (json.JSONDecodeError, KeyError, TypeError):
                continue  # Skip malformed log entries
        
        return {
            'total_requests': len(logs),
            'by_location': locations,
            'proxies_configured': len(self.proxies)
        }

# Integración con CFDIService existente
def wrap_cfdi_service_with_proxy(cfdi_service, core):
    """
    Envuelve el CFDIService existente con rotación de proxy.
    """
    rotator = CFDIProxyRotator(core)
    
    original_timbrar = cfdi_service.timbrar
    
    def timbrar_con_rotacion(*args, **kwargs):
        # Obtener RFC del CFDI
        rfc = kwargs.get('rfc') or args[0] if args else 'XAXX010101000'
        
        # Obtener proxy
        proxy = rotator.get_proxy_for_rfc(rfc)
        
        # Configurar proxy en el servicio
        if proxy.get('url'):
            kwargs['proxy'] = proxy['url']
        
        return original_timbrar(*args, **kwargs)
    
    cfdi_service.timbrar = timbrar_con_rotacion
    return cfdi_service

class GhostJitter:
    """
    Ghost-In-The-Shell: Jitter temporal para timbrado CFDI.
    
    El SAT detecta patrones cuando múltiples RFCs timbran
    exactamente a la misma hora todos los días.
    
    Este módulo añade retrasos aleatorios para parecer humano.
    """
    
    # Rangos de jitter en segundos
    MIN_JITTER = 120     # 2 minutos mínimo
    MAX_JITTER = 900     # 15 minutos máximo
    
    # Horas "humanas" de trabajo (9-18h)
    HUMAN_HOURS = range(9, 19)
    
    def __init__(self):
        self.pending_queue = []
        self._running = False
    
    def schedule_timbrado(self, cfdi_data: Dict, callback: callable,
                         immediate: bool = False) -> Dict:
        """
        Programa un timbrado con jitter aleatorio.
        
        cfdi_data: Datos del CFDI a timbrar
        callback: Función a llamar con los datos
        immediate: Si True, salta el jitter (urgente)
        """
        if immediate:
            # Sin jitter
            return callback(cfdi_data)
        
        # Calcular jitter
        jitter_seconds = _rng.randint(self.MIN_JITTER, self.MAX_JITTER)
        
        # Verificar si estamos en "horas humanas"
        current_hour = datetime.now().hour
        if current_hour not in self.HUMAN_HOURS:
            # Fuera de horario: posponer hasta mañana 9am + jitter
            # SECURITY: No loguear programación de timbrado
            pass
            # En producción, usar scheduler
            jitter_seconds = 0  # Procesar inmediato para demo
        
        # Programar
        import threading
        
        def delayed_timbrado():
            import time
            time.sleep(jitter_seconds)
            # SECURITY: No loguear ejecución de timbrado con jitter
            pass
            callback(cfdi_data)
        
        thread = threading.Thread(target=delayed_timbrado, daemon=True)
        thread.start()
        
        # SECURITY: No loguear programación de jitter
        pass
        
        return {
            'scheduled': True,
            'jitter_seconds': jitter_seconds,
            'will_execute_at': (datetime.now() + 
                               __import__('datetime').timedelta(seconds=jitter_seconds)).isoformat()
        }
    
    def get_random_timbrado_time(self) -> str:
        """
        Sugiere una hora aleatoria "humana" para timbrar.
        """
        hour = _rng.choice(list(self.HUMAN_HOURS))
        minute = _rng.randint(0, 59)
        second = _rng.randint(0, 59)
        
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    
    def distribute_timbrados(self, count: int, 
                            hours: int = 8) -> List[Dict]:
        """
        Distribuye múltiples timbrados a lo largo del día.
        
        Para evitar que 50 facturas se timbren a las 8:00 AM exactas.
        """
        from datetime import timedelta

        # Validate count to prevent division by zero
        if count <= 0:
            return []

        # Calcular intervalo base
        total_seconds = hours * 3600
        base_interval = total_seconds / count
        
        schedule = []
        current_time = datetime.now().replace(hour=9, minute=0, second=0)
        
        for i in range(count):
            # Añadir jitter al intervalo
            jitter = _rng.randint(-60, 60)  # ±1 minuto
            offset = int(i * base_interval + jitter)
            
            scheduled_time = current_time + timedelta(seconds=offset)
            
            schedule.append({
                'index': i + 1,
                'scheduled_time': scheduled_time.strftime('%H:%M:%S'),
                'jitter_applied': jitter
            })
        
        return schedule

# Función de utilidad para timbrado con jitter
def timbrar_con_ghost_jitter(core, cfdi_data: Dict, 
                             callback: callable) -> Dict:
    """
    Wrapper para timbrar con jitter automático.
    """
    jitter = GhostJitter()
    return jitter.schedule_timbrado(cfdi_data, callback)

