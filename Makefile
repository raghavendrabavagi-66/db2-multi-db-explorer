.PHONY: help install install-frontend install-backend dev dev-backend dev-frontend build-frontend legacy-streamlit lint-frontend

PYTHON ?= python3
VENV ?= .venv
NPM ?= npm

help:
	@echo "Targets:"
	@echo "  install            Install backend (Python) + frontend (npm) dependencies"
	@echo "  dev                Run FastAPI (:8000) and Vite (:5173) together"
	@echo "  dev-backend        FastAPI with reload on :8000"
	@echo "  dev-frontend       Vite dev server on :5173 (proxies /api → :8000)"
	@echo "  build-frontend     Production React build → frontend/dist"
	@echo "  legacy-streamlit   Run legacy Streamlit UI from legacy/streamlit/"
	@echo "  lint-frontend      Typecheck React app"

install: install-backend install-frontend

install-backend:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -r requirements.txt

install-frontend:
	cd frontend && $(NPM) install

dev-backend:
	PYTHONPATH=. $(VENV)/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && $(NPM) run dev

dev:
	@echo "Starting backend (:8000) and frontend (:5173)…"
	@($(MAKE) dev-backend &) && sleep 1 && $(MAKE) dev-frontend

build-frontend:
	cd frontend && $(NPM) run build

legacy-streamlit:
	cd legacy/streamlit && PYTHONPATH=../.. ../../$(VENV)/bin/streamlit run app.py

lint-frontend:
	cd frontend && $(NPM) run lint
