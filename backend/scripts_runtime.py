from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass(frozen=True)
class ScriptRuntime:
    base_url: str
    username: str
    password: str
    branch_id: int

    def api_url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        return urljoin(f"{self.base_url}/", clean_path.lstrip("/"))


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} no está configurada. Exporta {name} antes de ejecutar este script."
        )
    return value


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} debe ser un entero válido.") from exc


def load_runtime() -> ScriptRuntime:
    base_url = _read_required_env("TITAN_TEST_API_URL").rstrip("/")
    return ScriptRuntime(
        base_url=base_url,
        username=_read_required_env("TITAN_TEST_USER"),
        password=_read_required_env("TITAN_TEST_PASSWORD"),
        branch_id=_read_int_env("TITAN_TEST_BRANCH_ID", 1),
    )
