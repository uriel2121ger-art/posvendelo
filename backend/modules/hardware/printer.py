"""
POSVENDELO — CUPS Printer Service

Discover printers, send raw ESC/POS data, open cash drawer.
All operations run in executor to avoid blocking the async event loop.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import subprocess

logger = logging.getLogger(__name__)

_PRINTER_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_printer(name: str) -> str:
    """Validate printer name to prevent command injection."""
    name = name.strip()
    if not name or not _PRINTER_RE.match(name):
        raise ValueError(f"Nombre de impresora inválido: {name!r}")
    return name


# ---------------------------------------------------------------------------
# Synchronous helpers (run inside executor)
# ---------------------------------------------------------------------------

def _list_printers_sync() -> list[dict]:
    """Parse lpstat -p -d to discover CUPS printers (EN/ES locale)."""
    printers: list[dict] = []
    default_printer = ""

    try:
        result = subprocess.run(
            ["lpstat", "-p", "-d"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            low = line.lower()
            # EN: "printer NAME ..." / ES: "la impresora NAME ..."
            if low.startswith("printer ") or low.startswith("la impresora "):
                parts = line.split()
                # Name is always the word after "printer" or "impresora"
                name_idx = 1 if low.startswith("printer ") else 2
                if len(parts) > name_idx:
                    name = parts[name_idx]
                    is_enabled = "enabled" in low or "activada" in low
                    is_disabled = "disabled" in low or "deshabilitada" in low
                    printers.append({
                        "name": name,
                        "display_name": name,
                        "enabled": is_enabled and not is_disabled,
                        "status": "idle" if (is_enabled and not is_disabled) else "disabled",
                        "is_default": False,
                    })
            # EN: "system default destination:" / ES: "destino predeterminado del sistema:"
            elif "default destination:" in low or "destino predeterminado" in low:
                default_printer = line.split(":", 1)[1].strip()
    except FileNotFoundError:
        logger.warning("lpstat not found — CUPS not installed?")
    except subprocess.TimeoutExpired:
        logger.warning("lpstat timed out")
    except Exception as e:
        logger.error("Error listing printers: %s", e)

    for p in printers:
        if p["name"] == default_printer:
            p["is_default"] = True

    return printers


def _print_raw_sync(printer: str, data: bytes) -> None:
    """Send raw bytes to a CUPS printer via lp."""
    printer = _validate_printer(printer)
    subprocess.run(
        ["lp", "-d", printer, "-o", "raw", "-"],
        input=data, check=True, timeout=10,
    )


def _open_drawer_sync(printer: str, pulse_hex: str) -> None:
    """Send ESC/POS cash drawer pulse via lp/CUPS."""
    printer = _validate_printer(printer)
    cleaned = pulse_hex.replace("\\x", "").replace("0x", "").replace(" ", "").strip()
    try:
        pulse_bytes = bytes.fromhex(cleaned) if cleaned else b""
    except ValueError:
        logger.warning("Invalid pulse_hex %r, using default", pulse_hex)
        pulse_bytes = b""
    if not pulse_bytes:
        pulse_bytes = b"\x1B\x70\x00\x19\xFA"
    subprocess.run(
        ["lp", "-d", printer, "-o", "raw", "-"],
        input=pulse_bytes, check=True, timeout=10,
    )


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------

async def list_printers() -> list[dict]:
    """Discover CUPS printers (async wrapper)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _list_printers_sync)


async def print_raw(printer: str, data: bytes) -> None:
    """Send raw ESC/POS data to printer (async wrapper)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, functools.partial(_print_raw_sync, printer, data)
    )


async def open_drawer(printer: str, pulse_hex: str = "1B700019FA") -> None:
    """Open cash drawer via ESC/POS pulse (async wrapper)."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, functools.partial(_open_drawer_sync, printer, pulse_hex)
    )
