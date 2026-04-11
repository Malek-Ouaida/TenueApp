from __future__ import annotations

from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import InMemoryStorageClient
from app.domains.closet.metadata_extraction import METADATA_EXTRACTION_TASK_TYPE
from app.domains.closet.models import (
    ApplicabilityState,
    ClosetItemAuditEvent,
    ClosetItemFieldCandidate,
    ClosetItemFieldState,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    ClosetJob,
    ClosetJobStatus,
    FieldReviewState,
    FieldSource,
    MediaAsset,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResult,
    ProviderResultStatus,
)
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.taxonomy import TAXONOMY_VERSION
from app.domains.closet.worker import ClosetWorker
from app.domains.closet.worker_runner import build_worker_handlers


def register_and_get_headers(
    client: TestClient,
    *,
    email: str = "closet-metadata@example.com",
) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    access_token = response.json()["session"]["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def create_draft(
    client: TestClient,
    headers: dict[str, str],
    *,
    idempotency_key: str,
):
    return client.post(
        "/closet/drafts",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"title": "Black tee"},
    )


def create_upload_intent(
    client: TestClient,
    headers: dict[str, str],
    *,
    draft_id: str,
    filename: str,
    mime_type: str,
    file_size: int,
    sha256: str,
):
    return client.post(
        f"/closet/drafts/{draft_id}/upload-intents",
        headers=headers,
        json={
            "filename": filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "sha256": sha256,
        },
    )


def complete_upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    draft_id: str,
    upload_intent_id: str,
    idempotency_key: str,
):
    return client.post(
        f"/closet/drafts/{draft_id}/uploads/complete",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"upload_intent_id": upload_intent_id},
    )


def upload_to_fake_storage(
    fake_storage_client: InMemoryStorageClient,
    *,
    upload_response: dict[str, object],
    content: bytes,
) -> None:
    upload = upload_response["upload"]
    assert isinstance(upload, dict)
    fake_storage_client.put_via_presigned_upload(
        url=str(upload["url"]),
        headers=dict(upload["headers"]),
        content=content,
    )


def build_image_bytes(
    *,
    size: tuple[int, int] = (64, 64),
    color: tuple[int, ...] = (24, 24, 24),
    image_format: str = "JPEG",
    mode: str = "RGB",
) -> bytes:
    image = Image.new(mode, size, color=color)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def sha256_hex(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def create_uploaded_item(
    client: TestClient,
    headers: dict[str, str],
    fake_storage_client: InMemoryStorageClient,
    *,
    draft_key: str,
    complete_key: str,
) -> UUID:
    image_bytes = build_image_bytes()
    draft = create_draft(client, headers, idempotency_key=draft_key).json()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        filename="tee.jpg",
        mime_type="image/jpeg",
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert upload_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=image_bytes,
    )
    complete_response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
        idempotency_key=complete_key,
    )
    assert complete_response.status_code == 200
    return UUID(draft["id"])


def run_worker_once(
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
):
    worker = ClosetWorker(
        session=db_session,
        handlers=build_worker_handlers(
            storage=fake_storage_client,
            background_removal_provider=fake_background_removal_provider,
            metadata_extraction_provider=fake_metadata_extraction_provider,
        ),
    )
    return worker.run_once(worker_name="test-closet-worker")


def latest_provider_result_for_item(db_session: Session, *, item_id: UUID) -> ProviderResult | None:
    return (
        db_session.execute(
            select(ProviderResult)
            .where(
                ProviderResult.closet_item_id == item_id,
                ProviderResult.task_type == METADATA_EXTRACTION_TASK_TYPE,
            )
            .order_by(ProviderResult.created_at.desc(), ProviderResult.id.desc())
        )
        .scalars()
        .first()
    )


def field_state_map(db_session: Session, *, item_id: UUID) -> dict[str, ClosetItemFieldState]:
    return {
        field_state.field_name: field_state
        for field_state in db_session.execute(
            select(ClosetItemFieldState).where(ClosetItemFieldState.closet_item_id == item_id)
        ).scalars()
    }


