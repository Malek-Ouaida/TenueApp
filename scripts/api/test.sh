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
PYTHONPATH=. uv run pytest -m "not db_integration"
