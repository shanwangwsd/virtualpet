#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations --check --dry-run
.venv/bin/ruff check backend scripts evaluation
.venv/bin/pytest -q
mkdir -p work/swift-cache work/clang-cache
if command -v swiftc >/dev/null; then
  CLANG_MODULE_CACHE_PATH="$PWD/work/clang-cache" swiftc -module-cache-path "$PWD/work/swift-cache" watch/HabitPet/Core/Models.swift scripts/swift_core_check.swift -o work/swift-core-check
  work/swift-core-check
fi
