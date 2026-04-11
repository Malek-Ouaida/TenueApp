from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_closet_browse import (
    confirm_item_with_changes,
    create_normalized_review_item_for_user,
    create_uploaded_item,
    register_and_get_headers,
)

from app.domains.closet.repository import ClosetRepository
from app.domains.wear.models import WearLog, WearLogSnapshot


def wear_log_headers(access_headers: dict[str, str]) -> dict[str, str]:
    return access_headers


def build_raw_fields(*, category: str = "top", subcategory: str = "tee shirt", color: str = "navy"):
    return {
        "category": {"value": category, "confidence": 0.98, "applicability_state": "value"},
        "subcategory": {
            "value": subcategory,
            "confidence": 0.97,
            "applicability_state": "value",
        },
        "colors": {"value": [color], "confidence": 0.92, "applicability_state": "value"},
    }


def create_confirmed_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    headers: dict[str, str],
    title: str,
    key_prefix: str,
    raw_fields: dict[str, Any] | None = None,
) -> UUID:
    item_id = create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        raw_fields=raw_fields or build_raw_fields(),
        title=title,
        key_prefix=key_prefix,
    )
    confirm_item_with_changes(
        client,
        headers,
        item_id=item_id,
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
            {"field_name": "colors", "operation": "accept_suggestion"},
        ],
    )
    return item_id


def create_wear_log(
    client: TestClient,
    headers: dict[str, str],
    *,
    wear_date: str,
    mode: str | None = None,
    items: Sequence[dict[str, Any]] | None = None,
    outfit_id: str | None = None,
    worn_at: str | None = None,
    captured_at: str | None = None,
    timezone_name: str | None = None,
    context: str | None = "casual",
    vibe: str | None = None,
    notes: str | None = "Logged from tests.",
):
    payload: dict[str, Any] = {"wear_date": wear_date}
    if mode == "photo_upload":
        payload["mode"] = "photo_upload"
    elif outfit_id is not None:
        payload["mode"] = "saved_outfit"
        payload["outfit_id"] = outfit_id
    else:
        payload["mode"] = "manual_items"
        payload["items"] = list(items or [])
    if worn_at is not None:
        payload["worn_at"] = worn_at
    if captured_at is not None:
        payload["captured_at"] = captured_at
    if timezone_name is not None:
        payload["timezone_name"] = timezone_name
    if context is not None:
        payload["context"] = context
    if vibe is not None:
        payload["vibe"] = vibe
    if notes is not None:
        payload["notes"] = notes
    return client.post("/wear-logs", headers=wear_log_headers(headers), json=payload)


def test_wear_log_routes_require_authentication_with_fixture(client: TestClient) -> None:
    list_response = client.get("/wear-logs")
    create_response = client.post(
        "/wear-logs",
        json={"wear_date": "2026-04-06", "mode": "manual_items", "items": []},
    )
    calendar_response = client.get("/wear-logs/calendar?start_date=2026-04-01&end_date=2026-04-07")

    assert list_response.status_code == 401
    assert list_response.json() == {"detail": "Authentication required."}
    assert create_response.status_code == 401
    assert create_response.json() == {"detail": "Authentication required."}
    assert calendar_response.status_code == 401
    assert calendar_response.json() == {"detail": "Authentication required."}


def test_create_wear_log_from_confirmed_manual_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-create@example.com")
    first_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Navy tee",
        key_prefix="wear-create-first",
        raw_fields=build_raw_fields(color="navy"),
    )
    second_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Stone trousers",
        key_prefix="wear-create-second",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="beige"),
    )

    response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        context="work",
        notes="Office day",
        items=[
            {"closet_item_id": str(first_item_id), "role": "top", "sort_index": 4},
            {"closet_item_id": str(second_item_id), "role": "bottom", "sort_index": 0},
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["wear_date"] == "2026-04-06"
    assert body["source"] == "manual_items"
    assert body["context"] == "work"
    assert body["notes"] == "Office day"
    assert body["is_confirmed"] is True
    assert body["item_count"] == 2
    assert body["cover_image"] is not None
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(second_item_id),
        str(first_item_id),
    ]
    assert [item["sort_index"] for item in body["items"]] == [0, 1]
    assert body["items"][0]["primary_color"] == "beige"
    assert body["items"][1]["primary_color"] == "navy"


