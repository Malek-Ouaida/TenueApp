from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_wear_logs import build_raw_fields, create_confirmed_item, create_wear_log

from app.core.storage import InMemoryStorageClient
from app.domains.closet.repository import ClosetRepository
from app.domains.wear.detection import DetectedOutfitItem
from app.domains.wear.matching_service import WearDetectionMatchResult, WearMatchCandidateResult
from app.domains.wear.models import WearLog, WearLogStatus
from app.domains.wear.processing_service import (
    NormalizedWearDetection,
    _should_surface_detection_match,
)
from app.domains.wear.repository import WearRepository
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


def test_low_scoring_accessory_candidate_is_not_surfaced() -> None:
    should_surface = _should_surface_detection_match(
        detection=NormalizedWearDetection(
            role="bag",
            normalized_metadata={"category": "bags"},
            field_confidences={},
            field_notes={},
            confidence=0.9,
            bbox=None,
            sort_index=0,
        ),
        match_result=WearDetectionMatchResult(
            detection_key="sort:0",
            normalized_metadata={"category": "bags"},
            field_confidences={},
            candidates=[
                WearMatchCandidateResult(
                    closet_item_id=UUID("00000000-0000-0000-0000-000000000111"),
                    rank=1,
                    score=53.0,
                    normalized_confidence=0.53,
                    match_state="candidate",
                    is_exact_match=False,
                    explanation_json={},
                )
            ],
            exact_match=False,
            match_resolution={"state": "candidate_only", "reason": "review_required"},
            structured_explanation={},
        ),
    )

    assert should_surface is False


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
    assert detail["detected_items"][0]["normalized_metadata"]["category"] == "tops"
    assert detail["detected_items"][0]["normalized_metadata"]["subcategory"] == "t_shirt"
    assert detail["detected_items"][0]["normalized_metadata"]["primary_color"] == "navy"
    assert detail["detected_items"][0]["field_confidences"]["primary_color"] is None
    assert detail["detected_items"][0]["exact_match"] is True
    assert detail["detected_items"][0]["match_resolution"]["state"] == "exact_match"
    assert detail["detected_items"][0]["candidate_matches"][0]["closet_item_id"] == str(top_item_id)
    assert detail["detected_items"][0]["candidate_matches"][0]["match_state"] == "exact_match"
    assert detail["detected_items"][0]["candidate_matches"][0]["is_exact_match"] is True
    assert detail["detected_items"][0]["candidate_matches"][0]["normalized_confidence"] == 1.0
    assert detail["detected_items"][0]["candidate_matches"][0]["explanation"] is not None
    assert detail["detected_items"][1]["candidate_matches"][0]["closet_item_id"] == str(bottom_item_id)

    calendar_response = client.get(
        "/wear-logs/calendar?start_date=2026-04-10&end_date=2026-04-10",
        headers=headers,
    )
    assert calendar_response.status_code == 200
    assert calendar_response.json()["days"][0]["event_count"] == 0


