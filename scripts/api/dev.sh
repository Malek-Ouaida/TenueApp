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
export WATCHFILES_FORCE_POLLING="${WATCHFILES_FORCE_POLLING:-true}"

cd apps/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app --reload-dir tests
