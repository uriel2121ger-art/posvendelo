"""
Hardware fingerprint collection for auto-registration with control-plane.

Reads DMI info from /sys/class/dmi/id (Linux) — inside Docker requires
bind mount of the host's /sys/class/dmi/id directory.
"""

import logging
import platform
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def collect_hw_info() -> dict:
    """Collect hardware fingerprint matching control-plane pre-register schema."""
    info: dict = {}

    # DMI paths (Linux — inside Docker needs bind mount of /sys/class/dmi/id)
    _invalid_dmi = {
        "", "to be filled by o.e.m.", "default string", "none", "0",
        "n/a", "not applicable", "not specified", "system serial number",
        "chassis serial number", "base board serial number",
    }
    dmi_fields = [
        ("board_serial", "/sys/class/dmi/id/board_serial"),
        ("board_name", "/sys/class/dmi/id/board_name"),
        ("board_vendor", "/sys/class/dmi/id/board_vendor"),
        ("product_name", "/sys/class/dmi/id/product_name"),
        ("product_serial", "/sys/class/dmi/id/product_serial"),
    ]
    for key, path in dmi_fields:
        try:
            value = Path(path).read_text().strip()
            if value and value.lower() not in _invalid_dmi:
                info[key] = value
        except (OSError, PermissionError):
            pass

    # CPU model
    cpu = platform.processor()
    if not cpu:
        # Fallback: read from /proc/cpuinfo
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
    if cpu:
        info["cpu_model"] = cpu

    # Primary MAC address
    try:
        mac_int = uuid.getnode()
        # uuid.getnode() returns random MAC if real one not found — check bit 1 of first octet
        if not (mac_int >> 41) & 1:  # bit 1 = 0 → universally administered = real HW MAC
            info["mac_primary"] = ":".join(
                f"{(mac_int >> i) & 0xFF:02x}" for i in range(40, -1, -8)
            )
    except Exception:
        pass

    return info