def test_extraction_snapshot_returns_not_requested_before_enqueue(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="not-requested@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-not-requested",
        complete_key="complete-not-requested",
    )

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "not_requested"
    assert body["normalization_status"] == "not_requested"
    assert body["field_states_stale"] is False
    assert body["current_candidate_set"] is None
    assert body["current_field_states"] == []
    assert body["metadata_projection"]["category"] is None
    assert body["source_image"]["role"] == "original"


def test_extraction_snapshot_is_user_scoped(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    owner_headers = register_and_get_headers(client, email="owner-extract@example.com")
    item_id = create_uploaded_item(
        client,
        owner_headers,
        fake_storage_client,
        draft_key="draft-owner-extract",
        complete_key="complete-owner-extract",
    )
    intruder_headers = register_and_get_headers(client, email="intruder-extract@example.com")

    response = client.get(f"/closet/items/{item_id}/extraction", headers=intruder_headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "closet_item_not_found"


def test_image_processing_completion_auto_enqueues_metadata_extraction(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(72, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    headers = register_and_get_headers(client, email="auto-enqueue-success@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-auto-enqueue-success",
        complete_key="complete-auto-enqueue-success",
    )

    job = run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    assert job is not None
    jobs = list(
        db_session.execute(
            select(ClosetJob)
            .where(ClosetJob.closet_item_id == item_id)
            .order_by(ClosetJob.created_at.asc(), ClosetJob.id.asc())
        ).scalars()
    )
    audit_events = list(
        db_session.execute(
            select(ClosetItemAuditEvent).where(ClosetItemAuditEvent.closet_item_id == item_id)
        ).scalars()
    )

    assert len(jobs) == 2
    assert jobs[0].job_kind == ProcessingRunType.IMAGE_PROCESSING
    assert jobs[0].status == ClosetJobStatus.COMPLETED
    assert jobs[1].job_kind == ProcessingRunType.METADATA_EXTRACTION
    assert jobs[1].status == ClosetJobStatus.PENDING
    enqueue_event = next(
        event for event in audit_events if event.event_type == "metadata_extraction_enqueued"
    )
    assert isinstance(enqueue_event.payload, dict)
    assert enqueue_event.payload["source_role"] == "processed"


def test_fallback_image_processing_auto_enqueues_extraction_from_original(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.fail()
    headers = register_and_get_headers(client, email="auto-enqueue-fallback@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-auto-enqueue-fallback",
        complete_key="complete-auto-enqueue-fallback",
    )

    job = run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    assert job is not None
    audit_events = list(
        db_session.execute(
            select(ClosetItemAuditEvent).where(ClosetItemAuditEvent.closet_item_id == item_id)
        ).scalars()
    )
    enqueue_event = next(
        event for event in audit_events if event.event_type == "metadata_extraction_enqueued"
    )
    assert isinstance(enqueue_event.payload, dict)
    assert enqueue_event.payload["source_role"] == "original"


def test_failed_image_processing_does_not_enqueue_metadata_extraction(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="no-enqueue-on-failure@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-no-enqueue",
        complete_key="complete-no-enqueue",
    )
    original_asset = (
        db_session.execute(
            select(MediaAsset)
            .join(ClosetItemImage, ClosetItemImage.asset_id == MediaAsset.id)
            .where(
                ClosetItemImage.closet_item_id == item_id,
                ClosetItemImage.role == ClosetItemImageRole.ORIGINAL,
                ClosetItemImage.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )
    assert original_asset is not None
    fake_storage_client.delete_object(bucket=original_asset.bucket, key=original_asset.key)

    job = run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    assert job is not None
    jobs = list(
        db_session.execute(select(ClosetJob).where(ClosetJob.closet_item_id == item_id)).scalars()
    )
    assert len(jobs) == 1
    assert jobs[0].job_kind == ProcessingRunType.IMAGE_PROCESSING


def test_metadata_extraction_completion_auto_enqueues_normalization(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {"value": "top", "confidence": 0.99, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        }
    )
    headers = register_and_get_headers(client, email="auto-enqueue-normalization@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-auto-enqueue-normalization",
        complete_key="complete-auto-enqueue-normalization",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    jobs = list(
        db_session.execute(
            select(ClosetJob)
            .where(ClosetJob.closet_item_id == item_id)
            .order_by(ClosetJob.created_at.asc(), ClosetJob.id.asc())
        ).scalars()
    )
    audit_events = list(
        db_session.execute(
            select(ClosetItemAuditEvent).where(ClosetItemAuditEvent.closet_item_id == item_id)
        ).scalars()
    )

    assert [job.job_kind for job in jobs] == [
        ProcessingRunType.IMAGE_PROCESSING,
        ProcessingRunType.METADATA_EXTRACTION,
        ProcessingRunType.NORMALIZATION_PROJECTION,
    ]
    assert jobs[2].status == ClosetJobStatus.PENDING
    assert isinstance(jobs[2].payload, dict)
    assert jobs[2].payload["source_provider_result_id"]
    enqueue_event = next(
        event for event in audit_events if event.event_type == "metadata_normalization_enqueued"
    )
    assert isinstance(enqueue_event.payload, dict)
    assert (
        enqueue_event.payload["source_provider_result_id"]
        == jobs[2].payload["source_provider_result_id"]
    )

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["normalization_status"] == "pending"
    assert body["field_states_stale"] is True


def test_metadata_extraction_worker_persists_candidates_and_keeps_trust_layer_untouched(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {
                "value": "tops",
                "confidence": 0.99,
                "applicability_state": "value",
            },
            "subcategory": {
                "value": "t-shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "colors": {
                "values": ["black", "black", "white"],
                "confidence": 0.9,
                "applicability_state": "value",
            },
        }
    )
    headers = register_and_get_headers(client, email="extract-success@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-extract-success",
        complete_key="complete-extract-success",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    db_session.expire_all()
    metadata_run = (
        db_session.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.closet_item_id == item_id,
                ProcessingRun.run_type == ProcessingRunType.METADATA_EXTRACTION,
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        )
        .scalars()
        .first()
    )
    assert metadata_run is not None
    provider_result = (
        db_session.execute(
            select(ProviderResult).where(ProviderResult.processing_run_id == metadata_run.id)
        )
        .scalars()
        .one()
    )
    field_candidates = list(
        db_session.execute(
            select(ClosetItemFieldCandidate)
            .where(ClosetItemFieldCandidate.provider_result_id == provider_result.id)
            .order_by(ClosetItemFieldCandidate.created_at.asc(), ClosetItemFieldCandidate.id.asc())
        ).scalars()
    )
    field_states = list(db_session.execute(select(ClosetItemFieldState)).scalars())
    projection = db_session.execute(
        select(ClosetItemMetadataProjection).where(
            ClosetItemMetadataProjection.closet_item_id == item_id
        )
    ).scalar_one()

    assert metadata_run is not None
    assert metadata_run.status == ProcessingStatus.COMPLETED
    assert provider_result.status == ProviderResultStatus.SUCCEEDED
    assert [candidate.field_name for candidate in field_candidates] == [
        "category",
        "subcategory",
        "colors",
    ]
    assert field_candidates[2].raw_value == ["black", "white"]
    assert field_states == []
    assert projection.category is None
    assert projection.subcategory is None
    assert fake_metadata_extraction_provider.calls[0]["mime_type"] == "image/png"

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "completed"
    assert body["normalization_status"] == "pending"
    assert body["field_states_stale"] is True
    assert body["source_image"]["role"] == "processed"
    assert body["current_candidate_set"]["field_candidates"][0]["field_name"] == "category"
    assert body["current_field_states"] == []
    assert body["metadata_projection"]["category"] is None


def test_partial_extraction_marks_completed_with_issues_and_keeps_valid_candidates(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {
                "value": "tops",
                "confidence": 0.99,
                "applicability_state": "value",
            },
            "subcategory": {
                "value": "   ",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "notes_only": {"value": "ignored"},
        }
    )
    headers = register_and_get_headers(client, email="extract-partial@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-extract-partial",
        complete_key="complete-extract-partial",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "completed_with_issues"
    assert body["provider_results"][0]["status"] == "partial"
    candidate_fields = [
        candidate["field_name"] for candidate in body["current_candidate_set"]["field_candidates"]
    ]
    assert candidate_fields == ["category"]


def test_normalization_materializes_field_states_and_keeps_projection_confirmed_only(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {"value": "top", "confidence": 0.99, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "colors": {
                "values": ["grey", "navy blue", "taupe"],
                "confidence": 0.91,
                "applicability_state": "value",
            },
            "style_tags": {
                "values": ["athleisure", "smart casual"],
                "confidence": 0.62,
                "applicability_state": "value",
            },
            "occasion_tags": {
                "values": ["office", "vacation"],
                "confidence": 0.74,
                "applicability_state": "value",
            },
            "brand": {
                "value": "  COS  ",
                "confidence": 0.55,
                "applicability_state": "value",
            },
        }
    )
    headers = register_and_get_headers(client, email="normalization-success@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-normalization-success",
        complete_key="complete-normalization-success",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    db_session.expire_all()
    state_by_field = field_state_map(db_session, item_id=item_id)
    projection = db_session.execute(
        select(ClosetItemMetadataProjection).where(
            ClosetItemMetadataProjection.closet_item_id == item_id
        )
    ).scalar_one()
    latest_candidate_result = latest_provider_result_for_item(db_session, item_id=item_id)
    assert latest_candidate_result is not None
    field_candidates = list(
        db_session.execute(
            select(ClosetItemFieldCandidate)
            .where(ClosetItemFieldCandidate.provider_result_id == latest_candidate_result.id)
            .order_by(ClosetItemFieldCandidate.created_at.asc(), ClosetItemFieldCandidate.id.asc())
        ).scalars()
    )
    normalization_run = (
        db_session.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.closet_item_id == item_id,
                ProcessingRun.run_type == ProcessingRunType.NORMALIZATION_PROJECTION,
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        )
        .scalars()
        .first()
    )

    assert normalization_run is not None
    assert normalization_run.status == ProcessingStatus.COMPLETED_WITH_ISSUES
    assert [candidate.field_name for candidate in field_candidates] == [
        "category",
        "subcategory",
        "colors",
        "style_tags",
        "occasion_tags",
        "brand",
    ]
    assert field_candidates[0].normalized_candidate == "tops"
    assert field_candidates[1].normalized_candidate == "t-shirt"
    assert field_candidates[2].normalized_candidate == ["gray", "navy"]
    assert "taupe" in (field_candidates[2].conflict_notes or "")
    assert field_candidates[3].normalized_candidate == ["sporty"]
    assert "smart casual" in (field_candidates[3].conflict_notes or "")
    assert field_candidates[4].normalized_candidate == ["business", "vacation"]
    assert field_candidates[4].conflict_notes in {None, ""}
    assert field_candidates[5].normalized_candidate == "COS"

    assert set(state_by_field) == {
        "title",
        "category",
        "subcategory",
        "colors",
        "material",
        "pattern",
        "brand",
        "style_tags",
        "fit_tags",
        "occasion_tags",
        "season_tags",
        "silhouette",
        "attributes",
    }
    assert state_by_field["category"].source == FieldSource.PROVIDER
    assert state_by_field["category"].review_state == FieldReviewState.PENDING_USER
    assert state_by_field["category"].canonical_value == "tops"
    assert state_by_field["subcategory"].canonical_value == "t-shirt"
    assert state_by_field["colors"].canonical_value == ["gray", "navy"]
    assert state_by_field["material"].source == FieldSource.SYSTEM
    assert state_by_field["material"].review_state == FieldReviewState.SYSTEM_UNSET
    assert state_by_field["material"].applicability_state == ApplicabilityState.UNKNOWN
    assert state_by_field["brand"].canonical_value == "COS"

    assert projection.category is None
    assert projection.subcategory is None
    assert projection.primary_color is None
    assert projection.brand is None

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["normalization_status"] == "completed_with_issues"
    assert body["field_states_stale"] is False
    assert body["latest_normalization_run"]["status"] == "completed_with_issues"
    assert [field_state["field_name"] for field_state in body["current_field_states"]] == [
        "title",
        "category",
        "subcategory",
        "colors",
        "material",
        "pattern",
        "brand",
        "style_tags",
        "fit_tags",
        "occasion_tags",
        "season_tags",
        "silhouette",
        "attributes",
    ]
    assert body["current_field_states"][1]["canonical_value"] == "tops"
    assert body["current_field_states"][2]["canonical_value"] == "t-shirt"
    assert body["current_field_states"][3]["canonical_value"] == ["gray", "navy"]
    assert body["review_status"] == "needs_review"
    assert body["metadata_projection"]["category"] is None


def test_normalization_derives_category_and_preserves_unknown_states(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.88,
                "applicability_state": "value",
            },
            "material": {
                "value": None,
                "confidence": 0.4,
                "applicability_state": "not_applicable",
            },
            "pattern": {
                "value": None,
                "confidence": 0.3,
                "applicability_state": "unknown",
            },
        }
    )
    headers = register_and_get_headers(client, email="normalization-derived@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-normalization-derived",
        complete_key="complete-normalization-derived",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    state_by_field = field_state_map(db_session, item_id=item_id)

    assert state_by_field["category"].source == FieldSource.PROVIDER
    assert state_by_field["category"].canonical_value == "tops"
    assert state_by_field["category"].confidence == 0.88
    assert state_by_field["subcategory"].canonical_value == "t-shirt"
    assert state_by_field["material"].source == FieldSource.PROVIDER
    assert state_by_field["material"].applicability_state == ApplicabilityState.NOT_APPLICABLE
    assert state_by_field["material"].canonical_value is None
    assert state_by_field["pattern"].source == FieldSource.PROVIDER
    assert state_by_field["pattern"].applicability_state == ApplicabilityState.UNKNOWN
    assert state_by_field["pattern"].canonical_value is None

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["normalization_status"] == "completed_with_issues"
    assert body["field_states_stale"] is False
    assert body["current_field_states"][1]["canonical_value"] == "tops"
    assert body["current_field_states"][4]["applicability_state"] == "not_applicable"
    assert body["current_field_states"][5]["applicability_state"] == "unknown"


def test_normalization_preserves_existing_user_field_states(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {"value": "shoe", "confidence": 0.9, "applicability_state": "value"},
            "subcategory": {
                "value": "boots",
                "confidence": 0.88,
                "applicability_state": "value",
            },
            "brand": {"value": "Other Brand", "confidence": 0.2, "applicability_state": "value"},
        }
    )
    headers = register_and_get_headers(client, email="normalization-preserve-user@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-normalization-preserve-user",
        complete_key="complete-normalization-preserve-user",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    repository = ClosetRepository(db_session)
    repository.upsert_field_state(
        closet_item_id=item_id,
        field_name="brand",
        canonical_value="User Brand",
        source=FieldSource.USER,
        confidence=1.0,
        review_state=FieldReviewState.USER_EDITED,
        applicability_state=ApplicabilityState.VALUE,
        taxonomy_version=TAXONOMY_VERSION,
    )
    db_session.commit()

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    state_by_field = field_state_map(db_session, item_id=item_id)
    assert state_by_field["brand"].source == FieldSource.USER
    assert state_by_field["brand"].review_state == FieldReviewState.USER_EDITED
    assert state_by_field["brand"].canonical_value == "User Brand"
    assert state_by_field["category"].canonical_value == "shoes"
    assert state_by_field["subcategory"].canonical_value == "boots"


def test_failed_normalization_preserves_previous_field_states_and_marks_snapshot_stale(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {"value": "top", "confidence": 0.99, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        }
    )
    headers = register_and_get_headers(client, email="normalization-failure-stale@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-normalization-failure-stale",
        complete_key="complete-normalization-failure-stale",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    original_field_states = field_state_map(db_session, item_id=item_id)
    assert original_field_states["category"].canonical_value == "tops"

    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {"value": "bottom", "confidence": 0.66, "applicability_state": "value"},
            "subcategory": {
                "value": "shorts",
                "confidence": 0.65,
                "applicability_state": "value",
            },
        }
    )
    reextract = client.post(
        f"/closet/items/{item_id}/reextract",
        headers={**headers, "Idempotency-Key": "normalization-failure-stale-reextract"},
    )
    assert reextract.status_code == 202

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    newest_provider_result = latest_provider_result_for_item(db_session, item_id=item_id)
    assert newest_provider_result is not None
    candidates = list(
        db_session.execute(
            select(ClosetItemFieldCandidate).where(
                ClosetItemFieldCandidate.provider_result_id == newest_provider_result.id
            )
        ).scalars()
    )
    for candidate in candidates:
        db_session.delete(candidate)
    db_session.commit()

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    latest_normalization_run = (
        db_session.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.closet_item_id == item_id,
                ProcessingRun.run_type == ProcessingRunType.NORMALIZATION_PROJECTION,
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        )
        .scalars()
        .first()
    )
    assert latest_normalization_run is not None
    assert latest_normalization_run.status == ProcessingStatus.FAILED
    preserved_field_states = field_state_map(db_session, item_id=item_id)
    assert preserved_field_states["category"].canonical_value == "tops"
    assert preserved_field_states["subcategory"].canonical_value == "t-shirt"

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["normalization_status"] == "failed"
    assert body["field_states_stale"] is True
    assert body["current_field_states"][1]["canonical_value"] == "tops"
    assert body["current_field_states"][2]["canonical_value"] == "t-shirt"


def test_reextract_is_idempotent_and_duplicate_schedule_is_rejected(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={"category": {"value": "tops", "applicability_state": "value"}}
    )
    headers = register_and_get_headers(client, email="reextract-idempotent@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-reextract-idempotent",
        complete_key="complete-reextract-idempotent",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    first = client.post(
        f"/closet/items/{item_id}/reextract",
        headers={**headers, "Idempotency-Key": "reextract-key-1"},
    )
    second = client.post(
        f"/closet/items/{item_id}/reextract",
        headers={**headers, "Idempotency-Key": "reextract-key-1"},
    )
    conflict = client.post(
        f"/closet/items/{item_id}/reextract",
        headers={**headers, "Idempotency-Key": "reextract-key-2"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["extraction_status"] == "pending"
    assert first.json()["can_reextract"] is False
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "metadata_extraction_already_scheduled"


def test_failed_reextract_preserves_previous_candidate_set(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(
        raw_fields={
            "category": {"value": "tops", "applicability_state": "value"},
            "subcategory": {"value": "t-shirt", "applicability_state": "value"},
        }
    )
    headers = register_and_get_headers(client, email="reextract-preserve@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-reextract-preserve",
        complete_key="complete-reextract-preserve",
    )

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    fake_metadata_extraction_provider.fail()
    reextract = client.post(
        f"/closet/items/{item_id}/reextract",
        headers={**headers, "Idempotency-Key": "reextract-preserve-key"},
    )
    assert reextract.status_code == 202

    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "failed"
    assert body["current_candidate_set"] is not None
    candidate_fields = [
        candidate["field_name"] for candidate in body["current_candidate_set"]["field_candidates"]
    ]
    assert candidate_fields == ["category", "subcategory"]
