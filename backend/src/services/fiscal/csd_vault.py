"""
🔐 Bóveda Segura para Archivos CSD
Encripta archivos .key y contraseñas con AES-256.

NUNCA almacenar:
- Contraseñas de CSD en texto plano
- Archivos .key sin encriptar en DB

Uso:
    from src.services.fiscal.csd_vault import CSDVault
    
    vault = CSDVault(master_password=os.getenv('CSD_MASTER_KEY'))
    
    # Encriptar para almacenar
    encrypted_pass = vault.encrypt_password(csd_password)
    
    # Desencriptar solo para firmar
    password = vault.decrypt_password(encrypted_pass)
"""
from typing import Optional, Tuple
import base64
from datetime import datetime
import hashlib
import logging
import os
import secrets  # FIX 2026-02-01: For secure salt generation
from pathlib import Path

logger = logging.getLogger("CSD_VAULT")

# Intentar importar cryptography
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography no instalado. Ejecutar: pip install cryptography")

class CSDVault:
    """
    Bóveda segura para credenciales de Certificado de Sello Digital (CSD).

    Características:
    - Encriptación AES-256 (via Fernet)
    - Derivación de clave con PBKDF2
    - Los secretos solo se desencriptan en memoria cuando se necesitan
    """

    # FIX 2026-02-01: REMOVED hardcoded DEFAULT_SALT - must be configured per installation

    def __init__(self, master_password: str = None, salt: bytes = None):
        """
        Inicializa la bóveda.

        Args:
            master_password: Contraseña maestra para derivar la clave de encriptación
            salt: Salt para derivación (REQUERIDO via env var CSD_VAULT_SALT o parámetro)
        """
        if not HAS_CRYPTO:
            raise ImportError("Se requiere 'cryptography'. Ejecutar: pip install cryptography")

        # FIX 2026-02-01: REQUIRE master password - no insecure defaults
        if master_password is None:
            master_password = os.getenv('CSD_MASTER_KEY')
            if not master_password:
                raise ValueError(
                    "SECURITY ERROR: CSD_MASTER_KEY environment variable not configured. "
                    "Set a strong master password before using CSD vault."
                )

        # FIX 2026-02-01: REQUIRE salt - generate dynamically or from env
        if salt is None:
            salt_hex = os.getenv('CSD_VAULT_SALT')
            if salt_hex:
                salt = bytes.fromhex(salt_hex)
            else:
                # Generate new salt and warn user to save it
                salt = secrets.token_bytes(32)
                logger.warning(
                    "SECURITY: Generated new CSD_VAULT_SALT. Save this value: %s",
                    salt.hex()
                )
                logger.warning("Set CSD_VAULT_SALT environment variable for persistence!")

        self._salt = salt
        self._fernet = self._create_fernet(master_password)
    
    def _create_fernet(self, password: str) -> Fernet:
        """Crea cipher Fernet desde password usando PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=480000,  # OWASP recomendado
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def encrypt_password(self, password: str) -> str:
        """
        Encripta una contraseña de CSD.
        
        Args:
            password: Contraseña en texto plano
        
        Returns:
            String encriptado (base64) para almacenar en DB
        """
        if not password:
            return ''
        
        encrypted = self._fernet.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Desencripta una contraseña de CSD.
        
        IMPORTANTE: Solo llamar cuando se necesita firmar.
        Limpiar de memoria inmediatamente después.
        
        Args:
            encrypted_password: String encriptado de la DB
        
        Returns:
            Contraseña en texto plano
        """
        if not encrypted_password:
            return ''
        
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except (InvalidToken, Exception) as e:
            logger.error(f"Error desencriptando password: {e}")
            raise ValueError("No se pudo desencriptar la contraseña del CSD")
    
    def encrypt_file(self, file_path: str) -> bytes:
        """
        Encripta un archivo completo (.key o .cer).
        
        Args:
            file_path: Ruta al archivo
        
        Returns:
            Bytes encriptados para almacenar
        """
        with open(file_path, 'rb') as f:
            data = f.read()
        
        return self._fernet.encrypt(data)
    
    def decrypt_file(self, encrypted_data: bytes) -> bytes:
        """
        Desencripta un archivo en memoria.
        
        Returns:
            Bytes originales del archivo
        """
        try:
            return self._fernet.decrypt(encrypted_data)
        except InvalidToken:
            raise ValueError("No se pudo desencriptar el archivo CSD")
    
    def encrypt_and_save(self, source_path: str, dest_path: str) -> dict:
        """
        Encripta un archivo y lo guarda en disco.
        
        Args:
            source_path: Archivo original (.key)
            dest_path: Donde guardar el archivo encriptado
        
        Returns:
            {
                'success': bool,
                'encrypted_path': str,
                'original_hash': str (para verificación)
            }
        """
        # Leer original
        with open(source_path, 'rb') as f:
            original = f.read()
        
        # Hash del original para verificación
        original_hash = hashlib.sha256(original).hexdigest()
        
        # Encriptar
        encrypted = self._fernet.encrypt(original)
        
        # Guardar
        with open(dest_path, 'wb') as f:
            f.write(encrypted)
        
        return {
            'success': True,
            'encrypted_path': dest_path,
            'original_hash': original_hash
        }
    
    def load_and_decrypt(self, encrypted_path: str) -> bytes:
        """
        Carga un archivo encriptado y lo desencripta en memoria.
        """
        with open(encrypted_path, 'rb') as f:
            encrypted = f.read()
        
        return self._fernet.decrypt(encrypted)

