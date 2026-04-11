from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings

API_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_DIRECTORY = API_ROOT / "alembic"
MIGRATION_UPGRADE_COMMAND = "cd apps/api && PYTHONPATH=. .venv/bin/alembic upgrade head"


@dataclass(frozen=True)
class DatabaseFailure:
    code: str
    status_code: int
    message: str
    expected_revisions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DatabaseSchemaStatus:
    status: Literal["ok", "error", "skipped"]
    current_revisions: tuple[str, ...]
    expected_revisions: tuple[str, ...]
    detail: str | None


@lru_cache(maxsize=1)
def get_expected_database_revisions() -> tuple[str, ...]:
    return tuple(sorted(ScriptDirectory(str(ALEMBIC_DIRECTORY)).get_heads()))


def get_database_schema_status(session: Session) -> DatabaseSchemaStatus:
    expected_revisions = get_expected_database_revisions()
    bind = session.get_bind()
    if bind is None:
        return DatabaseSchemaStatus(
            status="error",
            current_revisions=(),
            expected_revisions=expected_revisions,
            detail="Database bind is unavailable for schema-version checks.",
        )

    if bind.dialect.name != "postgresql":
        return DatabaseSchemaStatus(
            status="skipped",
            current_revisions=(),
            expected_revisions=expected_revisions,
            detail="Schema version checks are skipped for non-PostgreSQL test databases.",
        )

    connection = session.connection()
    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        return DatabaseSchemaStatus(
            status="error",
            current_revisions=(),
            expected_revisions=expected_revisions,
            detail=build_schema_mismatch_message(
                current_revisions=(),
                expected_revisions=expected_revisions,
            ),
        )

    current_revisions = tuple(
        sorted(
            str(version_num)
            for version_num in session.execute(text("SELECT version_num FROM alembic_version"))
            .scalars()
            .all()
            if version_num
        )
    )
    if current_revisions == expected_revisions:
        return DatabaseSchemaStatus(
            status="ok",
            current_revisions=current_revisions,
            expected_revisions=expected_revisions,
            detail=None,
        )

    return DatabaseSchemaStatus(
        status="error",
        current_revisions=current_revisions,
        expected_revisions=expected_revisions,
        detail=build_schema_mismatch_message(
            current_revisions=current_revisions,
            expected_revisions=expected_revisions,
        ),
    )


def classify_database_failure(exc: Exception) -> DatabaseFailure | None:
    normalized_message = _normalize_error_message(exc)
    expected_revisions = get_expected_database_revisions()

    if _looks_like_schema_mismatch(normalized_message):
        return DatabaseFailure(
            code="database_schema_out_of_date",
            status_code=503,
            message=build_schema_mismatch_message(expected_revisions=expected_revisions),
            expected_revisions=expected_revisions,
        )

    if _looks_like_connection_failure(normalized_message):
        return DatabaseFailure(
            code="database_unavailable",
            status_code=503,
            message=(
                "Database connectivity failed. Confirm the intended database target is running, "
                "reachable, and matches this API process."
            ),
        )

    return None


def build_schema_mismatch_message(
    *,
    current_revisions: tuple[str, ...] | None = None,
    expected_revisions: tuple[str, ...] | None = None,
) -> str:
    resolved_expected_revisions = expected_revisions or get_expected_database_revisions()
    revision_detail = ""
    if current_revisions is not None:
        current_label = ", ".join(current_revisions) if current_revisions else "none"
        expected_label = ", ".join(resolved_expected_revisions)
        revision_detail = (
            f" Current revision(s): {current_label}. Expected revision(s): {expected_label}."
        )

    target_detail = (
        " Resolved API database target: "
        f"{settings.database_target} (source: {settings.database_source}, "
        f"host: {settings.database_host or 'unknown'})."
    )

    return (
        "Database schema is incompatible with this API build."
        f"{revision_detail}{target_detail} Run `{MIGRATION_UPGRADE_COMMAND}` against the same "
        "database target and restart the API. If the database is already at the expected "
        "revision, check for model/schema drift between SQLAlchemy models and Alembic migrations."
    )


def _normalize_error_message(exc: Exception) -> str:
    parts = [str(exc)]
    original_exc = getattr(exc, "orig", None)
    if original_exc is not None:
        parts.append(str(original_exc))

    return " ".join(part for part in parts if part).lower()


def _looks_like_schema_mismatch(normalized_message: str) -> bool:
    if "undefinedcolumn" in normalized_message or "undefinedtable" in normalized_message:
        return True

    if "alembic_version" in normalized_message and "does not exist" in normalized_message:
        return True

    return (
        ("column " in normalized_message and "does not exist" in normalized_message)
        or ("relation " in normalized_message and "does not exist" in normalized_message)
    )


def _looks_like_connection_failure(normalized_message: str) -> bool:
    return any(
        marker in normalized_message
        for marker in (
            "connection refused",
            "connection is bad",
            "could not connect",
            "failed to connect",
            "operation not permitted",
        )
    )
