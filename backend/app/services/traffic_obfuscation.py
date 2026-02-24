from pathlib import Path

"""
Traffic Obfuscation - Anti-Packet Inspection
Disfraza tráfico de sincronización como video/multimedia
"""

from typing import Any, Dict, Optional, Union
import base64
from datetime import datetime
import gzip
import json
import logging
import os
import random
import struct
import sys

logger = logging.getLogger(__name__)

class TrafficObfuscator:
    """
    Sistema de ofuscación de tráfico de red.
    
    Disfraza los datos de sincronización como:
    - Fragmentos de video (MP4/WebM)
    - Streams de audio
    - Tráfico WebSocket de videollamada
    - CDN de imágenes
    
    Para un inspector de red, el local solo está "viendo videos".
    """
    
    # Headers de diferentes tipos de contenido
    VIDEO_HEADERS = {
        'mp4': bytes([0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70]),
        'webm': bytes([0x1A, 0x45, 0xDF, 0xA3]),
        'flv': bytes([0x46, 0x4C, 0x56, 0x01])
    }
    
    AUDIO_HEADERS = {
        'mp3': bytes([0xFF, 0xFB]),
        'ogg': bytes([0x4F, 0x67, 0x67, 0x53])
    }
    
    # Dominios que parecen CDN legítimos
    FAKE_ORIGINS = [
        'cdn.youtube.googleapis.com',
        'video-edge.facebook.com',
        'live-video.net',
        'stream.zoom.us',
        'media.google.com'
    ]
    
    def __init__(self, method: str = 'video'):
        """
        method: 'video', 'audio', 'websocket', 'image'
        """
        self.method = method
        self.sequence_number = 0
    
    def obfuscate(self, data: Union[bytes, str, dict]) -> bytes:
        """
        Ofusca datos para que parezcan tráfico multimedia.
        """
        # Convertir a bytes si es necesario
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        elif isinstance(data, str):
            data = data.encode()
        
        # Comprimir
        compressed = gzip.compress(data)
        
        # Aplicar método de ofuscación
        if self.method == 'video':
            return self._wrap_as_video(compressed)
        elif self.method == 'audio':
            return self._wrap_as_audio(compressed)
        elif self.method == 'websocket':
            return self._wrap_as_websocket(compressed)
        else:
            return self._wrap_as_image(compressed)
    
    def deobfuscate(self, obfuscated: bytes) -> bytes:
        """
        Remueve ofuscación y retorna datos originales.
        """
        if self.method == 'video':
            compressed = self._unwrap_video(obfuscated)
        elif self.method == 'audio':
            compressed = self._unwrap_audio(obfuscated)
        elif self.method == 'websocket':
            compressed = self._unwrap_websocket(obfuscated)
        else:
            compressed = self._unwrap_image(obfuscated)
        
        return gzip.decompress(compressed)
    
    def _wrap_as_video(self, data: bytes) -> bytes:
        """Envuelve datos como fragmento de video MP4."""
        # Header de MP4 mdat box
        header = self.VIDEO_HEADERS['mp4']
        
        # Añadir tamaño del "chunk" de video
        size = len(data) + 8
        size_bytes = struct.pack('>I', size)
        
        # Marker de fin
        footer = b'\x00\x00\x00\x08mdat'
        
        # Número de secuencia (simula streaming)
        self.sequence_number = (self.sequence_number + 1) % 65535
        seq = struct.pack('>H', self.sequence_number)
        
        # XOR simple para mayor ofuscación
        xored = self._xor_data(data, b'SYNC')
        
        return header + size_bytes + seq + xored + footer
    
    def _unwrap_video(self, obfuscated: bytes) -> bytes:
        """Extrae datos de un paquete de video falso."""
        # Remover header (8 bytes) + size (4 bytes) + seq (2 bytes)
        start = 14
        # Remover footer (8 bytes)
        end = -8
        
        xored = obfuscated[start:end]
        return self._xor_data(xored, b'SYNC')
    
    def _wrap_as_audio(self, data: bytes) -> bytes:
        """Envuelve datos como stream de audio OGG."""
        header = self.AUDIO_HEADERS['ogg']
        
        # OGG page structure simulada
        page_header = struct.pack('<I', len(data))  # Segment size
        
        xored = self._xor_data(data, b'AUDIO')
        
        return header + page_header + xored
    
    def _unwrap_audio(self, obfuscated: bytes) -> bytes:
        """Extrae datos de paquete de audio falso."""
        start = 8  # Header + page header
        xored = obfuscated[start:]
        return self._xor_data(xored, b'AUDIO')
    
    def _wrap_as_websocket(self, data: bytes) -> bytes:
        """Envuelve como frames de WebSocket (Zoom/Meet style)."""
        # WebSocket frame header
        fin_opcode = 0x82  # Binary frame
        
        length = len(data)
        if length < 126:
            header = bytes([fin_opcode, length])
        elif length < 65536:
            header = bytes([fin_opcode, 126]) + struct.pack('>H', length)
        else:
            header = bytes([fin_opcode, 127]) + struct.pack('>Q', length)
        
        # Masking key (requerido en WebSocket cliente)
        mask_key = bytes([random.randint(0, 255) for _ in range(4)])
        
        # Aplicar mask
        masked = bytearray(len(data))
        for i, b in enumerate(data):
            masked[i] = b ^ mask_key[i % 4]
        
        return header + mask_key + bytes(masked)
    
    def _unwrap_websocket(self, obfuscated: bytes) -> bytes:
        """Extrae datos de frame WebSocket."""
        # Parsear header
        length_byte = obfuscated[1] & 0x7F
        
        if length_byte < 126:
            mask_start = 2
        elif length_byte == 126:
            mask_start = 4
        else:
            mask_start = 10
        
        mask_key = obfuscated[mask_start:mask_start + 4]
        data_start = mask_start + 4
        masked = obfuscated[data_start:]
        
        # Unmask
        unmasked = bytearray(len(masked))
        for i, b in enumerate(masked):
            unmasked[i] = b ^ mask_key[i % 4]
        
        return bytes(unmasked)
    
    def _wrap_as_image(self, data: bytes) -> bytes:
        """Envuelve como chunk de imagen JPEG."""
        # JPEG header
        jpeg_header = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10,
                            0x4A, 0x46, 0x49, 0x46, 0x00])
        
        # Escondemos datos en un segmento APP de JPEG
        app_marker = bytes([0xFF, 0xE1])  # APP1 (como EXIF)
        size = struct.pack('>H', len(data) + 2)
        
        xored = self._xor_data(data, b'IMG')
        
        # JPEG footer
        jpeg_footer = bytes([0xFF, 0xD9])
        
        return jpeg_header + app_marker + size + xored + jpeg_footer
    
    def _unwrap_image(self, obfuscated: bytes) -> bytes:
        """Extrae datos de imagen JPEG."""
        # Encontrar APP1 marker
        app1_pos = obfuscated.find(bytes([0xFF, 0xE1]))
        if app1_pos == -1:
            raise ValueError("Invalid obfuscated image")
        
        # Leer tamaño
        size_bytes = obfuscated[app1_pos + 2:app1_pos + 4]
        size = struct.unpack('>H', size_bytes)[0] - 2
        
        # Extraer datos
        data_start = app1_pos + 4
        xored = obfuscated[data_start:data_start + size]
        
        return self._xor_data(xored, b'IMG')
    
    def _xor_data(self, data: bytes, key: bytes) -> bytes:
        """XOR simple para ofuscación adicional."""
        result = bytearray(len(data))
        key_len = len(key)
        
        for i, b in enumerate(data):
            result[i] = b ^ key[i % key_len]
        
        return bytes(result)
    
    def get_fake_http_headers(self) -> Dict[str, str]:
        """Genera headers HTTP que parecen de CDN legítimo."""
        origin = random.choice(self.FAKE_ORIGINS)
        
        content_types = {
            'video': 'video/mp4',
            'audio': 'audio/ogg',
            'websocket': 'application/octet-stream',
            'image': 'image/jpeg'
        }
        
        return {
            'Content-Type': content_types.get(self.method, 'application/octet-stream'),
            'X-CDN-Source': origin,
            'X-Cache': 'HIT',
            'X-Content-Duration': str(random.randint(30, 300)),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': os.getenv('ALLOWED_ORIGINS', 'https://titan-pos.local')
        }

