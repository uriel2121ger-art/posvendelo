import pytest
from fastapi import HTTPException

from modules.releases.routes import release_manifest


# ---------------------------------------------------------------------------
# DummyDb helpers
# ---------------------------------------------------------------------------

_BRANCH_LINUX = {
    "id": 1,
    "branch_slug": "centro",
    "release_channel": "stable",
    "os_platform": "linux",
    "install_token": "install-token-abc123",
}

_BRANCH_WINDOWS = {
    "id": 2,
    "branch_slug": "norte",
    "release_channel": "stable",
    "os_platform": "windows",
    "install_token": "install-token-xyz789",
}


def _make_release(platform: str, artifact: str, version: str = "1.0.0", channel: str = "stable") -> dict:
    return {
        "id": abs(hash((platform, artifact, version, channel))) % 10000,
        "platform": platform,
        "artifact": artifact,
        "version": version,
        "channel": channel,
        "target_ref": f"https://example.com/releases/{artifact}/{version}/{artifact}-{version}.tar.gz",
        "notes": None,
        "created_at": "2026-03-12T00:00:00",
    }


class DummyDbFull:
    """Returns a release for every known artifact."""

    def __init__(self, branch: dict) -> None:
        self._branch = branch
        self._releases = {
            ("desktop", "backend"): _make_release("desktop", "backend"),
            ("desktop", "electron-linux"): _make_release("desktop", "electron-linux"),
            ("desktop", "electron-windows"): _make_release("desktop", "electron-windows"),
            ("desktop", "owner-electron-linux"): _make_release("desktop", "owner-electron-linux"),
            ("desktop", "owner-electron-windows"): _make_release("desktop", "owner-electron-windows"),
            ("android", "android-cajero"): _make_release("android", "android-cajero"),
            ("android", "owner-android"): _make_release("android", "owner-android"),
        }

    async def fetchrow(self, query: str, params: dict | None = None) -> dict | None:
        # Branch lookup (by branch_id or install_token)
        if "FROM branches" in query:
            return self._branch
        # release_assignments — no overrides
        if "FROM release_assignments" in query:
            return None
        # Previous release for rollback — always None in this dummy
        if "version != :current_version" in query:
            return None
        # Current release lookup
        if "FROM releases" in query and params:
            key = (params.get("platform"), params.get("artifact"))
            return self._releases.get(key)
        return None

    async def fetch(self, query: str, params: dict | None = None) -> list[dict]:
        return []


class DummyDbEmpty:
    """Branch exists but no releases are published."""

    def __init__(self, branch: dict) -> None:
        self._branch = branch

    async def fetchrow(self, query: str, params: dict | None = None) -> dict | None:
        if "FROM branches" in query:
            return self._branch
        # No releases, no assignments
        return None

    async def fetch(self, query: str, params: dict | None = None) -> list[dict]:
        return []


class DummyDbBackendOnly:
    """Only the backend release exists; all desktop/android apps are absent."""

    def __init__(self, branch: dict) -> None:
        self._branch = branch

    async def fetchrow(self, query: str, params: dict | None = None) -> dict | None:
        if "FROM branches" in query:
            return self._branch
        if "FROM release_assignments" in query:
            return None
        if "version != :current_version" in query:
            return None
        if "FROM releases" in query and params:
            if params.get("platform") == "desktop" and params.get("artifact") == "backend":
                return _make_release("desktop", "backend")
        return None

    async def fetch(self, query: str, params: dict | None = None) -> list[dict]:
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manifest_linux_returns_all_artifact_keys() -> None:
    """Manifest for a linux branch must include all five artifact keys."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_LINUX),
    )

    assert response["success"] is True
    artifacts = response["data"]["artifacts"]
    assert set(artifacts.keys()) == {"backend", "app", "owner_app", "android_cajero", "owner_android"}


@pytest.mark.asyncio
async def test_manifest_linux_resolves_correct_electron_artifacts() -> None:
    """On linux the app artifact should be electron-linux and owner_app owner-electron-linux."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_LINUX),
    )

    artifacts = response["data"]["artifacts"]
    assert artifacts["app"] is not None
    assert artifacts["app"]["artifact"] == "electron-linux"
    assert artifacts["owner_app"] is not None
    assert artifacts["owner_app"]["artifact"] == "owner-electron-linux"


@pytest.mark.asyncio
async def test_manifest_windows_resolves_correct_electron_artifacts() -> None:
    """On windows the app artifact should be electron-windows and owner_app owner-electron-windows."""
    response = await release_manifest(
        branch_id=2,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_WINDOWS),
    )

    artifacts = response["data"]["artifacts"]
    assert artifacts["app"] is not None
    assert artifacts["app"]["artifact"] == "electron-windows"
    assert artifacts["owner_app"] is not None
    assert artifacts["owner_app"]["artifact"] == "owner-electron-windows"


