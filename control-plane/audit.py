import json
from typing import Any


async def log_audit_event(
    db,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    payload: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO audit_log (actor, action, entity_type, entity_id, payload)
        VALUES (:actor, :action, :entity_type, :entity_id, :payload::jsonb)
        """,
        {
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "payload": json.dumps(payload or {}, ensure_ascii=True),
        },
    )
