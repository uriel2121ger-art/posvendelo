import logging

from audit import log_audit_event
from modules.tunnel.cloudflare import provision_tunnel

logger = logging.getLogger(__name__)


async def ensure_tunnel_provisioned(db, *, branch_id: int, branch_slug: str) -> dict | None:
    """
    Provision a tunnel for a branch if not already provisioned.
    Idempotent: skips if tunnel_token already exists.
    Returns provisioning result dict or None if already provisioned.
    """
    existing = await db.fetchrow(
        "SELECT tunnel_token, tunnel_status FROM branches WHERE id = :branch_id",
        {"branch_id": branch_id},
    )
    if existing and existing.get("tunnel_token") and existing.get("tunnel_status") == "active":
        logger.debug("Tunnel already provisioned for branch %d", branch_id)
        return None

    try:
        provisioned = await provision_tunnel(branch_slug)
    except Exception as exc:
        logger.error("Tunnel provision failed for branch %d: %s", branch_id, exc)
        await db.execute(
            """
            UPDATE branches
            SET tunnel_status = 'error', tunnel_last_error = :error, updated_at = NOW()
            WHERE id = :branch_id
            """,
            {"branch_id": branch_id, "error": str(exc)[:500]},
        )
        raise

    tunnel_id = provisioned["tunnel_id"]
    tunnel_token = provisioned["tunnel_token"]
    tunnel_url = provisioned["tunnel_url"]

    await db.execute(
        """
        INSERT INTO tunnel_configs (branch_id, tunnel_name, tunnel_id, tunnel_url)
        VALUES (:branch_id, :tunnel_name, :tunnel_id, :tunnel_url)
        ON CONFLICT (branch_id) DO UPDATE SET
            tunnel_name = EXCLUDED.tunnel_name,
            tunnel_id = EXCLUDED.tunnel_id,
            tunnel_url = EXCLUDED.tunnel_url,
            updated_at = NOW()
        """,
        {
            "branch_id": branch_id,
            "tunnel_name": branch_slug,
            "tunnel_id": tunnel_id,
            "tunnel_url": tunnel_url,
        },
    )
    await db.execute(
        """
        UPDATE branches
        SET
            tunnel_id = :tunnel_id,
            tunnel_token = :tunnel_token,
            tunnel_url = :tunnel_url,
            tunnel_status = 'active',
            tunnel_last_error = NULL,
            updated_at = NOW()
        WHERE id = :branch_id
        """,
        {
            "branch_id": branch_id,
            "tunnel_id": tunnel_id,
            "tunnel_token": tunnel_token,
            "tunnel_url": tunnel_url,
        },
    )
    await log_audit_event(
        db,
        actor="system",
        action="tunnel.auto_provision",
        entity_type="branch",
        entity_id=branch_id,
        payload={"tunnel_id": tunnel_id, "tunnel_url": tunnel_url, "mode": provisioned.get("mode")},
    )
    logger.info("Tunnel provisioned for branch %d: %s", branch_id, tunnel_url)
    return provisioned
