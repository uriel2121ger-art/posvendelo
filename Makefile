# ============================================================================
# TITAN POS — Makefile
# ============================================================================

.PHONY: up down logs test lint dev-backend dev-frontend clean

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
	cd backend && python3 -m bandit -r modules/ db/ main.py -ll -q 2>/dev/null || true
	cd frontend && npx eslint src/ --quiet 2>/dev/null || true

# --- Utilities ---
clean:
	find backend/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend/ -name "*.pyc" -delete 2>/dev/null || true

health:
	curl -s http://localhost:8000/health | python3 -m json.tool
