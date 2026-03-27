import os
import site
import subprocess
from pathlib import Path

import pytest

from app.core.db_target import (
    LOCAL_DB_TARGET,
    LOCAL_SUPABASE_DATABASE_URL,
    REMOTE_DB_TARGET,
    DatabaseTargetResolutionError,
    load_project_env,
    resolve_database_target,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
UV_BIN = Path(site.getuserbase()) / "bin" / "uv"


def test_resolve_database_target_defaults_to_local() -> None:
    target = resolve_database_target({})

    assert target.target == LOCAL_DB_TARGET
    assert target.database_url == LOCAL_SUPABASE_DATABASE_URL
    assert target.source == "local default"
    assert target.host == "127.0.0.1"


def test_resolve_database_target_requires_database_url_for_remote() -> None:
    with pytest.raises(
        DatabaseTargetResolutionError,
        match="DATABASE_URL must be set when TENUE_DB_TARGET=remote.",
    ):
        resolve_database_target({"TENUE_DB_TARGET": REMOTE_DB_TARGET})


def test_load_project_env_keeps_exported_env_values(tmp_path: Path) -> None:
    environ = {
        "TENUE_DB_TARGET": REMOTE_DB_TARGET,
        "DATABASE_URL": "postgresql+psycopg://shell:shell@127.0.0.1:6543/shelldb",
    }
    repo_root, api_root = _make_env_tree(
        root_env="TENUE_DB_TARGET=remote\nDATABASE_URL=postgresql+psycopg://root:root@127.0.0.1:1111/rootdb\n",
        api_env="DATABASE_URL=postgresql+psycopg://api:api@127.0.0.1:2222/apidb\n",
        tmp_path=tmp_path,
    )

    load_project_env(environ=environ, repo_root=repo_root, api_root=api_root)

    target = resolve_database_target(environ)
    assert target.target == REMOTE_DB_TARGET
    assert target.database_url == "postgresql+psycopg://shell:shell@127.0.0.1:6543/shelldb"
    assert target.host == "127.0.0.1"


def test_api_env_overrides_root_env_for_unset_values(tmp_path: Path) -> None:
    repo_root, api_root = _make_env_tree(
        root_env="TENUE_DB_TARGET=remote\nDATABASE_URL=postgresql+psycopg://root:root@127.0.0.1:1111/rootdb\n",
        api_env="DATABASE_URL=postgresql+psycopg://api:api@127.0.0.1:2222/apidb\n",
        tmp_path=tmp_path,
    )
    environ: dict[str, str] = {}

    load_project_env(environ=environ, repo_root=repo_root, api_root=api_root)

    target = resolve_database_target(environ)
    assert target.target == REMOTE_DB_TARGET
    assert target.database_url == "postgresql+psycopg://api:api@127.0.0.1:2222/apidb"
    assert target.host == "127.0.0.1"


def test_db_target_cli_defaults_to_local_when_only_database_url_is_set() -> None:
    env = _subprocess_env()
    env.pop("TENUE_DB_TARGET", None)
    env["DATABASE_URL"] = "postgresql+psycopg://remote:remote@db.example.com:5432/remotedb"

    result = subprocess.run(
        [str(UV_BIN), "run", "python", "-m", "app.core.db_target", "--field", "summary"],
        cwd=API_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "local (source: local default, host: 127.0.0.1)"


def test_migrate_script_blocks_remote_without_explicit_allow() -> None:
    env = _subprocess_env()
    env["TENUE_DB_TARGET"] = REMOTE_DB_TARGET
    env["DATABASE_URL"] = "postgresql+psycopg://remote:remote@db.example.com:5432/remotedb"
    env.pop("TENUE_ALLOW_REMOTE_MIGRATIONS", None)

    result = subprocess.run(
        ["bash", "scripts/api/migrate.sh"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Resolved API database target: remote" in result.stdout
    assert "Remote migrations are blocked by default." in result.stdout


def _make_env_tree(
    *,
    root_env: str,
    api_env: str,
    tmp_path: Path,
) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    api_root = repo_root / "apps" / "api"
    repo_root.mkdir(parents=True, exist_ok=True)
    api_root.mkdir(parents=True, exist_ok=True)
    (repo_root / ".env").write_text(root_env, encoding="utf-8")
    (api_root / ".env").write_text(api_env, encoding="utf-8")
    return repo_root, api_root


def _subprocess_env() -> dict[str, str]:
    environment = dict(os.environ)
    environment["UV_CACHE_DIR"] = str(REPO_ROOT / ".uv-cache")
    environment["PATH"] = f"{UV_BIN.parent}:{environment.get('PATH', '')}"
    return environment
