from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_outfits import create_outfit
from test_wear_logs import build_raw_fields, create_confirmed_item, create_wear_log

from app.domains.closet.models import ClosetItemMetadataProjection


def test_insight_routes_require_authentication_with_fixture(client: TestClient) -> None:
    endpoints = (
        "/insights/overview",
        "/insights/items",
        "/insights/outfits",
        "/insights/categories?start_date=2026-04-01&end_date=2026-04-07",
        "/insights/timeline?start_date=2026-04-01&end_date=2026-04-07",
        "/insights/stale-items",
        "/insights/never-worn",
    )

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required."}


def test_overview_item_usage_stale_and_never_worn(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="insights-overview@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Rotation tee",
        key_prefix="insights-overview-top",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Rotation trousers",
        key_prefix="insights-overview-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )
    shoes_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Stale sneakers",
        key_prefix="insights-overview-shoes",
        raw_fields=build_raw_fields(category="shoes", subcategory="sneakers", color="white"),
    )
    never_worn_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Never worn bag",
        key_prefix="insights-overview-never",
        raw_fields=build_raw_fields(category="bags", subcategory="tote", color="brown"),
    )
    archived_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Archived accessory",
        key_prefix="insights-overview-archived",
        raw_fields=build_raw_fields(category="accessories", subcategory="belt", color="black"),
    )

    archive_response = client.post(f"/closet/items/{archived_item_id}/archive", headers=headers)
    assert archive_response.status_code == 204

    for wear_date, items in (
        ("2026-03-01", [{"closet_item_id": str(shoes_item_id), "role": "shoes"}]),
        ("2026-04-10", [{"closet_item_id": str(bottom_item_id), "role": "bottom"}]),
        (
            "2026-04-18",
            [
                {"closet_item_id": str(top_item_id), "role": "top"},
                {"closet_item_id": str(bottom_item_id), "role": "bottom"},
            ],
        ),
        ("2026-04-19", [{"closet_item_id": str(top_item_id), "role": "top"}]),
        ("2026-04-20", [{"closet_item_id": str(top_item_id), "role": "top"}]),
    ):
        response = create_wear_log(client, headers, wear_date=wear_date, items=items)
        assert response.status_code == 201

    overview_response = client.get("/insights/overview?as_of_date=2026-04-20", headers=headers)
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["as_of_date"] == "2026-04-20"
    assert overview["all_time"] == {
        "total_wear_logs": 5,
        "total_worn_item_events": 6,
        "unique_items_worn": 3,
        "active_confirmed_closet_item_count": 4,
        "never_worn_item_count": 1,
    }
    assert overview["current_month"] == {
        "total_wear_logs": 4,
        "total_worn_item_events": 5,
        "unique_items_worn": 2,
        "active_closet_items_worn": 2,
        "active_closet_coverage_ratio": 0.5,
    }
    assert overview["streaks"] == {
        "current_streak_days": 3,
        "longest_streak_days": 3,
    }

    most_worn_response = client.get("/insights/items?sort=most_worn&limit=2", headers=headers)
    assert most_worn_response.status_code == 200
    most_worn = most_worn_response.json()
    assert [item["closet_item_id"] for item in most_worn["items"]] == [
        str(top_item_id),
        str(bottom_item_id),
    ]
    assert [item["wear_count"] for item in most_worn["items"]] == [3, 2]
    assert most_worn["next_cursor"] is not None

    second_page_response = client.get(
        f"/insights/items?sort=most_worn&limit=2&cursor={most_worn['next_cursor']}",
        headers=headers,
    )
    assert second_page_response.status_code == 200
    assert [item["closet_item_id"] for item in second_page_response.json()["items"]] == [
        str(shoes_item_id)
    ]

    least_worn_response = client.get("/insights/items?sort=least_worn", headers=headers)
    assert least_worn_response.status_code == 200
    least_worn = least_worn_response.json()["items"]
    assert [item["closet_item_id"] for item in least_worn] == [
        str(shoes_item_id),
        str(bottom_item_id),
        str(top_item_id),
    ]

    stale_response = client.get(
        "/insights/stale-items?as_of_date=2026-04-20&stale_after_days=30",
        headers=headers,
    )
    assert stale_response.status_code == 200
    stale_items = stale_response.json()["items"]
    assert len(stale_items) == 1
    assert stale_items[0]["closet_item_id"] == str(shoes_item_id)
    assert stale_items[0]["wear_count"] == 1
    assert stale_items[0]["days_since_last_worn"] == 50

    never_worn_response = client.get("/insights/never-worn", headers=headers)
    assert never_worn_response.status_code == 200
    never_worn_items = never_worn_response.json()["items"]
    assert [item["closet_item_id"] for item in never_worn_items] == [str(never_worn_item_id)]