class CSDManager:
    """
    Gestor de alto nivel para archivos CSD.
    Combina vault con metadatos y validaciones.
    """
    
    def __init__(self, vault: CSDVault, storage_path: str):
        """
        Args:
            vault: Instancia de CSDVault
            storage_path: Directorio donde se almacenan los CSD encriptados
        """
        self.vault = vault
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def import_csd(self, rfc: str, key_path: str, cer_path: str, 
                   password: str) -> dict:
        """
        Importa un CSD, encriptándolo para almacenamiento seguro.
        
        Args:
            rfc: RFC del emisor
            key_path: Ruta al archivo .key
            cer_path: Ruta al archivo .cer
            password: Contraseña del .key
        
        Returns:
            {
                'success': bool,
                'rfc': str,
                'encrypted_key_path': str,
                'encrypted_cer_path': str,
                'encrypted_password': str,
                'certificate_info': dict
            }
        """
        # Validar que los archivos existen
        if not os.path.exists(key_path):
            return {'success': False, 'error': f'Archivo .key no encontrado: {key_path}'}
        if not os.path.exists(cer_path):
            return {'success': False, 'error': f'Archivo .cer no encontrado: {cer_path}'}
        
        # Validar que la contraseña es correcta
        try:
            self._validate_key_password(key_path, password)
        except Exception as e:
            return {'success': False, 'error': f'Contraseña incorrecta: {e}'}
        
        # Crear directorio para este RFC
        rfc_dir = self.storage_path / rfc
        rfc_dir.mkdir(exist_ok=True)
        
        # Encriptar y guardar .key
        encrypted_key_path = rfc_dir / f"{rfc}.key.enc"
        self.vault.encrypt_and_save(key_path, str(encrypted_key_path))
        
        # Encriptar y guardar .cer
        encrypted_cer_path = rfc_dir / f"{rfc}.cer.enc"
        self.vault.encrypt_and_save(cer_path, str(encrypted_cer_path))
        
        # Encriptar password
        encrypted_password = self.vault.encrypt_password(password)
        
        # Extraer info del certificado
        cert_info = self._extract_certificate_info(cer_path)
        
        return {
            'success': True,
            'rfc': rfc,
            'encrypted_key_path': str(encrypted_key_path),
            'encrypted_cer_path': str(encrypted_cer_path),
            'encrypted_password': encrypted_password,
            'certificate_info': cert_info
        }
    
    def get_signing_credentials(self, rfc: str, encrypted_password: str) -> dict:
        """
        Obtiene credenciales desencriptadas para firmar.
        
        IMPORTANTE: Los datos retornados deben limpiarse de memoria
        inmediatamente después de usarse.
        
        Returns:
            {
                'key_bytes': bytes,
                'cer_bytes': bytes,
                'password': str
            }
        """
        rfc_dir = self.storage_path / rfc
        
        # Cargar y desencriptar .key
        key_path = rfc_dir / f"{rfc}.key.enc"
        key_bytes = self.vault.load_and_decrypt(str(key_path))
        
        # Cargar y desencriptar .cer
        cer_path = rfc_dir / f"{rfc}.cer.enc"
        cer_bytes = self.vault.load_and_decrypt(str(cer_path))
        
        # Desencriptar password
        password = self.vault.decrypt_password(encrypted_password)
        
        return {
            'key_bytes': key_bytes,
            'cer_bytes': cer_bytes,
            'password': password
        }
    
    def _validate_key_password(self, key_path: str, password: str):
        """Valida que el password abre el .key."""
        try:
            from OpenSSL import crypto
            
            with open(key_path, 'rb') as f:
                key_data = f.read()
            
            # Intentar cargar la llave privada
            crypto.load_privatekey(
                crypto.FILETYPE_ASN1,
                key_data,
                password.encode()
            )
        except ImportError:
            logger.warning("pyOpenSSL no disponible, saltando validación de password")
        except Exception as e:
            raise ValueError(f"No se pudo abrir el archivo .key: {e}")
    
    def _extract_certificate_info(self, cer_path: str) -> dict:
        """Extrae información del certificado."""
        try:
            from OpenSSL import crypto
            
            with open(cer_path, 'rb') as f:
                cer_data = f.read()
            
            cert = crypto.load_certificate(crypto.FILETYPE_ASN1, cer_data)
            
            return {
                'serial': cert.get_serial_number(),
                'subject': dict(cert.get_subject().get_components()),
                'not_before': cert.get_notBefore().decode(),
                'not_after': cert.get_notAfter().decode(),
                'issuer': dict(cert.get_issuer().get_components())
            }
        except ImportError:
            return {'error': 'pyOpenSSL no disponible'}
        except Exception as e:
            return {'error': str(e)}

