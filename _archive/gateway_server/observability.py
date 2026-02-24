"""
Minimal structured observability for gateway operations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("TITAN_GATEWAY")
DATA_DIR = Path("./gateway_data")
DATA_DIR.mkdir(exist_ok=True)
EVENTS_FILE = DATA_DIR / "events.jsonl"


def emit_event(event: str, level: str = "info", **fields: Dict[str, Any]) -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        "level": level,
        **fields,
    }
    try:
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.debug("Failed to persist event: %s", exc)

    line = json.dumps(payload, ensure_ascii=False)
    if level == "error":
        logger.error(line)
    elif level == "warning":
        logger.warning(line)
    else:
        logger.info(line)

