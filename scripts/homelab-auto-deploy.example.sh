#!/usr/bin/env bash
# POSVENDELO — Ejemplo de script de auto-deploy en el homelab (servidor .90)
#
# Uso en el homelab: copiar a /opt/posvendelo/auto-deploy.sh, ajustar
# POSVENDELO_REPO_DIR y cron (ej. cada 5 min).
# No ejecutar desde el repo de desarrollo; está pensado para correr EN el servidor.
#
# Requisitos en el homelab: git, docker, docker compose, acceso a clone/pull del repo.

set -e

POSVENDELO_REPO_DIR="${POSVENDELO_REPO_DIR:-/opt/posvendelo/repo}"
cd "$POSVENDELO_REPO_DIR"

# Detectar si hay commits nuevos (evitar rebuild innecesario)
git fetch origin master
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master)
if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

git pull origin master

# Rebuild y reinicio del control-plane (ajustar según tu docker-compose)
if [ -d "control-plane" ]; then
  (cd control-plane && docker compose build --quiet && docker compose up -d --force-recreate)
fi

# Opcional: forzar Watchtower una vez para que los nodos actualicen antes del próximo poll
# docker exec posvendelo-watchtower-1 /watchtower --run-once 2>/dev/null || true

# Opcional: copiar artefactos locales (si builds se hacen en el homelab)
# cp -f frontend/dist/*.deb control-plane/downloads/ 2>/dev/null || true
# cp -f frontend/dist/*.AppImage control-plane/downloads/ 2>/dev/null || true

exit 0
