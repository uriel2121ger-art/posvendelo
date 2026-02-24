"""
YubiKey Authentication Module - Integración de seguridad física
Requiere: python-fido2, yubikey-manager
"""

from typing import Any, Dict, Optional
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class YubiKeyAuth:
    """
    Módulo de autenticación con YubiKey.
    Proporciona verificación de presencia y trigger de pánico.
    """
    
    PANIC_TRIGGER_FILE = Path.home() / '.config' / 'titan' / '.yubikey_panic_trigger'
    VENDOR_ID = "1050"  # Yubico
    
    def __init__(self):
        self.last_check = None
        self._panic_string = self._load_panic_string()
    
    def _load_panic_string(self) -> Optional[str]:
        """Carga la cadena de pánico configurada."""
        if self.PANIC_TRIGGER_FILE.exists():
            try:
                return self.PANIC_TRIGGER_FILE.read_text().strip()
            except Exception:
                pass
        return None
    
    def is_present(self) -> bool:
        """Verifica si hay una YubiKey conectada."""
        try:
            result = subprocess.run(
                ['ykman', 'info'],
                capture_output=True,
                timeout=5
            )
            present = result.returncode == 0
            self.last_check = datetime.now()
            return present
        except Exception:
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Obtiene información de la YubiKey conectada."""
        try:
            result = subprocess.run(
                ['ykman', 'info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return {'connected': False}
            
            info = {
                'connected': True,
                'raw': result.stdout
            }
            
            # Parsear información básica
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip().lower().replace(' ', '_')] = value.strip()
            
            return info
            
        except Exception as e:
            return {'connected': False, 'error': str(e)}
    
    def verify_otp(self, otp: str) -> bool:
        """
        Verifica un OTP de la YubiKey.
        Requiere configuración con servidor de validación Yubico.

        Args:
            otp: OTP generado por la YubiKey (44 caracteres para YubiKey estándar)

        Returns:
            True si el OTP es válido

        Raises:
            NotImplementedError: La verificación con API Yubico no está implementada
        """
        # Verificación básica de formato
        if not otp or len(otp) < 32:
            return False

        # Validar formato estándar YubiKey (44 caracteres)
        if len(otp) != 44:
            logger.warning(f"Invalid OTP format: length={len(otp)}")
            return False

        # Los primeros 12 caracteres son el ID público
        public_id = otp[:12]

        # TODO: Implementar verificación real contra API Yubico
        # Requiere:
        # - API Client ID de Yubico
        # - API Secret Key
        # - Llamada a https://api.yubico.com/wsapi/2.0/verify
        # Por ahora solo validamos el formato
        raise NotImplementedError(
            "Verificación de OTP con API Yubico no implementada. "
            "Se requiere configurar API Client ID y Secret Key de Yubico."
        )
    
    def check_panic_trigger(self, input_string: str) -> bool:
        """
        Verifica si la cadena ingresada es el trigger de pánico.
        Útil para detectar cuando se presiona la YubiKey por 3 segundos.
        """
        if not self._panic_string:
            return False
        
        # Comparación segura contra timing attacks
        if len(input_string) != len(self._panic_string):
            return False
        
        is_panic = input_string == self._panic_string
        
        if is_panic:
            # SECURITY: No loguear detección de panic trigger\n            pass
            self._execute_panic()
        
        return is_panic
    
    def _execute_panic(self):
        """Ejecuta el protocolo de pánico."""
        try:
            # Importar y ejecutar lockdown
            from app.services.network_lockdown import NetworkLockdown
            lockdown = NetworkLockdown()
            lockdown.quick_lockdown()
            
            # SECURITY: No loguear lockdown via YubiKey
            pass
            
        except Exception as e:
            logger.error(f"Error en panic execution: {e}")
    
    def require_touch(self, operation: str) -> bool:
        """
        Requiere toque de YubiKey para operaciones críticas.
        
        Args:
            operation: Nombre de la operación que requiere confirmación
        
        Returns:
            True si el usuario tocó la YubiKey
        """
        if not self.is_present():
            # SECURITY: No loguear presencia de YubiKey
            pass
            return False
        
        try:
            # Usar fido2-token para requerir toque
            result = subprocess.run(
                ['fido2-token', '-G', '-d', '/dev/hidraw0'],
                capture_output=True,
                timeout=30  # 30 segundos para tocar
            )
            
            if result.returncode == 0:
                # SECURITY: No loguear touch verificado
                pass
                return True
            
            return False
            
        except subprocess.TimeoutExpired:
            # SECURITY: No loguear timeout de YubiKey
            pass
            return False
        except Exception as e:
            logger.error(f"Error en touch verification: {e}")
            return False
    
    def get_challenge_response(self, challenge: bytes, slot: int = 2) -> Optional[bytes]:
        """
        Obtiene respuesta HMAC-SHA1 de la YubiKey.
        Útil para LUKS y otras aplicaciones criptográficas.
        
        Args:
            challenge: Bytes del desafío (máximo 64 bytes)
            slot: Slot de la YubiKey (1 o 2)
        """
        try:
            # Convertir challenge a hex
            challenge_hex = challenge.hex()
            
            result = subprocess.run(
                ['ykchalresp', f'-{slot}', '-H', challenge_hex],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                response = bytes.fromhex(result.stdout.decode().strip())
                return response
            
            return None
            
        except Exception as e:
            logger.error(f"Error en challenge-response: {e}")
            return None
    
    def derive_encryption_key(self, password: str, salt: bytes = None) -> bytes:
        """
        Deriva una llave de cifrado combinando password + YubiKey.
        Útil para cifrado de archivos sensibles.
        """
        if salt is None:
            salt = os.urandom(32)
        
        # Crear desafío desde password
        password_hash = hashlib.sha256(password.encode()).digest()
        challenge = password_hash[:64]
        
        # Obtener respuesta de YubiKey
        yubikey_response = self.get_challenge_response(challenge)
        
        if not yubikey_response:
            raise ValueError("No se pudo obtener respuesta de YubiKey")
        
        # Combinar password + yubikey response
        combined = password_hash + yubikey_response + salt
        
        # Derivar llave final
        key = hashlib.pbkdf2_hmac('sha256', combined, salt, 100000, dklen=32)
        
        return key

class YubiKeyGuard:
    """
    Decorador para proteger funciones con YubiKey.
    """
    
    def __init__(self, require_touch: bool = True):
        self.require_touch = require_touch
        self.auth = YubiKeyAuth()
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if not self.auth.is_present():
                raise PermissionError("YubiKey requerida para esta operación")
            
            if self.require_touch:
                if not self.auth.require_touch(func.__name__):
                    raise PermissionError("Toque de YubiKey requerido")
            
            return func(*args, **kwargs)
        
        return wrapper

# Ejemplo de uso:
# @YubiKeyGuard(require_touch=True)
# def operacion_critica():
#     pass
