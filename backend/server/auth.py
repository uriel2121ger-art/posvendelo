"""
TITAN Gateway - Authentication

Token verification and authorization.
FIX 2026-02-01: Eliminado token por defecto, agregado secrets.compare_digest
"""
import json
import os
import secrets
import logging
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Header

logger = logging.getLogger(__name__)

DATA_DIR = Path("./gateway_data")
CONFIG_FILE = DATA_DIR / "config.json"
TOKENS_FILE = DATA_DIR / "tokens.json"


def load_config():
    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        # Verificar si tiene token configurado
        if config.get("admin_token") in (None, "", "change_me_in_production"):
            # Intentar obtener de variable de entorno
            env_token = os.environ.get("TITAN_GATEWAY_ADMIN_TOKEN")
            if env_token and len(env_token) >= 32:
                config["admin_token"] = env_token
            else:
                # FIX 2026-02-01: No usar valor por defecto inseguro
                logger.error("TITAN_GATEWAY_ADMIN_TOKEN not configured!")
                config["admin_token"] = None
        return config
    # FIX 2026-02-01: Sin archivo de config, requerir variable de entorno
    env_token = os.environ.get("TITAN_GATEWAY_ADMIN_TOKEN")
    if not env_token or len(env_token) < 32:
        logger.error("Gateway config not found and TITAN_GATEWAY_ADMIN_TOKEN not set!")
        return {"admin_token": None, "branches": {}}
    return {"admin_token": env_token, "branches": {}}

def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')

def load_tokens():
    if TOKENS_FILE.exists():
        return json.loads(TOKENS_FILE.read_text(encoding='utf-8'))
    return {}

def save_tokens(tokens):
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2, ensure_ascii=False), encoding='utf-8')

def _secure_compare(provided: str, expected: str) -> bool:
    """
    Comparación segura de tokens que previene timing attacks.
    FIX 2026-02-01: Usar secrets.compare_digest en lugar de ==
    """
    if not provided or not expected:
        return False
    try:
        return secrets.compare_digest(provided.encode(), expected.encode())
    except Exception as e:
        logger.warning("Secure compare failed: %s", e)
        return False


async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify Bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token requerido")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato de token inválido")

    token = authorization.replace("Bearer ", "")

    config = load_config()
    tokens = load_tokens()

    admin_token = config.get("admin_token")

    # FIX 2026-02-01: Verificar que admin_token esté configurado
    if not admin_token:
        logger.error("Admin token not configured - rejecting all auth attempts")
        raise HTTPException(status_code=500, detail="Server authentication not configured")

    # FIX 2026-02-01: Usar comparación segura contra timing attacks
    if _secure_compare(token, admin_token):
        return {"role": "admin", "branch_id": None}

    # Check branch tokens (también con comparación segura)
    for branch_id, branch_token in tokens.items():
        if _secure_compare(token, branch_token):
            return {"role": "branch", "branch_id": int(branch_id)}

    raise HTTPException(status_code=401, detail="Token inválido")


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    FIX 2026-02-04: For endpoints that work with or without authentication.
    """
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "")

    config = load_config()
    tokens = load_tokens()

    admin_token = config.get("admin_token")

    if admin_token and _secure_compare(token, admin_token):
        return {"role": "admin", "branch_id": None}

    for branch_id, branch_token in tokens.items():
        if _secure_compare(token, branch_token):
            return {"role": "branch", "branch_id": int(branch_id)}

    return None
