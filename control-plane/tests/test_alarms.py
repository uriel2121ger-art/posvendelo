from datetime import UTC, datetime, timedelta

from alarms.telegram import collect_alert_candidates


def test_collect_alert_candidates_detects_expected_conditions() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)

    alerts = collect_alert_candidates(
        [
            {
                "id": 10,
                "branch_name": "Centro",
                "last_seen": now - timedelta(minutes=20),
                "disk_used_pct": 87.5,
                "last_backup": now - timedelta(hours=18),
            }
        ],
        now=now,
    )

    kinds = {alert["kind"] for alert in alerts}

    assert kinds == {"offline_branch", "disk_usage", "backup_stale"}


def test_collect_alert_candidates_skips_healthy_branch() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)

    alerts = collect_alert_candidates(
        [
            {
                "id": 11,
                "branch_name": "Norte",
                "last_seen": now - timedelta(minutes=5),
                "disk_used_pct": 41.0,
                "last_backup": now - timedelta(hours=2),
            }
        ],
        now=now,
    )

    assert alerts == []


def test_collect_alert_candidates_detects_install_and_tunnel_errors() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)

    alerts = collect_alert_candidates(
        [
            {
                "id": 12,
                "branch_name": "Sur",
                "last_seen": now - timedelta(minutes=1),
                "disk_used_pct": 20.0,
                "last_backup": now - timedelta(hours=1),
                "install_status": "error",
                "install_error": "docker compose failed",
                "tunnel_status": "error",
                "tunnel_last_error": "dns conflict",
            }
        ],
        now=now,
    )

    kinds = {alert["kind"] for alert in alerts}

    assert kinds == {"install_error", "tunnel_error"}
