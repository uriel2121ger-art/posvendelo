#!/usr/bin/env python3
"""
Administra licencias del control-plane sin tocar SQL manual.

Ejemplos:
  python3 scripts/license_admin.py issue \
    --base-url http://localhost:9090 \
    --admin-token <admin-token-seguro> \
    --tenant-id 1 \
    --license-type monthly \
    --valid-until 2026-04-01T00:00:00

  python3 scripts/license_admin.py export-file \
    --base-url http://localhost:9090 \
    --install-token TOKEN \
    --machine-id MI-EQUIPO \
    --output titan-license.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _request_json(url: str, *, method: str = "GET", token: str | None = None, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Admin-Token"] = token
    if body is not None:
        payload = json.dumps(body, ensure_ascii=True).encode("utf-8")
    request = Request(url, data=payload, method=method, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"No se pudo conectar al control-plane: {exc}") from exc


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def issue_license(args: argparse.Namespace) -> None:
    body = {
        "tenant_id": args.tenant_id,
        "license_type": args.license_type,
        "status": args.status,
        "valid_from": args.valid_from,
        "valid_until": args.valid_until,
        "support_until": args.support_until,
        "trial_started_at": args.trial_started_at,
        "trial_expires_at": args.trial_expires_at,
        "grace_days": args.grace_days,
        "max_branches": args.max_branches,
        "max_devices": args.max_devices,
        "notes": args.notes,
    }
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/issue",
        method="POST",
        token=args.admin_token,
        body=body,
    )
    _print_json(result)


def onboard_tenant(args: argparse.Namespace) -> None:
    body = {
        "name": args.name,
        "slug": args.slug,
        "branch_name": args.branch_name,
        "branch_slug": args.branch_slug,
        "release_channel": args.release_channel,
        "license_type": args.license_type,
        "license_status": args.license_status,
        "grace_days": args.grace_days,
        "max_branches": args.max_branches,
        "max_devices": args.max_devices,
        "notes": args.notes,
    }
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/tenants/onboard",
        method="POST",
        token=args.admin_token,
        body=body,
    )
    _print_json(result)


def revoke_license(args: argparse.Namespace) -> None:
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/revoke",
        method="POST",
        token=args.admin_token,
        body={"license_id": args.license_id, "reason": args.reason},
    )
    _print_json(result)


def renew_license(args: argparse.Namespace) -> None:
    body = {
        "license_id": args.license_id,
        "valid_until": args.valid_until,
        "support_until": args.support_until,
        "additional_days": args.additional_days,
        "notes": args.notes,
    }
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/renew",
        method="POST",
        token=args.admin_token,
        body=body,
    )
    _print_json(result)


def list_licenses(args: argparse.Namespace) -> None:
    query = urlencode(
        {
            key: value
            for key, value in {
                "tenant_id": args.tenant_id,
                "status": args.status,
            }.items()
            if value is not None
        }
    )
    suffix = f"?{query}" if query else ""
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/{suffix}",
        token=args.admin_token,
    )
    _print_json(result)


def license_events(args: argparse.Namespace) -> None:
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/{args.license_id}/events",
        token=args.admin_token,
    )
    _print_json(result)


def license_summary(args: argparse.Namespace) -> None:
    query = urlencode({"reminder_days": args.reminder_days})
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/summary?{query}",
        token=args.admin_token,
    )
    _print_json(result)


def license_reminders(args: argparse.Namespace) -> None:
    query = urlencode(
        {
            "reminder_days": args.reminder_days,
            "limit": args.limit,
        }
    )
    result = _request_json(
        f"{args.base_url.rstrip('/')}/api/v1/licenses/reminders?{query}",
        token=args.admin_token,
    )
    _print_json(result)


def resolve_license(args: argparse.Namespace) -> dict[str, Any]:
    query = urlencode(
        {
            "install_token": args.install_token,
            "machine_id": args.machine_id,
            "os_platform": args.os_platform,
            "app_version": args.app_version,
            "pos_version": args.pos_version,
        }
    )
    result = _request_json(f"{args.base_url.rstrip('/')}/api/v1/licenses/resolve?{query}")
    _print_json(result)
    return result


def export_license_file(args: argparse.Namespace) -> None:
    result = resolve_license(args)
    license_blob = ((result.get("data") or {}) if isinstance(result, dict) else {}).get("license")
    if not isinstance(license_blob, dict):
        raise SystemExit("La respuesta no incluyó una licencia exportable")
    output_path = Path(args.output)
    output_path.write_text(json.dumps(license_blob, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nLicencia exportada a: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administración operativa de licencias POSVENDELO")
    parser.add_argument("--base-url", required=True, help="URL del control-plane, ej. http://localhost:9090")
    sub = parser.add_subparsers(dest="command", required=True)

    onboard = sub.add_parser("onboard", help="Crear tenant, sucursal bootstrap y licencia inicial")
    onboard.add_argument("--admin-token", required=True)
    onboard.add_argument("--name", required=True)
    onboard.add_argument("--slug", required=True)
    onboard.add_argument("--branch-name", default="Sucursal Principal")
    onboard.add_argument("--branch-slug")
    onboard.add_argument("--release-channel", default="stable")
    onboard.add_argument("--license-type", default="trial", choices=["trial", "monthly", "perpetual"])
    onboard.add_argument("--license-status", default="active", choices=["active", "grace", "expired", "revoked"])
    onboard.add_argument("--grace-days", type=int, default=0)
    onboard.add_argument("--max-branches", type=int)
    onboard.add_argument("--max-devices", type=int)
    onboard.add_argument("--notes")
    onboard.set_defaults(func=onboard_tenant)

    issue = sub.add_parser("issue", help="Emitir o renovar una licencia")
    issue.add_argument("--admin-token", required=True)
    issue.add_argument("--tenant-id", required=True, type=int)
    issue.add_argument("--license-type", required=True, choices=["trial", "monthly", "perpetual"])
    issue.add_argument("--status", default="active", choices=["active", "grace", "expired", "revoked"])
    issue.add_argument("--valid-from")
    issue.add_argument("--valid-until")
    issue.add_argument("--support-until")
    issue.add_argument("--trial-started-at")
    issue.add_argument("--trial-expires-at")
    issue.add_argument("--grace-days", type=int, default=0)
    issue.add_argument("--max-branches", type=int)
    issue.add_argument("--max-devices", type=int)
    issue.add_argument("--notes")
    issue.set_defaults(func=issue_license)

    revoke = sub.add_parser("revoke", help="Revocar una licencia existente")
    revoke.add_argument("--admin-token", required=True)
    revoke.add_argument("--license-id", required=True, type=int)
    revoke.add_argument("--reason")
    revoke.set_defaults(func=revoke_license)

    renew = sub.add_parser("renew", help="Renovar una licencia existente")
    renew.add_argument("--admin-token", required=True)
    renew.add_argument("--license-id", required=True, type=int)
    renew.add_argument("--valid-until")
    renew.add_argument("--support-until")
    renew.add_argument("--additional-days", type=int, default=0)
    renew.add_argument("--notes")
    renew.set_defaults(func=renew_license)

    list_cmd = sub.add_parser("list", help="Listar licencias")
    list_cmd.add_argument("--admin-token", required=True)
    list_cmd.add_argument("--tenant-id", type=int)
    list_cmd.add_argument("--status")
    list_cmd.set_defaults(func=list_licenses)

    events = sub.add_parser("events", help="Ver eventos de una licencia")
    events.add_argument("--admin-token", required=True)
    events.add_argument("--license-id", required=True, type=int)
    events.set_defaults(func=license_events)

    summary = sub.add_parser("summary", help="Resumen comercial de licencias")
    summary.add_argument("--admin-token", required=True)
    summary.add_argument("--reminder-days", type=int, default=30)
    summary.set_defaults(func=license_summary)

    reminders = sub.add_parser("reminders", help="Licencias que requieren atención")
    reminders.add_argument("--admin-token", required=True)
    reminders.add_argument("--reminder-days", type=int, default=30)
    reminders.add_argument("--limit", type=int, default=100)
    reminders.set_defaults(func=license_reminders)

    resolve = sub.add_parser("resolve", help="Resolver una licencia para un nodo")
    resolve.add_argument("--install-token", required=True)
    resolve.add_argument("--machine-id", required=True)
    resolve.add_argument("--os-platform", default=sys.platform)
    resolve.add_argument("--app-version", default="1.0.0")
    resolve.add_argument("--pos-version", default="2.0.0")
    resolve.set_defaults(func=resolve_license)

    export_file = sub.add_parser("export-file", help="Exportar titan-license.json para un cliente offline")
    export_file.add_argument("--install-token", required=True)
    export_file.add_argument("--machine-id", required=True)
    export_file.add_argument("--os-platform", default=sys.platform)
    export_file.add_argument("--app-version", default="1.0.0")
    export_file.add_argument("--pos-version", default="2.0.0")
    export_file.add_argument("--output", default="titan-license.json")
    export_file.set_defaults(func=export_license_file)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