def test_create_wear_log_rejects_unconfirmed_items(
    client: TestClient,
    fake_storage_client: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-unconfirmed@example.com")
    unconfirmed_item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="wear-unconfirmed-draft",
        complete_key="wear-unconfirmed-complete",
        title="Still in review",
    )

    response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(unconfirmed_item_id), "role": "top"}],
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "One or more closet items could not be found for confirmed wear logging."
    }


def test_create_wear_log_rejects_cross_user_references(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    owner_headers = register_and_get_headers(client, email="wear-owner@example.com")
    intruder_headers = register_and_get_headers(client, email="wear-intruder@example.com")
    owner_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=owner_headers,
        title="Owner item",
        key_prefix="wear-owner-item",
    )

    response = create_wear_log(
        client,
        intruder_headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(owner_item_id), "role": "top"}],
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "One or more closet items could not be found for confirmed wear logging."
    }


def test_create_wear_log_rejects_duplicate_item_ids(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-duplicate@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Duplicate tee",
        key_prefix="wear-duplicate-item",
    )

    response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[
            {"closet_item_id": str(item_id), "role": "top"},
            {"closet_item_id": str(item_id), "role": "other"},
        ],
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Each closet item can appear at most once in a single wear log."
    }


def test_create_wear_log_allows_multiple_logs_on_same_date(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-date-conflict@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Date conflict tee",
        key_prefix="wear-date-conflict-item",
    )

    first_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        worn_at="2026-04-06T09:00:00Z",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    second_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        worn_at="2026-04-06T19:00:00Z",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] != second_response.json()["id"]

    day_logs_response = client.get("/wear-logs?wear_date=2026-04-06", headers=headers)
    assert day_logs_response.status_code == 200
    assert [item["worn_at"] for item in day_logs_response.json()["items"]] == [
        "2026-04-06T19:00:00Z",
        "2026-04-06T09:00:00Z",
    ]

    calendar_response = client.get(
        "/wear-logs/calendar?start_date=2026-04-06&end_date=2026-04-06",
        headers=headers,
    )
    assert calendar_response.status_code == 200
    day = calendar_response.json()["days"][0]
    assert day["event_count"] == 2
    assert day["primary_event_id"] == second_response.json()["id"]
    assert [event["id"] for event in day["events"]] == [
        second_response.json()["id"],
        first_response.json()["id"],
    ]