class StealthSync:
    """
    Sincronización sigilosa usando ofuscación de tráfico.
    Integra con Ghost-Sync para máxima invisibilidad.
    """
    
    def __init__(self, core, obfuscator: TrafficObfuscator = None):
        self.core = core
        self.obfuscator = obfuscator or TrafficObfuscator(method='video')
    
    def prepare_sync_packet(self, data: Dict) -> Dict[str, Any]:
        """
        Prepara un paquete de sincronización ofuscado.
        """
        # Datos originales
        json_data = json.dumps(data)
        
        # Ofuscar
        obfuscated = self.obfuscator.obfuscate(json_data)
        
        # Codificar en base64 para transmisión HTTP
        encoded = base64.b64encode(obfuscated).decode()
        
        # Headers falsos
        headers = self.obfuscator.get_fake_http_headers()
        
        return {
            'payload': encoded,
            'headers': headers,
            'method': self.obfuscator.method,
            'size': len(obfuscated),
            'original_size': len(json_data.encode())
        }
    
    def extract_sync_packet(self, packet: Dict) -> Dict:
        """
        Extrae datos de un paquete ofuscado recibido.
        """
        # Decodificar base64
        obfuscated = base64.b64decode(packet['payload'])
        
        # Deofuscar
        original = self.obfuscator.deobfuscate(obfuscated)
        
        # Parsear JSON
        return json.loads(original.decode())

# Función de utilidad para Ghost-Sync
def create_stealth_channel(core) -> StealthSync:
    """Crea un canal de sincronización sigiloso."""
    # Rotar método de ofuscación para evitar patrones
    methods = ['video', 'audio', 'websocket', 'image']
    method = random.choice(methods)
    
    obfuscator = TrafficObfuscator(method=method)
    return StealthSync(core, obfuscator)
