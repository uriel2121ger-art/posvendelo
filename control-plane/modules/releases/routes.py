from audit import log_audit_event
from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.releases.schemas import (
    ReleaseAssignmentRequest,
    ReleaseCreateRequest,
    ReleasePublishRequest,
)
from security import verify_admin, verify_release_publisher

router = APIRouter()


def _build_checksums_manifest_url(target_ref: str | None) -> str | None:
    if not target_ref:
        return None
    if not target_ref.startswith("http://") and not target_ref.startswith("https://"):
        return None
    base, _, _ = target_ref.rpartition("/")
    if not base:
        return None
    return f"{base}/SHA256SUMS.txt"


def _enrich_release_row(row: dict | None) -> dict | None:
    if not row:
        return None
    target_ref = row.get("target_ref")
    artifact = row.get("artifact")
    is_desktop_app = isinstance(artifact, str) and artifact.startswith("electron-")
    checksums_manifest_url = _build_checksums_manifest_url(target_ref) if is_desktop_app else None
    return {
        **row,
        "checksums_manifest_url": checksums_manifest_url,
        "rollback_supported": bool(is_desktop_app),
        "rollout_strategy": "manual-stage-apply",
    }


async def _branch_release_context(db, *, branch_id: int | None = None, install_token: str | None = None) -> dict | None:
    if branch_id is not None:
        return await db.fetchrow(
            """
            SELECT id, release_channel, os_platform, branch_slug
            FROM branches
            WHERE id = :branch_id
            """,
            {"branch_id": branch_id},
        )
    if install_token:
        return await db.fetchrow(
            """
            SELECT id, release_channel, os_platform, branch_slug
            FROM branches
            WHERE install_token = :install_token
            """,
            {"install_token": install_token},
        )
    return None


async def _resolve_release_row(
    db,
    *,
    branch_id: int | None,
    default_channel: str,
    platform: str,
    artifact: str,
) -> dict | None:
    channel = default_channel
    pinned_version = None

    if branch_id is not None:
        assignment = await db.fetchrow(
            """
            SELECT channel, pinned_version
            FROM release_assignments
            WHERE branch_id = :branch_id AND platform = :platform AND artifact = :artifact
            """,
            {"branch_id": branch_id, "platform": platform, "artifact": artifact},
        )
        if assignment:
            channel = assignment["channel"] or channel
            pinned_version = assignment["pinned_version"]

    query = """
        SELECT id, platform, artifact, version, channel, target_ref, notes, created_at
        FROM releases
        WHERE platform = :platform
          AND artifact = :artifact
          AND channel = :channel
          AND is_active = 1
    """
    params = {"platform": platform, "artifact": artifact, "channel": channel}
    if pinned_version:
        query += " AND version = :version"
        params["version"] = pinned_version
    query += " ORDER BY created_at DESC LIMIT 1"
    return await db.fetchrow(query, params)


