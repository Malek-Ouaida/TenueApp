from __future__ import annotations

from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import InMemoryStorageClient
from app.domains.closet.models import (
    ClosetItemAuditEvent,
    ClosetItemFieldCandidate,
    ClosetItemFieldState,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetItemMetadataProjection,
    ClosetJob,
    ClosetJobStatus,
    MediaAsset,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResult,
    ProviderResultStatus,
)
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
    assert body["current_candidate_set"] is None
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
        db_session.execute(
            select(ClosetJob).where(ClosetJob.closet_item_id == item_id)
        ).scalars()
    )
    assert len(jobs) == 1
    assert jobs[0].job_kind == ProcessingRunType.IMAGE_PROCESSING


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
    assert body["source_image"]["role"] == "processed"
    assert body["current_candidate_set"]["field_candidates"][0]["field_name"] == "category"


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

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "completed_with_issues"
    assert body["provider_results"][0]["status"] == "partial"
    candidate_fields = [
        candidate["field_name"]
        for candidate in body["current_candidate_set"]["field_candidates"]
    ]
    assert candidate_fields == ["category"]


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

    response = client.get(f"/closet/items/{item_id}/extraction", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["extraction_status"] == "failed"
    assert body["current_candidate_set"] is not None
    candidate_fields = [
        candidate["field_name"]
        for candidate in body["current_candidate_set"]["field_candidates"]
    ]
    assert candidate_fields == ["category", "subcategory"]
