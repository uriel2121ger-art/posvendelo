import hashlib
import os
from pathlib import Path

from audit import log_audit_event
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile

from db.connection import get_db
from modules.releases.schemas import (
    ReleaseAssignmentRequest,
    ReleaseCreateRequest,
    ReleasePublishRequest,
)
from security import verify_admin, verify_release_publisher

router = APIRouter()

# Mirror the same env var used in main.py so the two modules stay in sync.
_default_downloads = Path(__file__).resolve().parent.parent.parent / "downloads"
DOWNLOADS_DIR = Path(os.getenv("CP_DOWNLOADS_DIR", str(_default_downloads)))

# Maps artifact identifier → canonical filename saved under DOWNLOADS_DIR.
ARTIFACT_FILENAME_MAP: dict[str, str] = {
    "electron-linux": "posvendelo.AppImage",
    "electron-windows": "posvendelo-setup.exe",
    "electron-deb": "posvendelo_amd64.deb",
    "electron-deb-arm64": "posvendelo_arm64.deb",
    "android-cajero": "posvendelo.apk",
    "owner-electron-linux": "posvendelo-owner.AppImage",
    "owner-electron-windows": "posvendelo-owner-setup.exe",
    "owner-electron-deb": "posvendelo-owner_amd64.deb",
    "owner-android": "posvendelo-owner.apk",
    "owner-web": "posvendelo-owner-web.zip",
    # backend is a Docker image — no file is uploaded, only the release record is registered.
    "backend": "backend",
}

# Maps artifact identifier → control-plane download path for target_ref construction.
ARTIFACT_DOWNLOAD_PATH: dict[str, str] = {
    "electron-linux": "/download/cajero/appimage",
    "electron-windows": "/download/cajero/windows",
    "electron-deb": "/download/cajero/deb",
    "electron-deb-arm64": "/download/cajero/deb/arm64",
    "android-cajero": "/download/cajero/apk",
    "owner-electron-linux": "/download/owner/appimage",
    "owner-electron-windows": "/download/owner/windows",
    "owner-electron-deb": "/download/owner/deb",
    "owner-android": "/download/owner/apk",
    "owner-web": "/download/owner/web",
}


def _update_sha256sums(downloads_dir: Path, filename: str, sha256hex: str) -> None:
    """Update SHA256SUMS.txt: remove old entry for *filename*, append new one, keep sorted."""
    sums_path = downloads_dir / "SHA256SUMS.txt"
    lines: list[str] = []
    if sums_path.exists():
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            # Keep lines that are not the old entry for this file.
            if line.strip() and not line.strip().endswith(f"  {filename}"):
                lines.append(line)
    lines.append(f"{sha256hex}  {filename}")
    lines.sort(key=lambda ln: ln.split("  ", 1)[-1] if "  " in ln else ln)
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


