from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_wear_logs import build_raw_fields, create_confirmed_item, create_wear_log

from app.core.storage import InMemoryStorageClient
from app.domains.wear.detection import DetectedOutfitItem
from app.domains.wear.worker import WearWorker
from app.domains.wear.worker_runner import build_worker_handlers


def build_test_image_bytes(*, color: str = "navy") -> bytes:
    image = Image.new("RGB", (640, 960), color=color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def upload_to_fake_storage(
    fake_storage_client: InMemoryStorageClient,
    *,
    upload_response: dict[str, Any],
    content: bytes,
) -> None:
    fake_storage_client.put_via_presigned_upload(
        url=upload_response["upload"]["url"],
        headers=upload_response["upload"]["headers"],
        content=content,
    )


def create_photo_wear_log(
    client: TestClient,
    headers: dict[str, str],
    *,
    wear_date: str = "2026-04-10",
    worn_at: str = "2026-04-10T20:00:00Z",
) -> dict[str, Any]:
    response = create_wear_log(
        client,
        headers,
        wear_date=wear_date,
        worn_at=worn_at,
        mode="photo_upload",
        context="event",
        notes="Photo upload event",
    )
    assert response.status_code == 201
    return response.json()


def finalize_photo_upload(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
    headers: dict[str, str],
    *,
    wear_log_id: str,
    image_bytes: bytes,
) -> dict[str, Any]:
    sha256 = hashlib.sha256(image_bytes).hexdigest()
    upload_intent_response = client.post(
        f"/wear-logs/{wear_log_id}/photos/upload-intents",
        headers=headers,
        json={
            "filename": "ootd.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(image_bytes),
            "sha256": sha256,
        },
    )
    assert upload_intent_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_intent_response.json(),
        content=image_bytes,
    )
    complete_response = client.post(
        f"/wear-logs/{wear_log_id}/photos/uploads/complete",
        headers=headers,
        json={"upload_intent_id": upload_intent_response.json()["upload_intent_id"]},
    )
    assert complete_response.status_code == 200
    return complete_response.json()


def run_wear_worker_once(
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_wear_detection_provider: Any,
):
    worker = WearWorker(
        session=db_session,
        handlers=build_worker_handlers(
            storage=fake_storage_client,
            detection_provider=fake_wear_detection_provider,
        ),
    )
    return worker.run_once(worker_name="test-wear-worker")


def test_photo_upload_finalize_and_worker_populate_review_state(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    fake_wear_detection_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-photo-processing@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Navy tee",
        key_prefix="wear-photo-top",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Black trousers",
        key_prefix="wear-photo-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )
    wear_log = create_photo_wear_log(client, headers)
    complete_body = finalize_photo_upload(
        client,
        fake_storage_client,
        headers,
        wear_log_id=wear_log["id"],
        image_bytes=build_test_image_bytes(),
    )

    assert complete_body["status"] == "processing"
    assert complete_body["is_confirmed"] is False
    assert complete_body["primary_photo"] is not None
    assert len(complete_body["photos"]) == 1

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
                bbox={"left": 0.15, "top": 0.05, "width": 0.7, "height": 0.35},
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
                confidence=0.95,
                bbox={"left": 0.2, "top": 0.45, "width": 0.6, "height": 0.4},
            ),
        ]
    )
    run_wear_worker_once(
        db_session,
        fake_storage_client,
        fake_wear_detection_provider,
    )

    detail_response = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "needs_review"
    assert detail["can_confirm"] is True
    assert detail["is_confirmed"] is False
    assert detail["review_version"]
    assert len(detail["detected_items"]) == 2
    assert detail["detected_items"][0]["crop_image"] is not None
    assert detail["detected_items"][0]["candidate_matches"][0]["closet_item_id"] == str(top_item_id)
    assert detail["detected_items"][1]["candidate_matches"][0]["closet_item_id"] == str(bottom_item_id)

    calendar_response = client.get(
        "/wear-logs/calendar?start_date=2026-04-10&end_date=2026-04-10",
        headers=headers,
    )
    assert calendar_response.status_code == 200
    assert calendar_response.json()["days"][0]["event_count"] == 0
