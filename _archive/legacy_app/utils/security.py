"""
Security utilities for TITAN POS
Generates secure passwords, tokens, and keys for production use
"""

import hashlib
import logging
import os
from pathlib import Path
import secrets
import string

logger = logging.getLogger(__name__)


def generate_secure_password(length: int = 16) -> str:
    """
    Generate a secure random password.
    
    Args:
        length: Password length (default 16, minimum 12)
    
    Returns:
        Secure random password with mixed characters
    """
    if length < 12:
        length = 12
    
    # Ensure at least one of each character type
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    
    # Generate password ensuring complexity
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        # Verify it has at least: 1 upper, 1 lower, 1 digit, 1 special
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*" for c in password)
        
        if has_upper and has_lower and has_digit and has_special:
            return password

def generate_secret_key(length: int = 32) -> str:
    """
    Generate a cryptographically secure secret key.
    
    Args:
        length: Key length in bytes (default 32 = 256 bits)
    
    Returns:
        Hex-encoded random key
    """
    return secrets.token_hex(length)

def generate_admin_token() -> str:
    """
    Generate a secure admin API token.
    
    Returns:
        URL-safe random token
    """
    return secrets.token_urlsafe(32)

def hash_password_sha256(password: str) -> str:
    """
    Hash a password using SHA256.
    
    Note: For new passwords, use bcrypt instead.
    This is for compatibility with existing system.
    
    Args:
        password: Plain text password
    
    Returns:
        SHA256 hex digest
    """
    return hashlib.sha256(password.encode()).hexdigest()

def create_env_file(env_path: Path, overwrite: bool = False) -> dict:
    """
    Create .env file with secure random values.
    
    Args:
        env_path: Path to .env file
        overwrite: If True, regenerate even if exists
    
    Returns:
        Dictionary with generated values
    """
    if env_path.exists() and not overwrite:
        # Read existing values
        values = {}
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    values[key] = value.strip('"\'')
        return values
    
    # Generate new values
    values = {
        'SECRET_KEY': generate_secret_key(),
        'ADMIN_TOKEN': generate_admin_token(),
        'JWT_SECRET': generate_secret_key(16),
    }
    
    # Write .env file
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("# TITAN POS - Security Configuration\n")
        f.write("# Generated automatically during installation\n")
        f.write("# DO NOT SHARE OR COMMIT TO VERSION CONTROL\n\n")

        for key, value in values.items():
            f.write(f'{key}="{value}"\n')
    
    # Set restrictive permissions (owner read/write only)
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass  # Windows doesn't support chmod
    
    return values

def create_admin_credentials(config_path: Path) -> dict:
    """
    Create secure admin credentials and save to config.
    
    Args:
        config_path: Path to config.json
    
    Returns:
        Dictionary with username and plain password (show to user once)
    """
    import json

    # Generate credentials
    username = "admin"
    password = generate_secure_password(16)
    password_hash = hash_password_sha256(password)
    
    # Load or create config
    config = {}
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            import logging
            logging.getLogger(__name__).warning(f"Error loading config: {e}")
    
    # Update with secure credentials
    config['admin_user'] = username
    config['admin_pass_hash'] = password_hash
    # Remove old plain text password if exists
    config.pop('admin_pass', None)
    
    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    return {
        'username': username,
        'password': password,  # Plain text - show to user ONCE
        'password_hash': password_hash
    }

# For command-line use during installation
if __name__ == "__main__":
    # FIX 2026-02-04: Use logging.debug instead of print for sensitive data
    logging.basicConfig(level=logging.DEBUG)

    logger.info("=" * 60)
    logger.info("TITAN POS - Security Credentials Generator")
    logger.info("=" * 60)

    # Generate credentials - only show truncated hashes in debug
    password = generate_secure_password()
    password_hash = hash_password_sha256(password)

    # FIX 2026-02-04: Truncate more aggressively and use debug level
    logger.debug(f"Generated admin password hash: {password_hash[:8]}...")
    logger.debug(f"Generated SECRET_KEY hash: {generate_secret_key()[:8]}...")
    logger.debug(f"Generated ADMIN_TOKEN prefix: {generate_admin_token()[:8]}...")

    logger.info("Credentials generated. Check debug logs for truncated values.")
    logger.info("Save these credentials securely!")
    logger.info("=" * 60)
