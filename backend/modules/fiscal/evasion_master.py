"""
Evasion Master - Anti-Forensics + Panic Wipe + Fake Screens
Consolidación de dead_drive_simulator, fake_maintenance, panic_wipe
"""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import logging
import os
import random
import subprocess
import threading
import time
import glob
import struct
import shutil

logger = logging.getLogger(__name__)


class EvasionMaster:
    VOLATILE_PATHS = ['/mnt/volatile_logs', '/tmp/antigravity_*', '/run/user/*/antigravity*']
    SERVICES_TO_KILL = ['tailscaled']
    HOTKEY = 'ctrl+alt+shift+k'

    CORRUPTION_PATTERNS = [
        b'\x00' * 512,
        b'\xFF' * 512,
        b'\xAA\x55' * 256,
    ]

    CRITICAL_OFFSETS = {
        'mbr': 0, 'gpt_header': 512, 'gpt_entries': 1024,
        'superblock_ext4': 1024, 'backup_superblock': 32768,
    }

    FAILURE_NARRATIVES = [
        "Fallo catastrófico por sobrecalentamiento (temperatura ambiente excede especificaciones).",
        "Fallo del controlador por pico de voltaje de la CFE. Sectores quemados.",
        "Corrupción de tabla de particiones y bad sectors. Fallo de flash NAND.",
        "Síntomas de fallo mecánico por vibración (edificio antiguo).",
    ]

    def __init__(self, db=None):
        self.db = db
        self.armed = False
        self._trigger_callback: Optional[Callable] = None

    # ── Panic Wipe ────────────────────────────────────────────────

    def arm(self):
        self.armed = True

    def disarm(self):
        self.armed = False

    def trigger_panic(self, immediate: bool = True) -> Dict[str, Any]:
        if not self.armed:
            return {'triggered': False, 'reason': 'Not armed'}

        start = time.time()
        actions = []

        if self._trigger_callback:
            try:
                self._trigger_callback()
                actions.append('custom_callback')
            except Exception:
                pass

        try:
            self._unmount_volatile()
            actions.append('unmount_ramfs')
        except Exception:
            pass

        try:
            self._kill_network_services()
            actions.append('kill_network')
        except Exception:
            pass

        try:
            self._wipe_temp_files()
            actions.append('wipe_temp')
        except Exception:
            pass

        if self.db:
            try:
                # Can't use await in sync context; use fire-and-forget approach
                pass
            except Exception:
                pass

        try:
            os.sync()
            actions.append('sync')
        except Exception:
            pass

        elapsed = time.time() - start

        if immediate:
            actions.append('poweroff')
            self._emergency_poweroff()

        return {'triggered': True, 'actions': actions, 'elapsed_seconds': elapsed}

    def _unmount_volatile(self):
        for mp in ['/mnt/volatile_logs', '/mnt/ramfs']:
            try:
                subprocess.run(['umount', '-f', mp], capture_output=True, timeout=2)
            except Exception:
                pass

    def _kill_network_services(self):
        for svc in self.SERVICES_TO_KILL:
            try:
                subprocess.run(['pkill', '-9', svc], capture_output=True, timeout=1)
            except Exception:
                pass
        try:
            subprocess.run(['tailscale', 'down'], capture_output=True, timeout=2)
        except Exception:
            pass

    def _wipe_temp_files(self):
        for pattern in ['/tmp/antigravity*', '/tmp/.pos_*', '/run/user/*/antigravity*']:
            for path in glob.glob(pattern):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except Exception:
                    pass

    def _emergency_poweroff(self):
        try:
            subprocess.Popen(['poweroff'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                subprocess.Popen(['poweroff', '-f'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                try:
                    with open('/proc/sysrq-trigger', 'w') as f:
                        f.write('o')
                except Exception:
                    pass

    def set_trigger_callback(self, cb: Callable):
        self._trigger_callback = cb

    # ── Dead Drive Simulator ──────────────────────────────────────

    def simulate_dead_drive(self, device: str, confirm: str = None) -> Dict[str, Any]:
        if confirm != "CONFIRMO DESTRUCCION":
            return {'success': False, 'error': 'Confirmación requerida: "CONFIRMO DESTRUCCION"'}
        if not device:
            return {'success': False, 'error': 'Dispositivo no especificado'}

        corruption_log = []
        try:
            self._unmount_device(device)
            self._corrupt_partition_table(device, corruption_log)
            self._generate_fake_bad_sectors(device, corruption_log)
            self._corrupt_superblocks(device, corruption_log)
            self._simulate_electrical_damage(device, corruption_log)

            return {
                'success': True, 'device': device, 'corruptions': len(corruption_log),
                'narrative': random.choice(self.FAILURE_NARRATIVES)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def quick_brick(self, device: str, confirm: str = None) -> Dict[str, Any]:
        if confirm != "BRICK":
            return {'success': False, 'error': 'Confirmación: "BRICK"'}
        try:
            with open(device, 'r+b') as f:
                f.seek(0)
                f.write(b'\x00' * 512)
                f.write(b'\xFF' * 512)
                for _ in range(100):
                    offset = random.randint(1024, 1024 * 1024)
                    f.seek(offset)
                    f.write(bytes(random.getrandbits(8) for _ in range(512)))
            return {'success': True, 'message': 'Quick brick completado'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _unmount_device(self, device: str):
        try:
            result = subprocess.run(['mount'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if device in line:
                    mp = line.split()[2]
                    subprocess.run(['umount', '-f', mp], check=False)
        except Exception:
            pass

    def _corrupt_partition_table(self, device, log):
        try:
            with open(device, 'r+b') as f:
                f.seek(0)
                original = bytearray(f.read(512))
                for _ in range(random.randint(20, 50)):
                    pos = random.randint(0, 511)
                    original[pos] = 0x00 if random.random() > 0.5 else (original[pos] ^ random.randint(1, 255))
                f.seek(0)
                f.write(bytes(original))
                log.append({'type': 'partition_table'})
        except Exception:
            pass

    def _generate_fake_bad_sectors(self, device, log):
        try:
            with open(device, 'rb') as f:
                f.seek(0, 2)
                size = f.tell()
            with open(device, 'r+b') as f:
                for _ in range(random.randint(50, 200)):
                    offset = random.randint(1024*1024, min(size - 512, size // 2))
                    offset = (offset // 512) * 512
                    f.seek(offset)
                    f.write(random.choice(self.CORRUPTION_PATTERNS))
                    log.append({'type': 'bad_sector', 'offset': offset})
        except Exception:
            pass

    def _corrupt_superblocks(self, device, log):
        try:
            with open(device, 'r+b') as f:
                for name, offset in self.CRITICAL_OFFSETS.items():
                    if 'superblock' in name:
                        f.seek(offset)
                        f.write(bytes(random.randint(0, 255) if random.random() > 0.7 else 0 for _ in range(1024)))
                        log.append({'type': 'superblock', 'name': name})
        except Exception:
            pass

    def _simulate_electrical_damage(self, device, log):
        try:
            with open(device, 'r+b') as f:
                for _ in range(random.randint(10, 30)):
                    offset = random.randint(0, 100*1024*1024)
                    offset = (offset // 4096) * 4096
                    f.seek(offset)
                    f.write(b'\xFF' * 4096)
                    log.append({'type': 'electrical_burn'})
        except Exception:
            pass

    # ── Fake Maintenance Screen ───────────────────────────────────

    def get_fake_screen_data(self, screen_type: str = 'windows_update') -> Dict[str, Any]:
        if screen_type == 'bios_error':
            return {
                'type': 'bios_error',
                'title': 'American Megatrends Inc. BIOS Setup Utility',
                'errors': [
                    'SMART Hard Drive Detects Imminent Failure',
                    'Error: 0171 - Disk Sector Read Failure',
                    'Error: 0250 - SSD Controller Failure Imminent',
                    f'Device: KINGSTON SA400S37240G  Serial: {random.randint(100000, 999999)}',
                    'SMART Error Count: 2847',
                    'Reallocated Sector Count: 1589',
                    'WARNING: Data may be corrupted or unrecoverable.',
                ],
                'instruction': 'Press F1 to Attempt Recovery or ESC to Exit Setup'
            }
        elif screen_type == 'disk_check':
            return {
                'type': 'disk_check',
                'title': 'Checking file system on C:',
                'filesystem': 'NTFS',
                'stages': 5,
                'current_stage': 1,
                'progress': 0
            }
        return {
            'type': 'windows_update',
            'title': 'Windows Update',
            'message': 'Trabajando en actualizaciones',
            'warning': 'No apagues el equipo',
            'progress': 0
        }

    def trigger_screen_with_protection(self, screen_type: str = 'windows_update') -> Dict[str, Any]:
        thread = threading.Thread(target=self._run_background_protection, daemon=True)
        thread.start()
        return {
            'success': True,
            'screen': self.get_fake_screen_data(screen_type),
            'message': 'Protection running in background'
        }

    def _run_background_protection(self):
        try:
            os.system('sudo umount -f /mnt/ramfs 2>/dev/null')
            os.system('sudo shred -vfz /var/log/antigravity/* 2>/dev/null')
            if self.db:
                pass  # DB cleanup handled at async layer
            os.system('sync')
        except Exception:
            pass

    # ── Hotkey Listener ───────────────────────────────────────────

    def start_hotkey_listener(self) -> Dict[str, Any]:
        try:
            from pynput import keyboard

            def on_activate():
                if self.armed:
                    self.trigger_panic(immediate=True)

            hotkey = keyboard.HotKey(keyboard.HotKey.parse('<ctrl>+<alt>+<shift>+k'), on_activate)

            def for_canonical(f):
                return lambda k: f(listener.canonical(k))

            listener = keyboard.Listener(
                on_press=for_canonical(hotkey.press),
                on_release=for_canonical(hotkey.release)
            )
            listener.start()
            return {'active': True, 'hotkey': self.HOTKEY}
        except ImportError:
            return {'active': False, 'reason': 'pynput not installed'}
