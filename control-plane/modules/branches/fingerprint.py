import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Weights for fingerprint matching
WEIGHTS = {
    "board_serial": 3,
    "cpu_model": 2,
    "mac_primary": 2,
    "disk_serial": 2,
    "board_name": 1,
}
MATCH_THRESHOLD = 5
MAX_TOTAL = sum(WEIGHTS.values())  # 10

# Values that indicate missing/generic hardware
INVALID_SERIALS = {
    "", "default string", "default", "to be filled by o.e.m.",
    "not specified", "none", "n/a", "0", "system serial number",
    "chassis serial number", "bsn12345678901234567",
}


def _hash_component(value: str | None) -> str | None:
    """SHA-256 hash a hardware component value, returning None for empty/invalid."""
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in INVALID_SERIALS:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_hw_info(hw_info: dict[str, str | None]) -> dict[str, str | None]:
    """Hash all hardware components from raw hw_info dict."""
    return {
        "board_serial_hash": _hash_component(hw_info.get("board_serial")),
        "board_name_hash": _hash_component(hw_info.get("board_name")),
        "cpu_model_hash": _hash_component(hw_info.get("cpu_model")),
        "mac_primary_hash": _hash_component(hw_info.get("mac_primary")),
        "disk_serial_hash": _hash_component(hw_info.get("disk_serial")),
    }


def compute_match_score(stored: dict, incoming: dict) -> int:
    """
    Compute similarity score between stored fingerprint and incoming hw_info.
    Each matching non-null hash adds its weight to the score.
    """
    score = 0
    field_map = {
        "board_serial_hash": "board_serial",
        "board_name_hash": "board_name",
        "cpu_model_hash": "cpu_model",
        "mac_primary_hash": "mac_primary",
        "disk_serial_hash": "disk_serial",
    }
    for hash_field, weight_key in field_map.items():
        stored_val = stored.get(hash_field)
        incoming_val = incoming.get(hash_field)
        if stored_val and incoming_val and stored_val == incoming_val:
            score += WEIGHTS[weight_key]
    return score


async def find_matching_fingerprint(db, hashed: dict[str, str | None]) -> dict | None:
    """
    Find existing fingerprint matching the incoming hardware info.
    Uses weighted scoring - returns best match above threshold.
    """
    # Build conditions for any non-null hash
    conditions = []
    params: dict[str, Any] = {}
    for field in ["board_serial_hash", "board_name_hash", "cpu_model_hash", "mac_primary_hash", "disk_serial_hash"]:
        if hashed.get(field):
            conditions.append(f"{field} = :{field}")
            params[field] = hashed[field]

    if not conditions:
        return None

    # Find candidates that match at least one component
    where_clause = " OR ".join(conditions)
    candidates = await db.fetch(
        f"""
        SELECT
            hf.id,
            hf.tenant_id,
            hf.branch_id,
            hf.board_serial_hash,
            hf.board_name_hash,
            hf.cpu_model_hash,
            hf.mac_primary_hash,
            hf.disk_serial_hash,
            b.install_token,
            b.cloud_activated,
            t.is_anonymous,
            t.slug AS tenant_slug
        FROM hardware_fingerprints hf
        JOIN branches b ON b.id = hf.branch_id
        JOIN tenants t ON t.id = hf.tenant_id
        WHERE {where_clause}
        ORDER BY hf.created_at DESC
        LIMIT 20
        """,
        params,
    )

    best_match = None
    best_score = 0
    for candidate in candidates:
        score = compute_match_score(dict(candidate), hashed)
        if score >= MATCH_THRESHOLD and score > best_score:
            best_score = score
            best_match = dict(candidate)
            best_match["match_score"] = score

    if best_match:
        logger.info(
            "Fingerprint match: branch_id=%s score=%d/%d",
            best_match["branch_id"], best_score, MAX_TOTAL,
        )
    return best_match
