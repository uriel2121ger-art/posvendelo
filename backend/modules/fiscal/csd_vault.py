"""
🔐 Bóveda Segura para Archivos CSD
Encripta archivos .key y contraseñas con AES-256.

NUNCA almacenar:
- Contraseñas de CSD en texto plano
- Archivos .key sin encriptar en DB

Uso:
    from modules.fiscal.csd_vault import CSDVault
    
    vault = CSDVault(master_password=os.getenv('CSD_MASTER_KEY'))
    
    # Encriptar para almacenar
    encrypted_pass = await vault.encrypt_password(csd_password)
    
    # Desencriptar solo para firmar
    password = await vault.decrypt_password(encrypted_pass)
"""
from typing import Optional, Tuple
import asyncio
import base64
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import aiofiles

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

    # SECURITY: Salt should be unique per installation
    # Load from environment or generate and persist on first run
    _SALT_FILE = Path(__file__).parent.parent.parent / "data" / ".csd_vault_salt"

    @classmethod
    def _get_installation_salt(cls) -> bytes:
        """
        Get or generate installation-specific salt.
        Salt is persisted to ensure consistency across restarts.
        """
        try:
            if cls._SALT_FILE.exists():
                with open(cls._SALT_FILE, 'rb') as f:
                    return f.read()
        except Exception:
            pass

        # Generate new salt for this installation
        new_salt = os.urandom(32)
        try:
            cls._SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls._SALT_FILE, 'wb') as f:
                f.write(new_salt)
            # Restrict permissions (owner read/write only)
            os.chmod(cls._SALT_FILE, 0o600)
            logger.info("Generated new installation-specific salt for CSD vault")
        except Exception as e:
            logger.warning(f"Could not persist salt: {e}. Using ephemeral salt.")

        return new_salt

    def __init__(self, master_password: str = None, salt: bytes = None):
        """
        Inicializa la bóveda.
        
        Args:
            master_password: Contraseña maestra para derivar la clave de encriptación
            salt: Salt para derivación (opcional, usa default si no se provee)
        """
        if not HAS_CRYPTO:
            raise ImportError("Se requiere 'cryptography'. Ejecutar: pip install cryptography")
        
        # SECURITY: CSD_MASTER_KEY is MANDATORY - no defaults allowed
        # This key protects all CSD certificate passwords in the database
        if master_password is None:
            master_password = os.getenv('CSD_MASTER_KEY')
            if not master_password:
                # CRITICAL: Never use a hardcoded default for encryption keys
                # The previous hardcoded default was a severe security vulnerability
                raise ValueError(
                    "CRITICAL: CSD_MASTER_KEY environment variable is required. "
                    "This key encrypts all CSD certificate passwords. "
                    "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\" "
                    "and set it as CSD_MASTER_KEY in your environment."
                )
        
        self._master_password = master_password
        self._salt_param = salt
        self._salt = None
        self._fernet = None
        
    async def _ensure_initialized(self):
        if self._fernet is None:
            self._salt = self._salt_param or self._get_installation_salt()
            self._fernet = self._create_fernet(self._master_password)
    
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
    
    async def encrypt_password(self, password: str) -> str:
        """
        Encripta una contraseña de CSD.

        Args:
            password: Contraseña en texto plano

        Returns:
            String encriptado (base64) para almacenar en DB
        """
        if not password:
            return ''

        await self._ensure_initialized()
        encrypted = self._fernet.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    async def decrypt_password(self, encrypted_password: str) -> str:
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

        await self._ensure_initialized()
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except (InvalidToken, Exception) as e:
            logger.error(f"Error desencriptando password: {e}")
            raise ValueError("No se pudo desencriptar la contraseña del CSD")
    
    def _ensure_initialized_sync(self):
        """Synchronous initialization for non-async methods."""
        if self._fernet is None:
            self._salt = self._salt_param or self._get_installation_salt()
            self._fernet = self._create_fernet(self._master_password)

    def encrypt_file(self, file_path: str) -> bytes:
        """
        Encripta un archivo completo (.key o .cer).

        Args:
            file_path: Ruta al archivo

        Returns:
            Bytes encriptados para almacenar
        """
        self._ensure_initialized_sync()
        with open(file_path, 'rb') as f:
            data = f.read()

        return self._fernet.encrypt(data)

    def decrypt_file(self, encrypted_data: bytes) -> bytes:
        """
        Desencripta un archivo en memoria.

        Returns:
            Bytes originales del archivo
        """
        self._ensure_initialized_sync()
        try:
            return self._fernet.decrypt(encrypted_data)
        except InvalidToken:
            raise ValueError("No se pudo desencriptar el archivo CSD")
    
    async def encrypt_and_save(self, source_path: str, dest_path: str) -> dict:
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
        async with aiofiles.open(source_path, 'rb') as f:
            original = await f.read()

        # Hash del original para verificación
        original_hash = hashlib.sha256(original).hexdigest()

        await self._ensure_initialized()
        # Encriptar
        encrypted = self._fernet.encrypt(original)

        # Guardar
        async with aiofiles.open(dest_path, 'wb') as f:
            await f.write(encrypted)
        
        return {
            'success': True,
            'encrypted_path': dest_path,
            'original_hash': original_hash
        }
    
    def load_and_decrypt(self, encrypted_path: str) -> bytes:
        """
        Carga un archivo encriptado y lo desencripta en memoria.
        """
        self._ensure_initialized_sync()
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
    
    async def import_csd(self, rfc: str, key_path: str, cer_path: str, 
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
        # SECURITY: Validate file paths — allowlist approach (not blocklist)
        # Only accept files under /tmp or the CSD storage directory
        _allowed_bases = [
            Path('/tmp').resolve(),
            self.storage_path.resolve(),
        ]

        def _validate_path(file_path: str, expected_ext: str) -> Path:
            """Validate path is safe and has expected extension."""
            path = Path(file_path).resolve()
            # Check extension
            if not path.suffix.lower() == expected_ext:
                raise ValueError(f"File must have {expected_ext} extension")
            # Allowlist: path must be under an allowed base directory
            if not any(path.is_relative_to(base) for base in _allowed_bases):
                raise ValueError(
                    f"File path must be under /tmp or CSD storage directory. "
                    f"Got: {path}"
                )
            return path

        try:
            key_path = str(_validate_path(key_path, '.key'))
            cer_path = str(_validate_path(cer_path, '.cer'))
        except ValueError as e:
            return {'success': False, 'error': f'Ruta de archivo inválida: {e}'}

        # Validar que los archivos existen
        if not await asyncio.to_thread(os.path.exists, key_path):
            return {'success': False, 'error': 'Archivo .key no encontrado'}
        if not await asyncio.to_thread(os.path.exists, cer_path):
            return {'success': False, 'error': 'Archivo .cer no encontrado'}
        
        # Validar que la contraseña es correcta
        try:
            self._validate_key_password(key_path, password)
        except Exception as e:
            return {'success': False, 'error': f'Contraseña incorrecta: {e}'}
        
        # SECURITY: Validate RFC format to prevent directory traversal
        import re
        rfc_clean = rfc.upper().strip()
        if not re.match(r'^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$', rfc_clean):
            return {'success': False, 'error': 'Formato de RFC inválido'}

        # Crear directorio para este RFC (using sanitized RFC)
        rfc_dir = self.storage_path / rfc_clean
        rfc_dir.mkdir(exist_ok=True)
        
        # Encriptar y guardar .key
        encrypted_key_path = rfc_dir / f"{rfc}.key.enc"
        await self.vault.encrypt_and_save(key_path, str(encrypted_key_path))
        
        # Encriptar y guardar .cer
        encrypted_cer_path = rfc_dir / f"{rfc}.cer.enc"
        await self.vault.encrypt_and_save(cer_path, str(encrypted_cer_path))
        
        # Encriptar password
        encrypted_password = await self.vault.encrypt_password(password)
        
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
    
    async def get_signing_credentials(self, rfc: str, encrypted_password: str) -> dict:
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
        # SECURITY: Re-validate RFC even if it comes from DB (defense-in-depth)
        import re
        rfc_clean = rfc.upper().strip()
        if not re.match(r'^[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}$', rfc_clean):
            raise ValueError(f"Formato de RFC inválido: {rfc!r}")
        rfc_dir = self.storage_path / rfc_clean
        
        # Cargar y desencriptar .key
        key_path = rfc_dir / f"{rfc_clean}.key.enc"
        key_bytes = self.vault.load_and_decrypt(str(key_path))

        # Cargar y desencriptar .cer
        cer_path = rfc_dir / f"{rfc_clean}.cer.enc"
        cer_bytes = self.vault.load_and_decrypt(str(cer_path))
        
        # Desencriptar password
        password = await self.vault.decrypt_password(encrypted_password)
        
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
async def encrypt_csd_password(password: str) -> str:
    """
    Encripta una contraseña de CSD usando la clave maestra del ambiente.
    
    Uso:
        encrypted = await encrypt_csd_password("mi_password")
        # Guardar encrypted en DB
    """
    vault = CSDVault()
    return await vault.encrypt_password(password)

async def decrypt_csd_password(encrypted: str) -> str:
    """
    Desencripta una contraseña de CSD.
    
    Uso:
        password = await decrypt_csd_password(encrypted_from_db)
        # Usar password para firmar
        # Limpiar password de memoria
    """
    vault = CSDVault()
    return await vault.decrypt_password(encrypted)

if __name__ == "__main__":
    import asyncio
    async def main():
        # SECURITY: This test block should only run in development
        import sys
    
        if os.getenv("TITAN_ENVIRONMENT", "development") == "production":
            print("❌ ERROR: Cannot run CSD Vault tests in production environment")
            sys.exit(1)
    
        print("🔐 CSD Vault Test (Development Only)\n")
    
        # Require explicit test key from environment or prompt
        test_key = os.getenv("CSD_TEST_KEY")
        if not test_key:
            print("⚠️  Set CSD_TEST_KEY environment variable for testing")
            print("   Example: export CSD_TEST_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')")
            sys.exit(1)
    
        vault = CSDVault(master_password=test_key)
    
        # Encriptar/desencriptar password
        original = "test_password_example"
        encrypted = await vault.encrypt_password(original)
        decrypted = await vault.decrypt_password(encrypted)
    
        print(f"Original length: {len(original)}")
        print(f"Encrypted length: {len(encrypted)}")
        print(f"✅ Round-trip match: {original == decrypted}")
    
        # Verificar que es diferente cada vez (Fernet usa IV aleatorio)
        encrypted2 = await vault.encrypt_password(original)
        print(f"✅ Unique ciphertexts: {encrypted != encrypted2}")
        
    asyncio.run(main())
