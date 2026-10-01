#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export AI_MODE=demo
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/ruff check backend scripts evaluation
.venv/bin/pytest -q
if command -v swift >/dev/null; then
  swift test --package-path watch
fi