async def _resolve_previous_release_row(
    db,
    *,
    platform: str,
    artifact: str,
    channel: str,
    current_version: str | None,
) -> dict | None:
    if not current_version:
        return None
    return await db.fetchrow(
        """
        SELECT id, platform, artifact, version, channel, target_ref, notes, created_at
        FROM releases
        WHERE platform = :platform
          AND artifact = :artifact
          AND channel = :channel
          AND is_active = 1
          AND version != :current_version
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {
            "platform": platform,
            "artifact": artifact,
            "channel": channel,
            "current_version": current_version,
        },
    )


@router.post("/")
async def create_release(
    body: ReleaseCreateRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    row = await db.fetchrow(
        """
        INSERT INTO releases (platform, artifact, version, channel, target_ref, notes)
        VALUES (:platform, :artifact, :version, :channel, :target_ref, :notes)
        ON CONFLICT (platform, artifact, version, channel) DO UPDATE SET
            target_ref = EXCLUDED.target_ref,
            notes = EXCLUDED.notes,
            is_active = 1
        RETURNING id, platform, artifact, version, channel, target_ref, notes, created_at
        """,
        body.model_dump(),
    )
    await log_audit_event(
        db,
        actor="admin",
        action="release.create",
        entity_type="release",
        entity_id=row["id"],
        payload={"platform": row["platform"], "artifact": row["artifact"], "version": row["version"]},
    )
    return {"success": True, "data": _enrich_release_row(row)}


@router.get("/")
async def list_releases(
    _: dict = Depends(verify_admin),
    platform: str | None = Query(default=None),
    artifact: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    db=Depends(get_db),
):
    query = """
        SELECT id, platform, artifact, version, channel, target_ref, notes, is_active, created_at
        FROM releases
        WHERE 1 = 1
    """
    params: dict[str, str] = {}
    if platform:
        query += " AND platform = :platform"
        params["platform"] = platform
    if artifact:
        query += " AND artifact = :artifact"
        params["artifact"] = artifact
    if channel:
        query += " AND channel = :channel"
        params["channel"] = channel
    query += " ORDER BY created_at DESC"
    rows = await db.fetch(query, params)
    return {"success": True, "data": [_enrich_release_row(row) for row in rows]}


@router.post("/assign")
async def assign_release(
    body: ReleaseAssignmentRequest,
    _: dict = Depends(verify_admin),
    db=Depends(get_db),
):
    branch = await db.fetchrow(
        "SELECT id FROM branches WHERE id = :branch_id",
        {"branch_id": body.branch_id},
    )
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    if body.pinned_version:
        release = await db.fetchrow(
            """
            SELECT id
            FROM releases
            WHERE platform = :platform
              AND artifact = :artifact
              AND version = :version
              AND channel = :channel
              AND is_active = 1
            """,
            {
                "platform": body.platform,
                "artifact": body.artifact,
                "version": body.pinned_version,
                "channel": body.channel,
            },
        )
        if not release:
            raise HTTPException(status_code=404, detail="Release fijada no encontrada")

    row = await db.fetchrow(
        """
        INSERT INTO release_assignments (branch_id, platform, artifact, pinned_version, channel)
        VALUES (:branch_id, :platform, :artifact, :pinned_version, :channel)
        ON CONFLICT (branch_id, platform, artifact) DO UPDATE SET
            pinned_version = EXCLUDED.pinned_version,
            channel = EXCLUDED.channel,
            updated_at = NOW()
        RETURNING id, branch_id, platform, artifact, pinned_version, channel, updated_at
        """,
        body.model_dump(),
    )
    await log_audit_event(
        db,
        actor="admin",
        action="release.assign",
        entity_type="branch",
        entity_id=body.branch_id,
        payload={
            "platform": body.platform,
            "artifact": body.artifact,
            "channel": body.channel,
            "pinned_version": body.pinned_version,
        },
    )
    return {"success": True, "data": _enrich_release_row(row)}


@router.post("/publish")
async def publish_release(
    body: ReleasePublishRequest,
    _: dict = Depends(verify_release_publisher),
    db=Depends(get_db),
):
    row = await db.fetchrow(
        """
        INSERT INTO releases (platform, artifact, version, channel, target_ref, notes)
        VALUES (:platform, :artifact, :version, :channel, :target_ref, :notes)
        ON CONFLICT (platform, artifact, version, channel) DO UPDATE SET
            target_ref = EXCLUDED.target_ref,
            notes = EXCLUDED.notes,
            is_active = 1
        RETURNING id, platform, artifact, version, channel, target_ref, notes, created_at
        """,
        body.model_dump(exclude={"source"}),
    )
    await log_audit_event(
        db,
        actor=body.source or "release-publisher",
        action="release.publish",
        entity_type="release",
        entity_id=row["id"],
        payload={
            "platform": row["platform"],
            "artifact": row["artifact"],
            "version": row["version"],
            "channel": row["channel"],
            "target_ref": row["target_ref"],
        },
    )
    return {"success": True, "data": _enrich_release_row(row)}


@router.get("/resolve")
async def resolve_release(
    branch_id: int | None = Query(default=None, ge=1),
    platform: str = Query(default="desktop"),
    artifact: str = Query(default="backend"),
    db=Depends(get_db),
):
    channel = "stable"
    if branch_id is not None:
        branch = await _branch_release_context(db, branch_id=branch_id)
        if branch and branch.get("release_channel"):
            channel = branch["release_channel"]

    release = await _resolve_release_row(
        db,
        branch_id=branch_id,
        default_channel=channel,
        platform=platform,
        artifact=artifact,
    )
    if not release:
        raise HTTPException(status_code=404, detail="No hay release activa para los filtros")

    return {"success": True, "data": _enrich_release_row(release)}


@router.get("/manifest")
async def release_manifest(
    branch_id: int | None = Query(default=None, ge=1),
    install_token: str | None = Query(default=None, min_length=8),
    db=Depends(get_db),
):
    if branch_id is None and not install_token:
        raise HTTPException(status_code=400, detail="branch_id o install_token requerido")

    branch = await _branch_release_context(db, branch_id=branch_id, install_token=install_token)
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    os_platform = (branch.get("os_platform") or "linux").strip().lower()
    app_artifact = "electron-windows" if os_platform.startswith("win") else "electron-linux"
    release_channel = branch.get("release_channel") or "stable"

    backend_release = await _resolve_release_row(
        db,
        branch_id=branch["id"],
        default_channel=release_channel,
        platform="desktop",
        artifact="backend",
    )
    app_release = await _resolve_release_row(
        db,
        branch_id=branch["id"],
        default_channel=release_channel,
        platform="desktop",
        artifact=app_artifact,
    )
    app_rollback_release = await _resolve_previous_release_row(
        db,
        platform="desktop",
        artifact=app_artifact,
        channel=release_channel,
        current_version=app_release["version"] if app_release else None,
    )
    app_payload = _enrich_release_row(app_release)
    if app_payload:
        app_payload["rollback"] = _enrich_release_row(app_rollback_release)

    return {
        "success": True,
        "data": {
            "branch_id": branch["id"],
            "branch_slug": branch["branch_slug"],
            "release_channel": release_channel,
            "os_platform": os_platform,
            "artifacts": {
                "backend": _enrich_release_row(backend_release),
                "app": app_payload,
            },
        },
    }
