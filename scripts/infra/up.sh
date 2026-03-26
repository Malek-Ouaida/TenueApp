#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

resolve_supabase() {
  if command -v supabase >/dev/null 2>&1; then
    echo "supabase"
    return 0
  fi

  if [ -x "$REPO_ROOT/node_modules/.bin/supabase" ]; then
    echo "$REPO_ROOT/node_modules/.bin/supabase"
    return 0
  fi

  return 1
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to start local infrastructure."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not running."
  exit 1
fi

if ! SUPABASE_BIN="$(resolve_supabase)"; then
  echo "Supabase CLI is required to start the local database stack."
  echo "Install it globally or make it available on PATH before running pnpm infra:up."
  exit 1
fi

cd "$REPO_ROOT"

"$SUPABASE_BIN" start
docker compose -f infra/local/compose.yaml up -d
