import base64
import os
import secrets
from typing import Any

import httpx


def _public_hostname() -> str:
    value = os.getenv("CF_PUBLIC_BASE_DOMAIN", "").strip()
    if value:
        return value
    base_url = os.getenv("CP_BASE_URL", "http://localhost:9090").strip().rstrip("/")
    return base_url.replace("http://", "").replace("https://", "")


def build_tunnel_url(branch_slug: str) -> str:
    return f"https://{branch_slug}.{_public_hostname()}"


def cloudflare_enabled() -> bool:
    return os.getenv("CF_TUNNEL_MODE", "simulate").strip().lower() == "cloudflare"


async def _cloudflare_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    account_id = os.getenv("CF_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CF_API_TOKEN", "").strip()
    if not account_id or not api_token:
        raise RuntimeError("CF_ACCOUNT_ID o CF_API_TOKEN no configurados")

    response = await client.request(
        method,
        f"https://api.cloudflare.com/client/v4{path}",
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        json=json_body,
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success", False):
        raise RuntimeError(f"Cloudflare API error: {payload}")
    return payload["result"]


async def _ensure_dns_record(
    client: httpx.AsyncClient,
    *,
    branch_slug: str,
    tunnel_id: str,
) -> None:
    zone_id = os.getenv("CF_ZONE_ID", "").strip()
    public_base_domain = os.getenv("CF_PUBLIC_BASE_DOMAIN", "").strip()
    if not zone_id or not public_base_domain:
        return

    hostname = f"{branch_slug}.{public_base_domain}"
    record_name = hostname
    record_content = f"{tunnel_id}.cfargotunnel.com"

    existing = await _cloudflare_request(
        client,
        "GET",
        f"/zones/{zone_id}/dns_records?type=CNAME&name={record_name}",
    )
    records = existing if isinstance(existing, list) else []
    body = {"type": "CNAME", "name": record_name, "content": record_content, "proxied": True}
    if records:
        record_id = records[0]["id"]
        await _cloudflare_request(client, "PUT", f"/zones/{zone_id}/dns_records/{record_id}", json_body=body)
        return
    await _cloudflare_request(client, "POST", f"/zones/{zone_id}/dns_records", json_body=body)


async def provision_tunnel(branch_slug: str) -> dict[str, str]:
    if not cloudflare_enabled():
        tunnel_id = secrets.token_hex(8)
        return {
            "tunnel_id": tunnel_id,
            "tunnel_token": secrets.token_urlsafe(24),
            "tunnel_url": build_tunnel_url(branch_slug),
            "mode": "simulate",
        }

    account_id = os.getenv("CF_ACCOUNT_ID", "").strip()
    tunnel_secret = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    async with httpx.AsyncClient() as client:
        created = await _cloudflare_request(
            client,
            "POST",
            f"/accounts/{account_id}/cfd_tunnel",
            json_body={"name": branch_slug, "tunnel_secret": tunnel_secret},
        )
        tunnel_id = created["id"]
        token = await _cloudflare_request(
            client,
            "GET",
            f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token",
        )
        await _ensure_dns_record(client, branch_slug=branch_slug, tunnel_id=tunnel_id)

    return {
        "tunnel_id": tunnel_id,
        "tunnel_token": token,
        "tunnel_url": build_tunnel_url(branch_slug),
        "mode": "cloudflare",
    }
