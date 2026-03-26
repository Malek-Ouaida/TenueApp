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
  echo "Docker is required to inspect local infrastructure."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not running."
  exit 1
fi

cd "$REPO_ROOT"

if SUPABASE_BIN="$(resolve_supabase)"; then
  "$SUPABASE_BIN" status || true
else
  echo "Supabase CLI is not installed; skipped supabase status."
fi

docker compose -f infra/local/compose.yaml ps
