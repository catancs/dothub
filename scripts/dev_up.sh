#!/usr/bin/env bash
# Run dothub locally with zero infra: SQLite file + local-disk bundles, no AWS.
# Usage:  ./scripts/dev_up.sh            (plain)
#         ./scripts/dev_up.sh --reload   (auto-reload on code changes)
# Data persists in ./dothub-dev.db and ./dev-bundles (both gitignored).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && source .venv/bin/activate

export DATABASE_URL="${DATABASE_URL:-sqlite+pysqlite:///./dothub-dev.db}"
export STORAGE_DIR="${STORAGE_DIR:-./dev-bundles}"
export SESSION_SECRET="${SESSION_SECRET:-dev-local-secret-please-change}"
export BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "dothub → http://localhost:8000  (feed /, mcp /mcp/, health /healthz)"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 "$@"
