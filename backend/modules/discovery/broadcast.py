"""
Servicio UDP broadcast para discovery en LAN.
Las terminales secundarias y apps móviles escuchan estos broadcasts
para encontrar el servidor POS automáticamente.
"""
import asyncio
import json
import logging
import os
import socket

logger = logging.getLogger(__name__)

DISCOVERY_PORT = 41520
BROADCAST_INTERVAL = 2.0  # segundos


def _get_local_ips() -> list[str]:
    """Obtiene todas las IPs locales (sin loopback ni interfaces Docker)."""
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("172.17."):
                ips.append(ip)
    except Exception:
        pass

    if not ips:
        # Fallback: conectar a externo para detectar interfaz por defecto
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ips.append(s.getsockname()[0])
        except Exception:
            pass

    return ips or ["127.0.0.1"]


def _build_discovery_payload() -> bytes:
    """Construye el payload JSON para el broadcast de discovery."""
    api_port = os.getenv("POSVENDELO_API_PORT", "8000")
    branch_name = os.getenv("POSVENDELO_BRANCH_NAME", "Sucursal Principal")
    version = os.getenv("POSVENDELO_VERSION", "2.0.0")
    local_ips = _get_local_ips()

    payload = {
        "service": "posvendelo",
        "version": version,
        "branch_name": branch_name,
        "api_port": int(api_port),
        "api_urls": [f"http://{ip}:{api_port}" for ip in local_ips],
        "api_url": f"http://{local_ips[0]}:{api_port}",
    }
    return json.dumps(payload, ensure_ascii=True).encode("utf-8")


async def start_discovery_broadcast():
    """
    Inicia el loop UDP broadcast para discovery LAN.
    Envía un paquete JSON cada BROADCAST_INTERVAL segundos.
    """
    logger.info("Iniciando broadcast LAN discovery en puerto %d", DISCOVERY_PORT)

    # Build payload once — IPs don't change at runtime; avoids blocking DNS
    # resolution (socket.getaddrinfo) on every broadcast tick.
    payload = _build_discovery_payload()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)

    try:
        while True:
            try:
                sock.sendto(payload, ("255.255.255.255", DISCOVERY_PORT))
            except Exception as exc:
                logger.debug("Discovery broadcast error: %s", exc)

            await asyncio.sleep(BROADCAST_INTERVAL)
    finally:
        sock.close()
        logger.info("Discovery broadcast detenido")
