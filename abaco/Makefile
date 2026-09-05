# Ábaco — atajos de desarrollo.
# Todo corre sin Docker: `make instalar` y luego `make api` + `make web`.

VENV ?= .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.PHONY: ayuda instalar api worker web pruebas docs limpiar

ayuda:
	@echo "instalar  — venv + dependencias de Python + npm install del frontend"
	@echo "api       — levanta FastAPI en :8000 (sin Redis corre en modo eager)"
	@echo "worker    — levanta el worker Celery (necesita ABACO_REDIS)"
	@echo "web       — levanta Next.js en :3000"
	@echo "pruebas   — pytest del núcleo"
	@echo "docs      — regenera docs/nodos.md del registro"

instalar:
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -e "packages/core[todo,dev]"
	$(PIP) install -e services/worker -e services/api
	cd apps/web && npm install

api:
	$(VENV)/bin/uvicorn abaco_api.main:app --reload --port 8000 --app-dir services/api

worker:
	cd services/worker && ../../$(VENV)/bin/celery -A abaco_worker.celery_app worker -l info

web:
	cd apps/web && npm run dev

pruebas:
	$(VENV)/bin/pytest packages/core/tests -q

docs:
	$(PY) tools/generar_docs.py

limpiar:
	rm -rf .abaco $(VENV) apps/web/.next apps/web/node_modules
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
