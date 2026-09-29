#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
exec .venv/bin/python backend/manage.py runserver "${DEV_BIND:-127.0.0.1:8000}"