def test_outfit_usage_counts_only_saved_outfit_logs(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="insights-outfits@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Outfit tee",
        key_prefix="insights-outfits-top",
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Outfit trouser",
        key_prefix="insights-outfits-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="grey"),
    )

    outfit_response = create_outfit(
        client,
        headers,
        title="Office uniform",
        items=[
            {"closet_item_id": str(top_item_id), "role": "top"},
            {"closet_item_id": str(bottom_item_id), "role": "bottom"},
        ],
        is_favorite=True,
    )
    assert outfit_response.status_code == 201
    outfit_id = outfit_response.json()["id"]

    for wear_date in ("2026-04-15", "2026-04-16"):
        response = create_wear_log(
            client,
            headers,
            wear_date=wear_date,
            outfit_id=outfit_id,
        )
        assert response.status_code == 201

    manual_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-17",
        items=[
            {"closet_item_id": str(top_item_id), "role": "top"},
            {"closet_item_id": str(bottom_item_id), "role": "bottom"},
        ],
    )
    assert manual_response.status_code == 201

    archive_response = client.post(f"/outfits/{outfit_id}/archive", headers=headers)
    assert archive_response.status_code == 204

    usage_response = client.get("/insights/outfits", headers=headers)
    assert usage_response.status_code == 200
    body = usage_response.json()
    assert body["next_cursor"] is None
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == outfit_id
    assert body["items"][0]["wear_count"] == 2
    assert body["items"][0]["first_worn_date"] == "2026-04-15"
    assert body["items"][0]["last_worn_date"] == "2026-04-16"
    assert body["items"][0]["is_archived"] is True
    assert body["items"][0]["item_count"] == 2


def test_category_usage_and_timeline_read_from_snapshots(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="insights-snapshots@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Snapshot top",
        key_prefix="insights-snapshots-top",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Snapshot bottom",
        key_prefix="insights-snapshots-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )

    first_wear = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[
            {"closet_item_id": str(top_item_id), "role": "top"},
            {"closet_item_id": str(bottom_item_id), "role": "bottom"},
        ],
    )
    second_wear = create_wear_log(
        client,
        headers,
        wear_date="2026-04-07",
        items=[{"closet_item_id": str(top_item_id), "role": "top"}],
    )
    assert first_wear.status_code == 201
    assert second_wear.status_code == 201

    projection = db_session.execute(
        select(ClosetItemMetadataProjection).where(
            ClosetItemMetadataProjection.closet_item_id == UUID(str(top_item_id))
        )
    ).scalar_one()
    projection.category = "outerwear"
    db_session.commit()

    categories_response = client.get(
        "/insights/categories?start_date=2026-04-06&end_date=2026-04-08",
        headers=headers,
    )
    assert categories_response.status_code == 200
    categories = categories_response.json()["items"]
    assert categories == [
        {
            "category": "tops",
            "wear_count": 2,
            "unique_item_count": 1,
            "last_worn_date": "2026-04-07",
        },
        {
            "category": "bottoms",
            "wear_count": 1,
            "unique_item_count": 1,
            "last_worn_date": "2026-04-06",
        },
    ]

    timeline_response = client.get(
        "/insights/timeline?start_date=2026-04-06&end_date=2026-04-08",
        headers=headers,
    )
    assert timeline_response.status_code == 200
    assert timeline_response.json()["points"] == [
        {
            "date": "2026-04-06",
            "wear_log_count": 1,
            "worn_item_count": 2,
            "unique_item_count": 2,
        },
        {
            "date": "2026-04-07",
            "wear_log_count": 1,
            "worn_item_count": 1,
            "unique_item_count": 1,
        },
        {
            "date": "2026-04-08",
            "wear_log_count": 0,
            "worn_item_count": 0,
            "unique_item_count": 0,
        },
    ]


def test_insight_reads_degrade_when_presigned_download_generation_fails(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    monkeypatch: Any,
) -> None:
    headers = register_and_get_headers(client, email="insights-presign-failure@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Fallback tee",
        key_prefix="insights-presign-top",
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Fallback trouser",
        key_prefix="insights-presign-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )

    outfit_response = create_outfit(
        client,
        headers,
        title="Fallback uniform",
        items=[
            {"closet_item_id": str(top_item_id), "role": "top"},
            {"closet_item_id": str(bottom_item_id), "role": "bottom"},
        ],
        is_favorite=True,
    )
    assert outfit_response.status_code == 201

    wear_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-21",
        outfit_id=outfit_response.json()["id"],
    )
    assert wear_response.status_code == 201

    def fail_presigned_download(*, bucket: str, key: str, expires_in_seconds: int):
        raise RuntimeError(f"unable to presign {bucket}/{key}")

    monkeypatch.setattr(
        fake_storage_client,
        "generate_presigned_download",
        fail_presigned_download,
    )

    items_response = client.get("/insights/items", headers=headers)
    assert items_response.status_code == 200
    assert items_response.json()["items"][0]["display_image"] is None

    outfits_response = client.get("/insights/outfits", headers=headers)
    assert outfits_response.status_code == 200
    assert outfits_response.json()["items"][0]["cover_image"] is None

    never_worn_response = client.get("/insights/never-worn", headers=headers)
    assert never_worn_response.status_code == 200

    timeline_response = client.get(
        "/insights/timeline?start_date=2026-04-21&end_date=2026-04-21",
        headers=headers,
    )
    assert timeline_response.status_code == 200
    assert timeline_response.json()["points"][0]["wear_log_count"] == 1