@pytest.mark.asyncio
async def test_manifest_android_artifacts_present() -> None:
    """android_cajero and owner_android must be present with correct platform."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_LINUX),
    )

    artifacts = response["data"]["artifacts"]
    assert artifacts["android_cajero"] is not None
    assert artifacts["android_cajero"]["platform"] == "android"
    assert artifacts["android_cajero"]["artifact"] == "android-cajero"
    assert artifacts["owner_android"] is not None
    assert artifacts["owner_android"]["platform"] == "android"
    assert artifacts["owner_android"]["artifact"] == "owner-android"


@pytest.mark.asyncio
async def test_manifest_missing_artifacts_return_null() -> None:
    """When no releases exist, all artifact values must be null (None)."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbEmpty(_BRANCH_LINUX),
    )

    assert response["success"] is True
    artifacts = response["data"]["artifacts"]
    assert artifacts["backend"] is None
    assert artifacts["app"] is None
    assert artifacts["owner_app"] is None
    assert artifacts["android_cajero"] is None
    assert artifacts["owner_android"] is None


@pytest.mark.asyncio
async def test_manifest_partial_releases_return_null_for_missing() -> None:
    """When only backend exists, app/owner_app/android artifacts must be null."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbBackendOnly(_BRANCH_LINUX),
    )

    artifacts = response["data"]["artifacts"]
    assert artifacts["backend"] is not None
    assert artifacts["app"] is None
    assert artifacts["owner_app"] is None
    assert artifacts["android_cajero"] is None
    assert artifacts["owner_android"] is None


@pytest.mark.asyncio
async def test_manifest_owner_app_includes_rollback_key() -> None:
    """owner_app payload must include a rollback key (even if None)."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_LINUX),
    )

    owner_app = response["data"]["artifacts"]["owner_app"]
    assert owner_app is not None
    assert "rollback" in owner_app
    # DummyDbFull returns None for rollback (no previous version)
    assert owner_app["rollback"] is None


@pytest.mark.asyncio
async def test_manifest_android_artifacts_have_no_rollback_key() -> None:
    """Android artifacts are plain enriched rows — no rollback key added."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_LINUX),
    )

    android_cajero = response["data"]["artifacts"]["android_cajero"]
    owner_android = response["data"]["artifacts"]["owner_android"]
    assert android_cajero is not None
    assert "rollback" not in android_cajero
    assert owner_android is not None
    assert "rollback" not in owner_android


@pytest.mark.asyncio
async def test_manifest_requires_branch_id_or_token() -> None:
    """Endpoint must raise 400 when neither branch_id nor install_token is provided."""
    with pytest.raises(HTTPException) as exc_info:
        await release_manifest(
            branch_id=None,
            install_token=None,
            x_install_token=None,
            db=DummyDbFull(_BRANCH_LINUX),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_manifest_raises_404_for_unknown_branch() -> None:
    """Endpoint must raise 404 when the branch is not found."""

    class NoBranchDb:
        async def fetchrow(self, query: str, params: dict | None = None) -> dict | None:
            if "FROM branches" in query:
                return None
            return None

        async def fetch(self, query: str, params: dict | None = None) -> list[dict]:
            return []

    with pytest.raises(HTTPException) as exc_info:
        await release_manifest(
            branch_id=999,
            install_token=None,
            x_install_token=None,
            db=NoBranchDb(),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_manifest_via_install_token_header() -> None:
    """Manifest must resolve correctly when authenticated via X-Install-Token header."""
    response = await release_manifest(
        branch_id=None,
        install_token=None,
        x_install_token="install-token-abc123",
        db=DummyDbFull(_BRANCH_LINUX),
    )

    assert response["success"] is True
    assert set(response["data"]["artifacts"].keys()) == {"backend", "app", "owner_app", "android_cajero", "owner_android"}


@pytest.mark.asyncio
async def test_manifest_metadata_fields() -> None:
    """Response data must include branch_id, branch_slug, release_channel, os_platform."""
    response = await release_manifest(
        branch_id=1,
        install_token=None,
        x_install_token=None,
        db=DummyDbFull(_BRANCH_LINUX),
    )

    data = response["data"]
    assert data["branch_id"] == 1
    assert data["branch_slug"] == "centro"
    assert data["release_channel"] == "stable"
    assert data["os_platform"] == "linux"
