# ============================================================================
# TITAN POS — Makefile
# ============================================================================

.PHONY: up down logs test lint security security-backend security-frontend dev-backend dev-frontend clean setup

# --- Docker ---
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

# --- Development ---
dev-backend:
	cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

# --- Testing ---
test:
	cd backend && python3 -m pytest tests/ -v

test-quick:
	cd backend && python3 -m pytest tests/ -x -q

# --- Quality ---
lint:
	cd backend && python3 -m bandit -r modules/ db/ main.py -c .bandit.yaml -ll -q 2>/dev/null || true
	cd frontend && npx eslint src/ --quiet 2>/dev/null || true

# --- Security (herramientas sofisticadas) ---
# Requiere: pip install bandit pip-audit; opcional: semgrep, gitleaks
security:
	$(MAKE) security-backend
	$(MAKE) security-frontend

security-backend:
	cd backend && python3 -m bandit -r modules/ db/ main.py -c .bandit.yaml -ll
	cd backend && pip install -q pip-audit && pip-audit

security-frontend:
	cd frontend && npm audit --omit=dev --audit-level=high

# --- Utilities ---
clean:
	find backend/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend/ -name "*.pyc" -delete 2>/dev/null || true

health:
	curl -s http://localhost:8000/health | python3 -m json.tool

# --- Instalador ---
setup:
	bash setup.sh
