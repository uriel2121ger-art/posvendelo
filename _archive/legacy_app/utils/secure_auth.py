"""
TITAN POS - Sistema de Autenticacion Seguro
Implementa hashing robusto de contrasenias y manejo de sesiones.
Thread-safe implementation.
"""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import secrets  # Also used for constant-time comparison (compare_digest)
import threading
import time
from typing import Optional, Tuple


class SecureAuth:
    """Sistema de autenticación con hashing robusto"""
    
    def __init__(self, salt_rounds: int = 12):
        """
        Args:
            salt_rounds: Número de rondas para bcrypt (más = más seguro pero más lento)
        """
        self.salt_rounds = salt_rounds
        self.sessions = {}
        self.session_timeout = 3600  # 1 hora por defecto
        
        # Intentar usar bcrypt, fallback a hashlib si no está disponible
        try:
            import bcrypt
            self.use_bcrypt = True
            self.bcrypt = bcrypt
        except ImportError:
            self.use_bcrypt = False
            print("⚠️ bcrypt no disponible, usando hashlib (menos seguro)")
    
    def hash_password(self, password: str) -> str:
        """
        Hash seguro de contraseña
        Returns: String hasheado para guardar en BD
        """
        if self.use_bcrypt:
            # BCrypt con salt automático
            salt = self.bcrypt.gensalt(rounds=self.salt_rounds)
            hashed = self.bcrypt.hashpw(password.encode('utf-8'), salt)
            return hashed.decode('utf-8')
        else:
            # Fallback: SHA-256 con salt manual
            salt = secrets.token_hex(16)
            password_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000  # 100k iteraciones
            )
            return f"sha256${salt}${password_hash.hex()}"
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verifica contraseña contra hash
        Returns: True si coincide
        """
        if not hashed:
            return False
            
        if self.use_bcrypt and not hashed.startswith('sha256$'):
            # Usar bcrypt
            try:
                return self.bcrypt.checkpw(
                    password.encode('utf-8'),
                    hashed.encode('utf-8')
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Bcrypt verification failed: {e}")
                return False
        else:
            # Fallback SHA-256 with PBKDF2
            try:
                parts = hashed.split('$')
                if len(parts) != 3 or parts[0] != 'sha256':
                    # SECURITY: MD5 hashes are NO LONGER SUPPORTED
                    # MD5 is cryptographically broken (collisions since 2004)
                    # Rainbow tables can crack MD5 passwords in seconds
                    # Users with MD5 hashes MUST reset their password
                    import logging
                    logging.getLogger(__name__).critical(
                        "SECURITY: Attempted login with MD5 hash detected. "
                        "MD5 passwords are no longer supported. User must reset password."
                    )
                    # SECURITY: Return False - do not authenticate with broken crypto
                    return False

                salt = parts[1]
                stored_hash = parts[2]

                password_hash = hashlib.pbkdf2_hmac(
                    'sha256',
                    password.encode('utf-8'),
                    salt.encode('utf-8'),
                    100000
                )
                # SECURITY: Use constant-time comparison to prevent timing attacks
                return secrets.compare_digest(password_hash.hex(), stored_hash)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"SHA256 verification failed: {e}")
                return False
    
    def create_session(self, user_id: int, username: str, role: str = "cashier") -> str:
        """
        Crea sesión de usuario con token único
        Returns: Token de sesión
        """
        # Generar token único
        token = secrets.token_urlsafe(32)
        
        self.sessions[token] = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'created_at': time.time(),
            'last_activity': time.time(),
            'ip': None  # Podría capturar IP en futuro
        }
        
        return token
    
    def validate_session(self, token: str) -> Optional[dict]:
        """
        Valida token de sesión y verifica timeout
        Returns: Datos de sesión si es válida, None si expiró
        """
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        current_time = time.time()
        
        # Verificar timeout
        if current_time - session['last_activity'] > self.session_timeout:
            # Sesión expirada
            del self.sessions[token]
            return None
        
        # Actualizar última actividad
        session['last_activity'] = current_time
        
        return session
    
    def destroy_session(self, token: str):
        """Destruye sesión (logout)"""
        if token in self.sessions:
            del self.sessions[token]
    
    def cleanup_expired_sessions(self):
        """Limpia sesiones expiradas"""
        current_time = time.time()
        expired = [
            token for token, session in self.sessions.items()
            if current_time - session['last_activity'] > self.session_timeout
        ]
        
        for token in expired:
            del self.sessions[token]
        
        return len(expired)
    
    def set_session_timeout(self, seconds: int):
        """Configura timeout de sesión"""
        self.session_timeout = seconds
    
    def get_active_sessions(self) -> list:
        """Retorna lista de sesiones activas"""
        return [
            {
                'username': s['username'],
                'role': s['role'],
                'created_at': datetime.fromtimestamp(s['created_at']).isoformat(),
                'last_activity': datetime.fromtimestamp(s['last_activity']).isoformat()
            }
            for s in self.sessions.values()
        ]

class AuditLog:
    """Sistema de logs de auditoria persistentes. Thread-safe."""

    def __init__(self, log_dir: str = "logs/audit"):
        import logging
        self._logger = logging.getLogger(__name__)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Thread-safe file access
        self._lock = threading.Lock()
        self._current_log = None
        self._current_date = None
        self._open_log()

    def _open_log(self) -> None:
        """Abre archivo de log diario. Must hold _lock."""
        # Close previous log if exists
        self._close_current()

        date_str = datetime.now().strftime("%Y-%m-%d")
        self._current_date = date_str
        log_file = self.log_dir / f"audit_{date_str}.jsonl"

        try:
            self._current_log = open(log_file, 'a', encoding='utf-8', buffering=1)
        except Exception as e:
            self._logger.error(f"Failed to open audit log {log_file}: {e}")
            self._current_log = None

    def _close_current(self) -> None:
        """Close current log file if open. Must hold _lock or be in __init__."""
        if self._current_log is not None:
            try:
                self._current_log.flush()
                self._current_log.close()
            except Exception as e:
                self._logger.debug(f"Error closing audit log: {e}")
            finally:
                self._current_log = None

    def _ensure_current_log(self) -> bool:
        """Ensure log file is open and current. Must hold _lock."""
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Check if we need to rotate to a new day's log
        if self._current_date != current_date or self._current_log is None:
            self._open_log()

        return self._current_log is not None

    def close(self) -> None:
        """Cierra el archivo de log correctamente. Thread-safe."""
        with self._lock:
            self._close_current()

    def __del__(self):
        """Destructor para asegurar cierre del archivo."""
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures file is closed."""
        self.close()
        return False

    def log(self, action: str, user_id: int, username: str, details: dict = None) -> None:
        """
        Registra accion en log de auditoria. Thread-safe.

        Args:
            action: Tipo de accion (LOGIN, SALE, PRODUCT_CREATE, etc)
            user_id: ID del usuario
            username: Nombre del usuario
            details: Detalles adicionales
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'user_id': user_id,
            'username': username,
            'details': details or {}
        }

        with self._lock:
            if not self._ensure_current_log():
                self._logger.error("Cannot write audit log: file not available")
                return

            try:
                self._current_log.write(json.dumps(entry, ensure_ascii=False) + '\n')
                self._current_log.flush()
            except Exception as e:
                self._logger.error(f"Failed to write audit log: {e}")
                # Try to reopen and write again
                self._open_log()
                if self._current_log:
                    try:
                        self._current_log.write(json.dumps(entry, ensure_ascii=False) + '\n')
                        self._current_log.flush()
                    except Exception as e2:
                        self._logger.error(f"Failed to write audit log after reopen: {e2}")

    def search_logs(
        self,
        user_id: int = None,
        action: str = None,
        date_from: str = None,
        limit: int = 100
    ) -> list:
        """
        Busca en logs de auditoria. Thread-safe.

        Returns: Lista de entradas que coinciden
        """
        results = []

        # Determinar archivos a buscar
        if date_from:
            try:
                start_date = datetime.fromisoformat(date_from).date()
            except ValueError:
                start_date = (datetime.now() - timedelta(days=7)).date()
        else:
            start_date = (datetime.now() - timedelta(days=7)).date()

        current_date = datetime.now().date()

        # Buscar en cada archivo de log
        date = start_date
        while date <= current_date:
            log_file = self.log_dir / f"audit_{date.isoformat()}.jsonl"

            if log_file.exists():
                try:
                    with open(log_file, encoding='utf-8') as f:
                        for line in f:
                            try:
                                entry = json.loads(line)

                                # Filtrar
                                if user_id and entry.get('user_id') != user_id:
                                    continue
                                if action and entry.get('action') != action:
                                    continue

                                results.append(entry)

                                if len(results) >= limit:
                                    return results
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    self._logger.debug(f"Error reading log file {log_file}: {e}")

            date += timedelta(days=1)

        return results

# Instancias globales
secure_auth = SecureAuth()
audit_log = AuditLog()