def test_wear_log_detail_and_timeline_pagination(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-timeline@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Timeline tee",
        key_prefix="wear-timeline-item",
    )

    created_ids: list[str] = []
    for wear_date in ("2026-04-03", "2026-04-04", "2026-04-05"):
        response = create_wear_log(
            client,
            headers,
            wear_date=wear_date,
            items=[{"closet_item_id": str(item_id), "role": "top"}],
            notes=f"Logged {wear_date}",
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    detail_response = client.get(f"/wear-logs/{created_ids[-1]}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["notes"] == "Logged 2026-04-05"

    first_page = client.get("/wear-logs?limit=2", headers=headers)
    assert first_page.status_code == 200
    first_page_body = first_page.json()
    assert [item["wear_date"] for item in first_page_body["items"]] == ["2026-04-05", "2026-04-04"]
    assert first_page_body["next_cursor"] is not None

    second_page = client.get(
        f"/wear-logs?limit=2&cursor={first_page_body['next_cursor']}",
        headers=headers,
    )
    assert second_page.status_code == 200
    assert [item["wear_date"] for item in second_page.json()["items"]] == ["2026-04-03"]


def test_wear_log_reads_degrade_when_presigned_download_generation_fails(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    monkeypatch: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-presign-failure@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Fallback wear tee",
        key_prefix="wear-presign-item",
    )

    create_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-08",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    assert create_response.status_code == 201
    wear_log_id = create_response.json()["id"]

    def fail_presigned_download(*, bucket: str, key: str, expires_in_seconds: int):
        raise RuntimeError(f"unable to presign {bucket}/{key}")

    monkeypatch.setattr(
        fake_storage_client,
        "generate_presigned_download",
        fail_presigned_download,
    )

    timeline_response = client.get("/wear-logs", headers=headers)
    assert timeline_response.status_code == 200
    assert timeline_response.json()["items"][0]["id"] == wear_log_id
    assert timeline_response.json()["items"][0]["cover_image"] is None

    detail_response = client.get(f"/wear-logs/{wear_log_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["cover_image"] is None
    assert detail_response.json()["items"][0]["display_image"] is None

    calendar_response = client.get(
        "/wear-logs/calendar?start_date=2026-04-08&end_date=2026-04-08",
        headers=headers,
    )
    assert calendar_response.status_code == 200
    assert calendar_response.json()["days"][0]["cover_image"] is None


def test_update_wear_log_metadata_only(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-update-meta@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Metadata tee",
        key_prefix="wear-update-meta-item",
    )
    create_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
        context="casual",
        notes="Before patch",
    )
    wear_log_id = create_response.json()["id"]

    response = client.patch(
        f"/wear-logs/{wear_log_id}",
        headers=headers,
        json={"context": "travel", "notes": "After patch"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["context"] == "travel"
    assert body["notes"] == "After patch"
    assert body["item_count"] == 1
    assert body["items"][0]["closet_item_id"] == str(item_id)


def test_update_wear_log_replaces_composition_atomically(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-update-items@example.com")
    first_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="First tee",
        key_prefix="wear-update-items-first",
    )
    second_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Second trouser",
        key_prefix="wear-update-items-second",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )
    third_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Third shoes",
        key_prefix="wear-update-items-third",
        raw_fields=build_raw_fields(category="shoes", subcategory="sneakers", color="white"),
    )
    create_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(first_item_id), "role": "top"}],
    )
    wear_log_id = create_response.json()["id"]

    response = client.patch(
        f"/wear-logs/{wear_log_id}",
        headers=headers,
        json={
            "items": [
                {"closet_item_id": str(third_item_id), "role": "shoes", "sort_index": 5},
                {"closet_item_id": str(second_item_id), "role": "bottom", "sort_index": 0},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(second_item_id),
        str(third_item_id),
    ]
    assert [item["sort_index"] for item in body["items"]] == [0, 1]

    snapshot = db_session.execute(
        select(WearLogSnapshot).where(WearLogSnapshot.wear_log_id == UUID(wear_log_id))
    ).scalar_one()
    assert [item["closet_item_id"] for item in snapshot.items_snapshot_json] == [
        str(second_item_id),
        str(third_item_id),
    ]


def test_update_wear_log_can_move_event_onto_a_date_with_other_events(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-patch-date@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Patch date tee",
        key_prefix="wear-patch-date-item",
    )
    first_log = create_wear_log(
        client,
        headers,
        wear_date="2026-04-05",
        worn_at="2026-04-05T10:00:00Z",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    second_log = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        worn_at="2026-04-06T18:00:00Z",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )

    response = client.patch(
        f"/wear-logs/{first_log.json()['id']}",
        headers=headers,
        json={"wear_date": "2026-04-06"},
    )

    assert second_log.status_code == 201
    assert response.status_code == 200
    assert response.json()["wear_date"] == "2026-04-06"

    day_logs_response = client.get("/wear-logs?wear_date=2026-04-06", headers=headers)
    assert day_logs_response.status_code == 200
    assert {item["id"] for item in day_logs_response.json()["items"]} == {
        first_log.json()["id"],
        second_log.json()["id"],
    }


def test_delete_wear_log_removes_it(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-delete@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Delete tee",
        key_prefix="wear-delete-item",
    )
    create_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    wear_log_id = create_response.json()["id"]

    delete_response = client.delete(f"/wear-logs/{wear_log_id}", headers=headers)
    detail_response = client.get(f"/wear-logs/{wear_log_id}", headers=headers)
    existing_log = db_session.execute(
        select(WearLog).where(WearLog.id == UUID(wear_log_id))
    ).scalar_one_or_none()

    assert delete_response.status_code == 204
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": "Wear log not found."}
    assert existing_log is None


def test_calendar_returns_populated_and_empty_days(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-calendar@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Calendar tee",
        key_prefix="wear-calendar-item",
    )
    for wear_date in ("2026-04-02", "2026-04-04"):
        response = create_wear_log(
            client,
            headers,
            wear_date=wear_date,
            items=[{"closet_item_id": str(item_id), "role": "top"}],
        )
        assert response.status_code == 201

    response = client.get(
        "/wear-logs/calendar?start_date=2026-04-01&end_date=2026-04-04",
        headers=headers,
    )

    assert response.status_code == 200
    days = response.json()["days"]
    assert [day["date"] for day in days] == [
        "2026-04-01",
        "2026-04-02",
        "2026-04-03",
        "2026-04-04",
    ]
    assert [day["has_wear_log"] for day in days] == [False, True, False, True]
    assert days[1]["cover_image"] is not None
    assert days[0]["cover_image"] is None


def test_snapshot_stability_uses_logged_metadata_not_current_closet_projection(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-snapshot@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Original title",
        key_prefix="wear-snapshot-item",
        raw_fields=build_raw_fields(color="green"),
    )
    create_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    wear_log_id = create_response.json()["id"]

    closet_repository = ClosetRepository(db_session)
    projection = closet_repository.get_metadata_projection(item_id=item_id)
    assert projection is not None
    projection.title = "Changed title"
    projection.primary_color = "black"
    db_session.commit()

    detail_response = client.get(f"/wear-logs/{wear_log_id}", headers=headers)

    assert detail_response.status_code == 200
    item = detail_response.json()["items"][0]
    assert item["title"] == "Original title"
    assert item["primary_color"] == "green"


def test_create_wear_log_from_saved_outfit_includes_link_and_outfit_titles(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-saved-outfit@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Cream knit",
        key_prefix="wear-saved-outfit-top",
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Black trousers",
        key_prefix="wear-saved-outfit-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )

    outfit_response = client.post(
        "/outfits",
        headers=headers,
        json={
            "title": "Office uniform",
            "occasion": "work",
            "is_favorite": True,
            "items": [
                {"closet_item_id": str(top_item_id), "role": "top", "sort_index": 9},
                {"closet_item_id": str(bottom_item_id), "role": "bottom", "sort_index": 0},
            ],
        },
    )
    assert outfit_response.status_code == 201
    outfit = outfit_response.json()

    response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        outfit_id=outfit["id"],
        context="work",
        notes="Logged from outfit",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "saved_outfit"
    assert body["linked_outfit"] == {
        "id": outfit["id"],
        "title": "Office uniform",
        "is_favorite": True,
        "is_archived": False,
    }
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(bottom_item_id),
        str(top_item_id),
    ]

    snapshot = db_session.execute(
        select(WearLogSnapshot).where(WearLogSnapshot.wear_log_id == UUID(body["id"]))
    ).scalar_one()
    assert snapshot.outfit_title_snapshot == "Office uniform"

    timeline_response = client.get("/wear-logs", headers=headers)
    assert timeline_response.status_code == 200
    assert timeline_response.json()["items"][0]["outfit_title"] == "Office uniform"

    calendar_response = client.get(
        "/wear-logs/calendar?start_date=2026-04-06&end_date=2026-04-06",
        headers=headers,
    )
    assert calendar_response.status_code == 200
    assert calendar_response.json()["days"][0]["outfit_title"] == "Office uniform"


def test_updating_saved_outfit_wear_log_items_clears_outfit_link_and_marks_mixed(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-mixed-patch@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Patch top",
        key_prefix="wear-mixed-patch-top",
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Patch bottom",
        key_prefix="wear-mixed-patch-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="gray"),
    )
    shoes_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Patch shoes",
        key_prefix="wear-mixed-patch-shoes",
        raw_fields=build_raw_fields(category="shoes", subcategory="sneakers", color="white"),
    )

    outfit_response = client.post(
        "/outfits",
        headers=headers,
        json={
            "title": "Patch outfit",
            "items": [
                {"closet_item_id": str(top_item_id), "role": "top"},
                {"closet_item_id": str(bottom_item_id), "role": "bottom"},
            ],
        },
    )
    assert outfit_response.status_code == 201
    outfit_id = outfit_response.json()["id"]

    create_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        outfit_id=outfit_id,
    )
    assert create_response.status_code == 201
    wear_log_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/wear-logs/{wear_log_id}",
        headers=headers,
        json={
            "items": [
                {"closet_item_id": str(shoes_item_id), "role": "shoes", "sort_index": 5},
                {"closet_item_id": str(bottom_item_id), "role": "bottom", "sort_index": 0},
            ]
        },
    )

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["source"] == "mixed"
    assert body["linked_outfit"] is None
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(bottom_item_id),
        str(shoes_item_id),
    ]

    wear_log = db_session.execute(
        select(WearLog).where(WearLog.id == UUID(wear_log_id))
    ).scalar_one()
    snapshot = db_session.execute(
        select(WearLogSnapshot).where(WearLogSnapshot.wear_log_id == UUID(wear_log_id))
    ).scalar_one()
    assert wear_log.outfit_id is None
    assert snapshot.outfit_title_snapshot is None
