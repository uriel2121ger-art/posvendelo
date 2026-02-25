"""
TITAN POS - Shared Rate Limiter

Single limiter instance shared between main.py and route modules.
Uses slowapi with get_remote_address as the key function.
"""

import logging
import os

logger = logging.getLogger(__name__)

limiter = None

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    debug = os.getenv("DEBUG", "false").lower() == "true"
    # 5x multiplier in DEBUG to avoid 429 in E2E tests
    _default_limit = "25/minute" if debug else "5/minute"

    limiter = Limiter(key_func=get_remote_address, default_limits=[_default_limit])
except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled")
