#!/usr/bin/env bash
set -euo pipefail

if [ ! -f "apps/api/pyproject.toml" ]; then
  echo "apps/api is not scaffolded yet. Phase 00 only defines the API wrapper contract."
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  export PATH="$(python3 -m site --user-base)/bin:$PATH"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to run apps/api. Install it before using the API scripts."
  exit 1
fi

export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uv-cache}"

cd apps/api
resolve_db_field() {
  PYTHONPATH=. uv run python -m app.core.db_target --field "$1"
}

DB_TARGET="$(resolve_db_field target)"
DB_SOURCE="$(resolve_db_field source)"
DB_HOST="$(resolve_db_field host)"
DB_URL="$(resolve_db_field database_url)"

echo "Resolved API database target: $DB_TARGET (source: $DB_SOURCE, host: $DB_HOST)"

if [ "$DB_TARGET" = "remote" ] && [ "${TENUE_ALLOW_REMOTE_MIGRATIONS:-}" != "1" ]; then
  echo "Remote migrations are blocked by default."
  echo "Set TENUE_ALLOW_REMOTE_MIGRATIONS=1 for this command if you really intend to migrate a remote database."
  exit 1
fi

export DATABASE_URL="$DB_URL"
PYTHONPATH=. uv run alembic upgrade head
