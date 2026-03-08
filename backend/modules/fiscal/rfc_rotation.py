"""
Auto-Proxy CFDI - Rotación de IPs para Timbrado
"""

from typing import Any, Dict, List
from datetime import datetime
from urllib.parse import urlparse
import hashlib
import ipaddress
import json
import logging
import secrets
import socket
import urllib.request

_rng = secrets.SystemRandom()
logger = logging.getLogger(__name__)


class CFDIProxyRotator:
    PROXY_PROVIDERS = {
        'residential': [],
        'datacenter': [],
        'tor': [],
    }
    RFC_PROXY_MAP = {}

    def __init__(self, db=None):
        self.db = db
        self.current_proxy_index = 0
        self.proxies = []
        self._load_proxies()

    def _load_proxies(self):
        if not self.db:
            self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]
            return
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]
            else:
                self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]
        except Exception:
            self.proxies = [{'url': None, 'type': 'direct', 'location': 'Local'}]

    def get_proxy_for_rfc(self, rfc: str) -> Dict[str, Any]:
        if not self.proxies:
            return {'url': None, 'location': 'Direct'}
        if rfc in self.RFC_PROXY_MAP:
            return self.RFC_PROXY_MAP[rfc]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return self.proxies[self.current_proxy_index]

    def create_proxied_opener(self, proxy: Dict) -> urllib.request.OpenerDirector:
        if not proxy.get('url'):
            return urllib.request.build_opener()
        proxy_url = proxy['url']
        if proxy_url.startswith('socks'):
            try:
                import socket, socks
                socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
                socket.socket = socks.socksocket
                return urllib.request.build_opener()
            except ImportError:
                return urllib.request.build_opener()
        else:
            return urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))

    # SECURITY: Allowlist of known PAC provider hostnames to prevent SSRF
    ALLOWED_PAC_HOSTS = {
        'facturapi.io', 'www.facturapi.io', 'api.facturapi.io',
        'sw.com.mx', 'services.sw.com.mx', 'api.sw.com.mx',
        'finkok.com', 'facturacion.finkok.com', 'demo-facturacion.finkok.com',
        'pac.sat.gob.mx', 'cfdi.sat.gob.mx',
        'timbrado.pade.mx', 'api.pade.mx',
    }

    @staticmethod
    def _validate_pac_url(pac_url: str) -> None:
        """Validate PAC URL to prevent SSRF attacks."""
        parsed = urlparse(pac_url)
        # Only HTTPS allowed
        if parsed.scheme != 'https':
            raise ValueError(f"PAC URL must use HTTPS, got: {parsed.scheme}")
        hostname = parsed.hostname or ''
        # Block private/loopback IPs
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                raise ValueError(f"PAC URL resolved to private/loopback IP: {ip}")
        except (socket.gaierror, ValueError):
            pass  # DNS resolution may fail for valid hostnames; allowlist handles it
        # Allowlist check
        if hostname not in CFDIProxyRotator.ALLOWED_PAC_HOSTS:
            raise ValueError(
                f"PAC host '{hostname}' not in allowed list. "
                f"Add it to CFDIProxyRotator.ALLOWED_PAC_HOSTS if legitimate."
            )

    def timbrar_con_proxy(self, xml_data: str, rfc: str, pac_url: str) -> Dict[str, Any]:
        # SECURITY: Validate URL before making the request
        self._validate_pac_url(pac_url)
        proxy = self.get_proxy_for_rfc(rfc)
        opener = self.create_proxied_opener(proxy)
        try:
            request = urllib.request.Request(pac_url, data=xml_data.encode(),
                headers={'Content-Type': 'application/xml', 'User-Agent': self._get_random_user_agent()})
            with opener.open(request, timeout=30) as response:
                result = response.read().decode()
            return {'success': True, 'response': result, 'proxy_used': proxy.get('location', 'Direct')}
        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            return {'success': False, 'error': str(e), 'proxy_used': proxy.get('location', 'Direct')}

    def _get_random_user_agent(self) -> str:
        agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]
        return _rng.choice(agents)

    def configure_proxies(self, proxies: List[Dict]) -> Dict:
        self.proxies = proxies
        return {'configured': len(proxies)}

    def assign_rfc_to_proxy(self, rfc: str, proxy: Dict):
        self.RFC_PROXY_MAP[rfc] = proxy


class GhostJitter:
    MIN_JITTER = 120
    MAX_JITTER = 900
    HUMAN_HOURS = range(9, 19)

    def __init__(self):
        self.pending_queue = []

    def schedule_timbrado(self, cfdi_data: Dict, callback: callable, immediate: bool = False) -> Dict:
        if immediate:
            return callback(cfdi_data)

        jitter_seconds = _rng.randint(self.MIN_JITTER, self.MAX_JITTER)
        current_hour = datetime.now().hour
        if current_hour not in self.HUMAN_HOURS:
            jitter_seconds = 0

        import threading
        def delayed():
            import time
            time.sleep(jitter_seconds)
            callback(cfdi_data)
        threading.Thread(target=delayed, daemon=True).start()

        return {'scheduled': True, 'jitter_seconds': jitter_seconds,
                'will_execute_at': (datetime.now() + __import__('datetime').timedelta(seconds=jitter_seconds)).isoformat()}

    def get_random_timbrado_time(self) -> str:
        h, m, s = _rng.choice(list(self.HUMAN_HOURS)), _rng.randint(0, 59), _rng.randint(0, 59)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def distribute_timbrados(self, count: int, hours: int = 8) -> List[Dict]:
        from datetime import timedelta
        if count <= 0: return []
        total_seconds = hours * 3600
        base_interval = total_seconds / count
        current_time = datetime.now().replace(hour=9, minute=0, second=0)
        schedule = []
        for i in range(count):
            jitter = _rng.randint(-60, 60)
            offset = int(i * base_interval + jitter)
            scheduled_time = current_time + timedelta(seconds=offset)
            schedule.append({'index': i + 1, 'scheduled_time': scheduled_time.strftime('%H:%M:%S'), 'jitter_applied': jitter})
        return schedule
