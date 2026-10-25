.PHONY: up down logs test lint eval

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f app

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm run test:run

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

# Runs evals/cases.json through the real model from .env (costs tokens). EVAL_ARGS="--case golden"
eval:
	cd backend && .venv/bin/python -m evals.run $(EVAL_ARGS)