# Función de conveniencia para uso rápido
def encrypt_csd_password(password: str) -> str:
    """
    Encripta una contraseña de CSD usando la clave maestra del ambiente.
    
    Uso:
        encrypted = encrypt_csd_password("mi_password")
        # Guardar encrypted en DB
    """
    vault = CSDVault()
    return vault.encrypt_password(password)

def decrypt_csd_password(encrypted: str) -> str:
    """
    Desencripta una contraseña de CSD.
    
    Uso:
        password = decrypt_csd_password(encrypted_from_db)
        # Usar password para firmar
        # Limpiar password de memoria
    """
    vault = CSDVault()
    return vault.decrypt_password(encrypted)

if __name__ == "__main__":
    import sys

    print("CSD Vault Test\n")

    # FIX 2026-02-04: Use environment variable instead of hardcoded password
    test_password = os.getenv("CSD_TEST_PASSWORD", "")
    if not test_password:
        print("Set CSD_TEST_PASSWORD environment variable for testing")
        sys.exit(1)

    vault = CSDVault(master_password=test_password)

    # Encriptar/desencriptar password
    original = "mi_password_csd_super_secreto"
    encrypted = vault.encrypt_password(original)
    decrypted = vault.decrypt_password(encrypted)

    print(f"Original: {original}")
    print(f"Encriptado: {encrypted[:50]}...")
    print(f"Desencriptado: {decrypted}")
    print(f"Match: {original == decrypted}")

    # Verificar que es diferente cada vez (Fernet usa IV aleatorio)
    encrypted2 = vault.encrypt_password(original)
    print(f"\nEncriptados iguales?: {encrypted == encrypted2} (debe ser False)")
