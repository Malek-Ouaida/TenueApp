from app.domains.wear.models import WearLogSnapshot


def test_wear_log_snapshot_uses_wear_log_id_as_primary_key() -> None:
    assert tuple(WearLogSnapshot.__table__.primary_key.columns.keys()) == ("wear_log_id",)