@router.post("/upload")
async def upload_release_artifact(
    request: Request,
    platform: str = Form(...),
    artifact: str = Form(...),
    version: str = Form(...),
    channel: str = Form(default="stable"),
    notes: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    _: dict = Depends(verify_release_publisher),
    db=Depends(get_db),
):
    """Upload a build artifact and register it as an active release.

    For the 'backend' artifact (Docker image) no file is required — pass only the
    form fields and the version string is used as the Docker image tag.
    """
    if artifact not in ARTIFACT_FILENAME_MAP:
        raise HTTPException(status_code=400, detail=f"Artifact desconocido: {artifact}")

    # Resolve base URL for target_ref construction.
    cp_public_url = os.getenv("CP_PUBLIC_URL", "").strip().rstrip("/")
    if not cp_public_url:
        cp_public_url = str(request.base_url).rstrip("/")

    # --- Backend (Docker image only) — no file upload ---
    if artifact == "backend":
        target_ref = f"ghcr.io/uriel2121ger-art/posvendelo:{version}"
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
            {
                "platform": platform,
                "artifact": artifact,
                "version": version,
                "channel": channel,
                "target_ref": target_ref,
                "notes": notes,
            },
        )
        await log_audit_event(
            db,
            actor="release-publisher",
            action="release.upload",
            entity_type="release",
            entity_id=row["id"],
            payload={
                "platform": platform,
                "artifact": artifact,
                "version": version,
                "target_ref": target_ref,
            },
        )
        return {"success": True, "data": _enrich_release_row(row)}

    # --- File-based artifact ---
    if file is None:
        raise HTTPException(status_code=422, detail="Se requiere el archivo para este artifact")

    target_filename = ARTIFACT_FILENAME_MAP[artifact]
    download_path = ARTIFACT_DOWNLOAD_PATH.get(artifact, "")
    target_ref = f"{cp_public_url}{download_path}" if download_path else ""

    # Read file content (max ~500 MB enforced by FastAPI body limit or reverse proxy).
    content = await file.read()
    sha256hex = hashlib.sha256(content).hexdigest()

    # Persist file to downloads directory.
    downloads_dir = DOWNLOADS_DIR
    downloads_dir.mkdir(parents=True, exist_ok=True)
    dest = downloads_dir / target_filename
    dest.write_bytes(content)

    # Keep SHA256SUMS.txt up-to-date.
    _update_sha256sums(downloads_dir, target_filename, sha256hex)

    checksums_url = f"{cp_public_url}/download/SHA256SUMS.txt"

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
        {
            "platform": platform,
            "artifact": artifact,
            "version": version,
            "channel": channel,
            "target_ref": target_ref,
            "notes": notes,
        },
    )
    await log_audit_event(
        db,
        actor="release-publisher",
        action="release.upload",
        entity_type="release",
        entity_id=row["id"],
        payload={
            "platform": platform,
            "artifact": artifact,
            "version": version,
            "filename": target_filename,
            "sha256": sha256hex,
            "size_bytes": len(content),
        },
    )
    result = _enrich_release_row(row)
    result["sha256"] = sha256hex
    result["filename"] = target_filename
    result["size_bytes"] = len(content)
    result["checksums_url"] = checksums_url
    return {"success": True, "data": result}


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
    x_install_token: str | None = Header(default=None, alias="X-Install-Token"),
    db=Depends(get_db),
):
    install_token = install_token or (x_install_token.strip() if isinstance(x_install_token, str) and x_install_token.strip() else None)
    if branch_id is None and not install_token:
        raise HTTPException(status_code=400, detail="branch_id o install_token requerido")

    branch = await _branch_release_context(db, branch_id=branch_id, install_token=install_token)
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    os_platform = (branch.get("os_platform") or "linux").strip().lower()
    app_artifact = "electron-windows" if os_platform.startswith("win") else "electron-linux"
    owner_artifact = "owner-electron-windows" if os_platform.startswith("win") else "owner-electron-linux"
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

    owner_app_release = await _resolve_release_row(
        db,
        branch_id=branch["id"],
        default_channel=release_channel,
        platform="desktop",
        artifact=owner_artifact,
    )
    owner_app_rollback_release = await _resolve_previous_release_row(
        db,
        platform="desktop",
        artifact=owner_artifact,
        channel=release_channel,
        current_version=owner_app_release["version"] if owner_app_release else None,
    )
    owner_app_payload = _enrich_release_row(owner_app_release)
    if owner_app_payload:
        owner_app_payload["rollback"] = _enrich_release_row(owner_app_rollback_release)

    android_cajero_release = await _resolve_release_row(
        db,
        branch_id=branch["id"],
        default_channel=release_channel,
        platform="android",
        artifact="android-cajero",
    )
    owner_android_release = await _resolve_release_row(
        db,
        branch_id=branch["id"],
        default_channel=release_channel,
        platform="android",
        artifact="owner-android",
    )

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
                "owner_app": owner_app_payload,
                "android_cajero": _enrich_release_row(android_cajero_release),
                "owner_android": _enrich_release_row(owner_android_release),
            },
        },
    }
