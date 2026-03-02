"""
TITAN POS - Shared Rate Limiter

Single limiter instance shared between main.py and route modules.
Uses slowapi with get_remote_address as the key function.
Includes PIN-specific rate limiter to prevent brute-force on 4-digit PINs.
"""

import logging
import os
import time
import threading

logger = logging.getLogger(__name__)

limiter = None

try:
    from slowapi import Limiter
    from starlette.requests import Request

    debug = os.getenv("DEBUG", "false").lower() == "true"
    # 5x multiplier in DEBUG to avoid 429 in E2E tests
    _default_limit = "25/minute" if debug else "5/minute"

    def _get_real_client_ip(request: Request) -> str:
        """Use only the actual TCP connection IP, ignoring X-Forwarded-For.
        POS runs on LAN without reverse proxy — spoofed headers must be ignored."""
        return request.client.host if request.client else "127.0.0.1"

    limiter = Limiter(key_func=_get_real_client_ip, default_limits=[_default_limit])
except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled")


# ---------------------------------------------------------------------------
# PIN brute-force protection (in-memory, per-IP)
# 4-digit PINs have only 10,000 combos — strict limits are essential
# ---------------------------------------------------------------------------

_pin_attempts: dict = {}  # ip -> list of timestamps
_pin_lock = threading.Lock()
_PIN_WINDOW = 300   # 5 minutes
_PIN_MAX = 5        # max attempts per window (10 in debug)
_PIN_MAX_ACTUAL = 10 if os.getenv("DEBUG", "false").lower() == "true" else _PIN_MAX


def check_pin_rate_limit(client_ip: str) -> None:
    """Raise HTTPException(429) if too many PIN attempts from this IP."""
    from fastapi import HTTPException

    now = time.time()
    with _pin_lock:
        attempts = _pin_attempts.get(client_ip, [])
        attempts = [t for t in attempts if now - t < _PIN_WINDOW]
        if len(attempts) >= _PIN_MAX_ACTUAL:
            _pin_attempts[client_ip] = attempts
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos de PIN. Intente en 5 minutos.",
            )
        attempts.append(now)
        _pin_attempts[client_ip] = attempts
