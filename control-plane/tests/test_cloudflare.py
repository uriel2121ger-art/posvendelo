from modules.tunnel.cloudflare import build_tunnel_url, cloudflare_enabled


def test_build_tunnel_url_uses_public_base_domain(monkeypatch) -> None:
    monkeypatch.setenv("CF_PUBLIC_BASE_DOMAIN", "demo.posvendelo.local")

    url = build_tunnel_url("sucursal-centro")

    assert url == "https://sucursal-centro.demo.posvendelo.local"


def test_cloudflare_enabled_defaults_to_simulate(monkeypatch) -> None:
    monkeypatch.delenv("CF_TUNNEL_MODE", raising=False)

    assert cloudflare_enabled() is False


def test_cloudflare_enabled_returns_true_for_cloudflare_mode(monkeypatch) -> None:
    monkeypatch.setenv("CF_TUNNEL_MODE", "cloudflare")

    assert cloudflare_enabled() is True
