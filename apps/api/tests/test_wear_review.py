from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_wear_logs import build_raw_fields, create_confirmed_item
from test_wear_processing import (
    build_test_image_bytes,
    create_photo_wear_log,
    finalize_photo_upload,
    run_wear_worker_once,
)

from app.core.storage import InMemoryStorageClient
from app.domains.wear.detection import DetectedOutfitItem


def test_confirm_review_persists_photo_wear_event_for_calendar_and_insights(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    fake_wear_detection_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-review-confirm@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Review tee",
        key_prefix="wear-review-top",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Review trousers",
        key_prefix="wear-review-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )

    wear_log = create_photo_wear_log(
        client,
        headers,
        wear_date="2026-04-11",
        worn_at="2026-04-11T19:30:00Z",
    )
    finalize_photo_upload(
        client,
        fake_storage_client,
        headers,
        wear_log_id=wear_log["id"],
        image_bytes=build_test_image_bytes(color="black"),
    )
    fake_wear_detection_provider.succeed(
        detections=[
            DetectedOutfitItem(
                role="top",
                category="top",
                subcategory="tee shirt",
                colors=["navy"],
                material=None,
                pattern=None,
                fit_tags=[],
                silhouette=None,
                attributes=[],
                confidence=0.97,
                bbox={"left": 0.1, "top": 0.05, "width": 0.75, "height": 0.32},
            ),
            DetectedOutfitItem(
                role="bottom",
                category="bottom",
                subcategory="trousers",
                colors=["black"],
                material=None,
                pattern=None,
                fit_tags=[],
                silhouette=None,
                attributes=[],
                confidence=0.96,
                bbox={"left": 0.18, "top": 0.42, "width": 0.64, "height": 0.45},
            ),
        ]
    )
    run_wear_worker_once(db_session, fake_storage_client, fake_wear_detection_provider)

    review_detail = client.get(f"/wear-logs/{wear_log['id']}", headers=headers).json()
    confirm_response = client.post(
        f"/wear-logs/{wear_log['id']}/confirm",
        headers=headers,
        json={
            "expected_review_version": review_detail["review_version"],
            "notes": "Confirmed from OOTD",
            "items": [
                {
                    "closet_item_id": str(top_item_id),
                    "role": "top",
                    "detected_item_id": review_detail["detected_items"][0]["id"],
                },
                {
                    "closet_item_id": str(bottom_item_id),
                    "role": "bottom",
                    "detected_item_id": review_detail["detected_items"][1]["id"],
                },
            ],
        },
    )

    assert confirm_response.status_code == 200
    body = confirm_response.json()
    assert body["status"] == "confirmed"
    assert body["is_confirmed"] is True
    assert body["confirmed_at"] is not None
    assert body["item_count"] == 2
    assert body["notes"] == "Confirmed from OOTD"
    assert body["primary_photo"] is not None
    assert [item["detected_item_id"] for item in body["items"]] == [
        review_detail["detected_items"][0]["id"],
        review_detail["detected_items"][1]["id"],
    ]

    calendar_response = client.get(
        "/wear-logs/calendar?start_date=2026-04-11&end_date=2026-04-11",
        headers=headers,
    )
    assert calendar_response.status_code == 200
    day = calendar_response.json()["days"][0]
    assert day["event_count"] == 1
    assert day["primary_event_id"] == wear_log["id"]
    assert day["primary_cover_image"] is not None
    assert day["events"][0]["id"] == wear_log["id"]

    overview_response = client.get("/insights/overview?as_of_date=2026-04-11", headers=headers)
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["all_time"]["total_wear_logs"] == 1
    assert overview["all_time"]["total_worn_item_events"] == 2
    assert overview["all_time"]["unique_items_worn"] == 2
