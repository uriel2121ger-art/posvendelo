"""
POSVENDELO - Shared PIN Authentication

Verificación de PIN de gerente reutilizable para endpoints que requieren
autorización de un manager/admin/owner mediante PIN.

Usage:
    from modules.shared.pin_auth import verify_manager_pin

    async with get_connection() as db:
        mgr = await verify_manager_pin(pin, db.connection)
        # mgr["id"] contiene el user_id del manager que autorizó
"""

import hashlib
import hmac
import logging

import bcrypt
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Consulta SQL para obtener usuarios con PIN activos y con rol de autorización
# IMPORTANT: The roles listed in this SQL WHERE clause ('admin', 'manager', 'owner')
# must stay synchronized with PRIVILEGED_ROLES in modules.shared.constants.
# If you add/remove roles from PRIVILEGED_ROLES, update this query accordingly.
# ---------------------------------------------------------------------------
_PIN_QUERY = (
    "SELECT id, pin_hash FROM users "
    "WHERE is_active = 1 "
    "AND role IN ('admin', 'manager', 'owner') "
    "AND pin_hash IS NOT NULL"
)


async def verify_manager_pin(pin: str, conn) -> dict:
    """Verificar que un PIN corresponde a un gerente/admin/owner activo.

    Intenta bcrypt primero (hashes modernos que empiezan con $2b$ / $2a$).
    Si el hash no es bcrypt, hace fallback a SHA-256 con comparación timing-safe
    (hmac.compare_digest) para soportar hashes legados.

    Args:
        pin:  PIN en texto plano enviado por el cliente.
        conn: Conexión asyncpg raw (NO el wrapper db — pasar db.connection).

    Returns:
        dict con al menos ``id`` y ``pin_hash`` del usuario que coincidió.

    Raises:
        HTTPException(403): Si ningún usuario activo tiene un PIN que coincida.
    """
    rows = await conn.fetch(_PIN_QUERY)

    # Always iterate ALL rows to prevent timing-based user enumeration.
    # Do NOT early-return inside the loop.
    matched_row = None
    for row in rows:
        stored: str = row["pin_hash"]
        try:
            if stored.startswith("$2b$") or stored.startswith("$2a$"):
                # Hash bcrypt moderno
                if bcrypt.checkpw(pin.encode(), stored.encode()) and matched_row is None:
                    matched_row = dict(row)
            else:
                # Hash SHA-256 legado — comparación timing-safe
                candidate = hashlib.sha256(pin.encode()).hexdigest()
                if hmac.compare_digest(candidate, stored) and matched_row is None:
                    matched_row = dict(row)
        except Exception:
            # Hash corrupto o formato inesperado — ignorar y continuar
            logger.warning("Error al verificar pin_hash para user_id=%s", row.get("id"))
            continue

    if matched_row is not None:
        return matched_row
    raise HTTPException(status_code=403, detail="PIN de gerente inválido")
