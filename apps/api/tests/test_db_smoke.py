import pytest
from sqlalchemy import text


@pytest.mark.db_integration
def test_database_accepts_connections() -> None:
    from app.db.session import engine

    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()

    assert value == 1
