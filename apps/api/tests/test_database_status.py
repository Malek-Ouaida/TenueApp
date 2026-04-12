from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.database_status import (
    classify_database_failure,
    get_database_schema_status,
    get_expected_database_revisions,
)
from app.main import app

if not any(route.path == "/_tests/database-schema-error" for route in app.router.routes):

    @app.get("/_tests/database-schema-error")
    def read_test_database_schema_error() -> None:
        raise ProgrammingError(
            "SELECT closet_items.archived_at FROM closet_items",
            {},
            Exception('column "archived_at" does not exist'),
        )


def test_expected_database_revisions_resolve_current_head() -> None:
    assert get_expected_database_revisions() == ("0018_lookbook_hardening_constraints",)


def test_database_schema_status_skips_sqlite_test_sessions(db_session) -> None:
    status = get_database_schema_status(db_session)

    assert status.status == "skipped"
    assert status.current_revisions == ()
    assert status.expected_revisions == ("0018_lookbook_hardening_constraints",)


def test_classify_database_failure_reports_schema_drift() -> None:
    failure = classify_database_failure(
        ProgrammingError(
            "SELECT closet_items.archived_at FROM closet_items",
            {},
            Exception('column "archived_at" does not exist'),
        )
    )

    assert failure is not None
    assert failure.code == "database_schema_out_of_date"
    assert failure.status_code == 503
    assert failure.expected_revisions == ("0018_lookbook_hardening_constraints",)
    assert "alembic upgrade head" in failure.message
    assert "Resolved API database target:" in failure.message


def test_classify_database_failure_reports_connectivity_issues() -> None:
    failure = classify_database_failure(
        OperationalError(
            "SELECT 1",
            {},
            Exception(
                'connection to server at "127.0.0.1", port 54322 failed: Operation not permitted'
            ),
        )
    )

    assert failure is not None
    assert failure.code == "database_unavailable"
    assert failure.status_code == 503


def test_database_schema_failures_return_json_with_cors_headers(client: TestClient) -> None:
    response = client.get(
        "/_tests/database-schema-error",
        headers={"Origin": "http://localhost:8081"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "database_schema_out_of_date"
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
    assert response.headers["x-request-id"]