def test_reprocess_clears_stale_detected_items_until_new_results_arrive(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    fake_wear_detection_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-photo-reprocess@example.com")
    create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Reprocess tee",
        key_prefix="wear-photo-reprocess-top",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    wear_log = create_photo_wear_log(client, headers)
    finalize_photo_upload(
        client,
        fake_storage_client,
        headers,
        wear_log_id=wear_log["id"],
        image_bytes=build_test_image_bytes(),
    )

    fake_wear_detection_provider.succeed(
        detections=[
            DetectedOutfitItem(
                role="top",
                category="top",
                subcategory="tee shirt",
                colors=["navy"],
                confidence=0.96,
                bbox={"left": 0.12, "top": 0.08, "width": 0.72, "height": 0.34},
            )
        ]
    )
    run_wear_worker_once(db_session, fake_storage_client, fake_wear_detection_provider)

    before_reprocess = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert before_reprocess.status_code == 200
    assert len(before_reprocess.json()["detected_items"]) == 1

    reprocess_response = client.post(f"/wear-logs/{wear_log['id']}/reprocess", headers=headers)
    assert reprocess_response.status_code == 202
    reprocess_body = reprocess_response.json()
    assert reprocess_body["status"] == "processing"
    assert reprocess_body["detected_items"] == []

    fake_wear_detection_provider.fail()
    run_wear_worker_once(db_session, fake_storage_client, fake_wear_detection_provider)

    failed_detail = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert failed_detail.status_code == 200
    assert failed_detail.json()["status"] == "failed"
    assert failed_detail.json()["detected_items"] == []


def test_wear_detail_filters_out_candidates_that_are_no_longer_valid(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    fake_wear_detection_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-photo-candidate-filter@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Archivable tee",
        key_prefix="wear-photo-archive-filter",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    wear_log = create_photo_wear_log(client, headers)
    finalize_photo_upload(
        client,
        fake_storage_client,
        headers,
        wear_log_id=wear_log["id"],
        image_bytes=build_test_image_bytes(),
    )

    fake_wear_detection_provider.succeed(
        detections=[
            DetectedOutfitItem(
                role="top",
                category="top",
                subcategory="tee shirt",
                colors=["navy"],
                confidence=0.97,
                bbox={"left": 0.15, "top": 0.05, "width": 0.7, "height": 0.35},
            )
        ]
    )
    run_wear_worker_once(db_session, fake_storage_client, fake_wear_detection_provider)

    closet_repository = ClosetRepository(db_session)
    closet_item = closet_repository.get_item(item_id=top_item_id)
    assert closet_item is not None
    closet_item.archived_at = closet_item.updated_at
    db_session.commit()

    detail_response = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert detail_response.status_code == 200
    detected_item = detail_response.json()["detected_items"][0]
    assert detected_item["candidate_matches"] == []
    assert detected_item["exact_match"] is False
    assert detected_item["match_resolution"]["state"] == "no_match"


def test_processing_hides_detected_items_without_real_closet_matches(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    fake_wear_detection_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-photo-hide-unmatched@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="White tank",
        key_prefix="wear-photo-hide-unmatched-top",
        raw_fields=build_raw_fields(category="top", subcategory="tank top", color="white"),
    )
    wear_log = create_photo_wear_log(client, headers)
    finalize_photo_upload(
        client,
        fake_storage_client,
        headers,
        wear_log_id=wear_log["id"],
        image_bytes=build_test_image_bytes(color="white"),
    )

    fake_wear_detection_provider.succeed(
        detections=[
            DetectedOutfitItem(
                role="top",
                category="top",
                subcategory="tank top",
                colors=["white"],
                confidence=0.97,
                bbox={"left": 0.18, "top": 0.08, "width": 0.48, "height": 0.3},
            ),
            DetectedOutfitItem(
                role="bag",
                category="bag",
                subcategory="shoulder bag",
                colors=["brown"],
                confidence=0.91,
                bbox={"left": 0.64, "top": 0.18, "width": 0.16, "height": 0.28},
            ),
        ]
    )
    run_wear_worker_once(db_session, fake_storage_client, fake_wear_detection_provider)

    detail_response = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "needs_review"
    assert len(detail["detected_items"]) == 1
    assert detail["detected_items"][0]["candidate_matches"][0]["closet_item_id"] == str(top_item_id)
    assert detail["detected_items"][0]["normalized_metadata"]["category"] == "tops"


def test_processing_fails_cleanly_when_no_detected_items_match_closet(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    fake_wear_detection_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-photo-no-closet-matches@example.com")
    wear_log = create_photo_wear_log(client, headers)
    finalize_photo_upload(
        client,
        fake_storage_client,
        headers,
        wear_log_id=wear_log["id"],
        image_bytes=build_test_image_bytes(color="white"),
    )

    fake_wear_detection_provider.succeed(
        detections=[
            DetectedOutfitItem(
                role="bag",
                category="bag",
                subcategory="shoulder bag",
                colors=["brown"],
                confidence=0.9,
                bbox={"left": 0.62, "top": 0.14, "width": 0.18, "height": 0.3},
            )
        ]
    )
    run_wear_worker_once(db_session, fake_storage_client, fake_wear_detection_provider)

    detail_response = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "failed"
    assert detail["detected_items"] == []
    assert detail["failure_summary"] == "We could not match this photo to items in your closet."


def test_pre_migration_detected_rows_remain_readable_in_detail_payload(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="wear-photo-legacy-detected@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Legacy tee",
        key_prefix="wear-photo-legacy-top",
        raw_fields=build_raw_fields(category="top", subcategory="tee shirt", color="navy"),
    )
    wear_log = create_photo_wear_log(client, headers)

    wear_log_row = db_session.execute(
        select(WearLog).where(WearLog.id == UUID(wear_log["id"]))
    ).scalar_one()
    wear_log_row.status = WearLogStatus.NEEDS_REVIEW

    repository = WearRepository(db_session)
    detected_item = repository.create_detected_item(
        wear_log_id=wear_log_row.id,
        processing_run_id=None,
        sort_index=0,
        predicted_role=None,
        predicted_category="tops",
        predicted_subcategory="t_shirt",
        predicted_colors_json=["navy"],
        predicted_material=None,
        predicted_pattern=None,
        predicted_fit_tags_json=None,
        predicted_silhouette=None,
        predicted_attributes_json=None,
        normalized_metadata_json=None,
        field_confidences_json=None,
        matching_explanation_json=None,
        confidence=0.94,
        bbox_json=None,
        crop_asset_id=None,
    )
    repository.create_match_candidate(
        detected_item_id=detected_item.id,
        closet_item_id=top_item_id,
        rank=1,
        score=96.0,
        signals_json={"is_exact_match": True, "match_state": "exact_match"},
    )
    db_session.commit()

    detail_response = client.get(f"/wear-logs/{wear_log['id']}", headers=headers)
    assert detail_response.status_code == 200
    detected_body = detail_response.json()["detected_items"][0]
    assert detected_body["normalized_metadata"]["category"] == "tops"
    assert detected_body["normalized_metadata"]["subcategory"] == "t_shirt"
    assert detected_body["normalized_metadata"]["primary_color"] == "navy"
    assert "primary_color" in detected_body["field_confidences"]
    assert detected_body["field_confidences"]["primary_color"] is None
    assert detected_body["exact_match"] is True
    assert detected_body["match_resolution"]["state"] == "exact_match"
    assert detected_body["match_resolution"]["closet_item_id"] == str(top_item_id)
    assert detected_body["structured_explanation"]["returned_candidate_ids"] == [str(top_item_id)]
