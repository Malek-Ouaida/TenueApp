from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]

LOCAL_DB_TARGET = "local"
REMOTE_DB_TARGET = "remote"
LOCAL_SUPABASE_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"

TENUE_DB_TARGET_ENV = "TENUE_DB_TARGET"
TENUE_ALLOW_REMOTE_MIGRATIONS_ENV = "TENUE_ALLOW_REMOTE_MIGRATIONS"
DATABASE_URL_ENV = "DATABASE_URL"


class DatabaseTargetResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class DatabaseTarget:
    target: str
    database_url: str
    source: str
    host: str | None

    @property
    def host_display(self) -> str:
        return self.host or "unknown"

    @property
    def summary(self) -> str:
        return f"{self.target} (source: {self.source}, host: {self.host_display})"


def load_project_env(
    *,
    environ: MutableMapping[str, str] | None = None,
    repo_root: Path = REPO_ROOT,
    api_root: Path = API_ROOT,
) -> None:
    environment = os.environ if environ is None else environ
    protected_keys = set(environment.keys())
    _merge_env_file(
        repo_root / ".env",
        environment,
        protected_keys=protected_keys,
        override_loaded_values=False,
    )
    _merge_env_file(
        api_root / ".env",
        environment,
        protected_keys=protected_keys,
        override_loaded_values=True,
    )


def resolve_database_target(environ: Mapping[str, str] | None = None) -> DatabaseTarget:
    environment = os.environ if environ is None else environ
    raw_target = environment.get(TENUE_DB_TARGET_ENV, LOCAL_DB_TARGET).strip().lower()
    if raw_target not in {LOCAL_DB_TARGET, REMOTE_DB_TARGET}:
        raise DatabaseTargetResolutionError(
            f"{TENUE_DB_TARGET_ENV} must be either 'local' or 'remote'."
        )

    if raw_target == LOCAL_DB_TARGET:
        return DatabaseTarget(
            target=LOCAL_DB_TARGET,
            database_url=LOCAL_SUPABASE_DATABASE_URL,
            source="local default",
            host=_extract_host(LOCAL_SUPABASE_DATABASE_URL),
        )

    database_url = environment.get(DATABASE_URL_ENV, "").strip()
    if not database_url:
        raise DatabaseTargetResolutionError(
            f"{DATABASE_URL_ENV} must be set when {TENUE_DB_TARGET_ENV}=remote."
        )

    return DatabaseTarget(
        target=REMOTE_DB_TARGET,
        database_url=database_url,
        source=DATABASE_URL_ENV,
        host=_extract_host(database_url),
    )


def _merge_env_file(
    path: Path,
    environ: MutableMapping[str, str],
    *,
    protected_keys: set[str],
    override_loaded_values: bool,
) -> None:
    if not path.exists():
        return

    for key, value in dotenv_values(path).items():
        if value is None:
            continue

        normalized_key = str(key)
        normalized_value = str(value)
        if normalized_key in protected_keys:
            continue
        if override_loaded_values or normalized_key not in environ:
            environ[normalized_key] = normalized_value


def _extract_host(database_url: str) -> str | None:
    try:
        return make_url(database_url).host
    except Exception:
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the Tenue API database target.")
    parser.add_argument(
        "--field",
        choices=("database_url", "target", "source", "host", "summary"),
        default="summary",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        load_project_env()
        target = resolve_database_target()
    except DatabaseTargetResolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.field == "database_url":
        print(target.database_url)
    elif args.field == "target":
        print(target.target)
    elif args.field == "source":
        print(target.source)
    elif args.field == "host":
        print(target.host_display)
    else:
        print(target.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
