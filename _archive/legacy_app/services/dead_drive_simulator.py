from pathlib import Path

"""
Dead Drive Simulator - Simulador Anti-Forense de Disco Muerto
Corrupción controlada que simula fallo físico catastrófico
"""

from typing import Any, Dict, Optional
from datetime import datetime
import logging
import os
import random
import struct
import subprocess
import sys

logger = logging.getLogger(__name__)

class DeadDriveSimulator:
    """
    Sistema anti-forense que simula fallo físico de disco.
    
    Al activar pánico:
    - Corrompe tabla de particiones
    - Genera "bad sectors" falsos
    - Deja el disco como basura inservible
    
    Narrativa: "El disco falló por el calor de Mérida y la CFE"
    """
    
    # Patrones de corrupción que parecen naturales
    CORRUPTION_PATTERNS = [
        b'\x00' * 512,           # Sector totalmente borrado
        b'\xFF' * 512,           # Todos unos (fallo de flash)
        b'\xAA\x55' * 256,       # Patrón de test fallido
        bytes(random.getrandbits(8) for _ in range(512)),  # Ruido aleatorio
    ]
    
    # Ubicaciones críticas del filesystem
    CRITICAL_OFFSETS = {
        'mbr': 0,                    # Master Boot Record
        'gpt_header': 512,           # GPT Header
        'gpt_entries': 1024,         # GPT Partition entries
        'superblock_ext4': 1024,     # Ext4 superblock
        'backup_superblock': 32768,  # Backup superblock
    }
    
    def __init__(self, device: str = None):
        self.device = device
        self.corruption_log = []
    
    def simulate_catastrophic_failure(self, 
                                      device: str = None,
                                      confirm: str = None) -> Dict[str, Any]:
        """
        Simula fallo catastrófico del disco.
        
        Args:
            device: Dispositivo a corromper (/dev/sdX)
            confirm: "CONFIRMO DESTRUCCION"
        
        Returns:
            Resultado de la operación
        """
        if confirm != "CONFIRMO DESTRUCCION":
            return {
                'success': False,
                'error': 'Confirmación requerida: "CONFIRMO DESTRUCCION"'
            }
        
        target = device or self.device
        if not target:
            return {'success': False, 'error': 'Dispositivo no especificado'}
        
        # SECURITY: No loguear operaciones antiforenses
        pass
        
        try:
            # 1. Desmontar el dispositivo
            self._unmount_device(target)
            
            # 2. Corromper tabla de particiones
            self._corrupt_partition_table(target)
            
            # 3. Generar bad sectors falsos
            self._generate_fake_bad_sectors(target)
            
            # 4. Corromper superblocks
            self._corrupt_superblocks(target)
            
            # 5. Dejar rastros de "daño eléctrico"
            self._simulate_electrical_damage(target)
            
            # SECURITY: No loguear completado de operaciones antiforenses
            pass
            
            return {
                'success': True,
                'device': target,
                'corruptions': len(self.corruption_log),
                'narrative': self._generate_failure_narrative(),
                'message': 'Disco simulado como muerto. Parece fallo físico.'
            }
            
        except Exception as e:
            logger.error(f"Error en Dead Drive: {e}")
            return {'success': False, 'error': str(e)}
    
    def _unmount_device(self, device: str):
        """Desmonta el dispositivo de forma segura."""
        try:
            # Buscar particiones montadas
            result = subprocess.run(
                ['mount'], capture_output=True, text=True
            )
            
            for line in result.stdout.split('\n'):
                if device in line:
                    mount_point = line.split()[2]
                    subprocess.run(['umount', '-f', mount_point], check=False)
                    # SECURITY: No loguear operaciones de desmontaje
                    pass
                    
        except Exception as e:
            # SECURITY: No loguear errores de desmontaje
            pass
    
    def _corrupt_partition_table(self, device: str):
        """Corrompe MBR/GPT de forma que parezca fallo físico."""
        try:
            with open(device, 'r+b') as f:
                # Corromper MBR parcialmente (no todo, sería sospechoso)
                f.seek(self.CRITICAL_OFFSETS['mbr'])
                
                # Mantener algunos bytes originales, corromper otros
                original = f.read(512)
                corrupted = bytearray(original)
                
                # Corromper bytes aleatorios (simula pérdida de bits)
                for _ in range(random.randint(20, 50)):
                    pos = random.randint(0, 511)
                    # Flip algunos bits o poner a 0
                    if random.random() > 0.5:
                        corrupted[pos] ^= random.randint(1, 255)
                    else:
                        corrupted[pos] = 0x00
                
                f.seek(self.CRITICAL_OFFSETS['mbr'])
                f.write(bytes(corrupted))
                
                self.corruption_log.append({
                    'type': 'partition_table',
                    'offset': 0,
                    'bytes_affected': 512
                })
                
        except Exception as e:
            logger.error(f"Error corrompiendo partición: {e}")
    
    def _generate_fake_bad_sectors(self, device: str):
        """Genera sectores que parecen físicamente dañados."""
        try:
            # Obtener tamaño del dispositivo
            with open(device, 'rb') as f:
                f.seek(0, 2)
                size = f.tell()
            
            # Generar bad sectors en ubicaciones aleatorias
            num_bad_sectors = random.randint(50, 200)
            sector_size = 512
            
            with open(device, 'r+b') as f:
                for _ in range(num_bad_sectors):
                    # Posición aleatoria (evitar primeros sectores críticos)
                    offset = random.randint(1024 * 1024, min(size - sector_size, size // 2))
                    offset = (offset // sector_size) * sector_size
                    
                    # Patrón de corrupción
                    pattern = random.choice(self.CORRUPTION_PATTERNS)
                    
                    f.seek(offset)
                    f.write(pattern)
                    
                    self.corruption_log.append({
                        'type': 'bad_sector',
                        'offset': offset,
                        'pattern': 'random'
                    })
                    
        except Exception as e:
            logger.error(f"Error generando bad sectors: {e}")
    
    def _corrupt_superblocks(self, device: str):
        """Corrompe superblocks del filesystem."""
        try:
            with open(device, 'r+b') as f:
                for name, offset in self.CRITICAL_OFFSETS.items():
                    if 'superblock' in name:
                        f.seek(offset)
                        
                        # Corrupción parcial
                        corrupted = bytes(
                            random.randint(0, 255) if random.random() > 0.7 else 0
                            for _ in range(1024)
                        )
                        f.write(corrupted)
                        
                        self.corruption_log.append({
                            'type': 'superblock',
                            'name': name,
                            'offset': offset
                        })
                        
        except Exception as e:
            logger.error(f"Error corrompiendo superblocks: {e}")
    
    def _simulate_electrical_damage(self, device: str):
        """Simula daño por pico eléctrico de la CFE."""
        try:
            with open(device, 'r+b') as f:
                # Sectores con patrón de "burn" (todos 1s o 0s en clusters)
                burn_clusters = random.randint(10, 30)
                cluster_size = 4096
                
                for _ in range(burn_clusters):
                    offset = random.randint(0, 1024 * 1024 * 100)
                    offset = (offset // cluster_size) * cluster_size
                    
                    # Simular quemado (todos 1s)
                    burn_pattern = b'\xFF' * cluster_size
                    
                    f.seek(offset)
                    f.write(burn_pattern)
                    
                    self.corruption_log.append({
                        'type': 'electrical_burn',
                        'offset': offset,
                        'size': cluster_size
                    })
                    
        except Exception as e:
            logger.error(f"Error simulando daño eléctrico: {e}")
    
    def _generate_failure_narrative(self) -> str:
        """Genera la narrativa para explicar el 'fallo'."""
        narratives = [
            "El disco presentó fallo catastrófico por sobrecalentamiento "
            "(temperatura ambiente de Mérida excede especificaciones del fabricante).",
            
            "Fallo del controlador de disco por pico de voltaje de la CFE. "
            "Se observan sectores quemados típicos de descarga eléctrica.",
            
            "Corrupción de tabla de particiones y múltiples bad sectors. "
            "Consistente con fallo de flash NAND por ciclos de escritura excesivos.",
            
            "El disco muestra síntomas de fallo mecánico por vibración "
            "(edificio antiguo del centro de Mérida).",
        ]
        return random.choice(narratives)
    
    def quick_brick(self, device: str, confirm: str = None) -> Dict[str, Any]:
        """
        Brick rápido: corrompe solo lo esencial en segundos.
        Para uso con Panic Button.
        """
        if confirm != "BRICK":
            return {'success': False, 'error': 'Confirmación: "BRICK"'}
        
        try:
            with open(device, 'r+b') as f:
                # Solo corromper MBR y primeros 1MB
                f.seek(0)
                f.write(b'\x00' * 512)  # MBR
                f.write(b'\xFF' * 512)  # GPT header (burn)
                
                # Scatter random corruption
                for _ in range(100):
                    offset = random.randint(1024, 1024 * 1024)
                    f.seek(offset)
                    f.write(bytes(random.getrandbits(8) for _ in range(512)))
            
            return {
                'success': True,
                'message': 'Quick brick completado',
                'narrative': 'Disco muestra como RAW sin formato'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Función para Panic Button
def brick_drive(device: str, confirm: str = None):
    """Wrapper para brick rápido desde Panic."""
    simulator = DeadDriveSimulator(device)
    return simulator.quick_brick(device, confirm)
