from __future__ import annotations

from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import InMemoryStorageClient
from app.domains.closet.models import (
    ClosetItem,
    ClosetItemAuditEvent,
    ClosetItemImage,
    ClosetItemImageRole,
    ClosetJob,
    ClosetJobStatus,
    LifecycleStatus,
    MediaAsset,
    MediaAssetSourceKind,
    ProcessingRun,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResult,
    ProviderResultStatus,
)
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.worker import ClosetWorker
from app.domains.closet.worker_runner import build_worker_handlers


def register_and_get_headers(
    client: TestClient,
    *,
    email: str = "closet-processing@example.com",
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
    title: str | None = "Black tee",
):
    payload: dict[str, str] = {}
    if title is not None:
        payload["title"] = title
    return client.post(
        "/closet/drafts",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json=payload,
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
    color: tuple[int, ...] = (24, 24, 24, 255),
    image_format: str = "PNG",
    mode: str = "RGBA",
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
    image_bytes: bytes | None = None,
) -> UUID:
    content = image_bytes or build_image_bytes(
        image_format="JPEG",
        mode="RGB",
        color=(40, 40, 40),
    )
    draft = create_draft(client, headers, idempotency_key=draft_key).json()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        filename="tee.jpg",
        mime_type="image/jpeg",
        file_size=len(content),
        sha256=sha256_hex(content),
    )
    assert upload_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=content,
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
    fake_metadata_extraction_provider: Any | None = None,
):
    worker = ClosetWorker(
        session=db_session,
        handlers=build_worker_handlers(
            storage=fake_storage_client,
            background_removal_provider=fake_background_removal_provider,
            metadata_extraction_provider=fake_metadata_extraction_provider,
        ),
    )
    return worker.run_once(worker_name="test-image-worker")
def test_upload_complete_enqueues_image_processing(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-enqueue",
        complete_key="complete-enqueue",
    )

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    jobs = list(
        db_session.execute(select(ClosetJob).where(ClosetJob.closet_item_id == item_id)).scalars()
    )

    assert item.lifecycle_status == LifecycleStatus.PROCESSING
    assert item.processing_status == ProcessingStatus.PENDING
    assert len(jobs) == 1
    assert jobs[0].status == ClosetJobStatus.PENDING
    assert jobs[0].job_kind == ProcessingRunType.IMAGE_PROCESSING


def test_image_processing_worker_success_creates_processed_and_thumbnail_assets(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(size=(80, 96), color=(255, 255, 255, 0)),
    )
    headers = register_and_get_headers(client, email="success@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-success",
        complete_key="complete-success",
    )

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    repository = ClosetRepository(db_session)
    old_processed_bytes = build_image_bytes(size=(20, 20), color=(10, 10, 10, 255))
    old_processed_key = f"closet/processed/{item.user_id}/{item.id}/seed-processed"
    old_thumbnail_key = f"closet/thumbnails/{item.user_id}/{item.id}/seed-thumbnail"
    fake_storage_client.put_object_bytes(
        bucket=settings.minio_bucket,
        key=old_processed_key,
        content=old_processed_bytes,
        content_type="image/png",
    )
    fake_storage_client.put_object_bytes(
        bucket=settings.minio_bucket,
        key=old_thumbnail_key,
        content=old_processed_bytes,
        content_type="image/png",
    )
    old_processed_asset = repository.create_media_asset(
        user_id=item.user_id,
        bucket=settings.minio_bucket,
        key=old_processed_key,
        mime_type="image/png",
        file_size=len(old_processed_bytes),
        checksum=sha256_hex(old_processed_bytes),
        width=20,
        height=20,
        source_kind=MediaAssetSourceKind.PROCESSED,
        is_private=True,
    )
    old_thumbnail_asset = repository.create_media_asset(
        user_id=item.user_id,
        bucket=settings.minio_bucket,
        key=old_thumbnail_key,
        mime_type="image/png",
        file_size=len(old_processed_bytes),
        checksum=sha256_hex(old_processed_bytes),
        width=20,
        height=20,
        source_kind=MediaAssetSourceKind.DERIVED,
        is_private=True,
    )
    repository.attach_image_asset(
        closet_item_id=item.id,
        asset_id=old_processed_asset.id,
        role=ClosetItemImageRole.PROCESSED,
    )
    repository.attach_image_asset(
        closet_item_id=item.id,
        asset_id=old_thumbnail_asset.id,
        role=ClosetItemImageRole.THUMBNAIL,
    )
    db_session.commit()

    job = run_worker_once(db_session, fake_storage_client, fake_background_removal_provider)
    assert job is not None

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    item_images = list(
        db_session.execute(
            select(ClosetItemImage).where(ClosetItemImage.closet_item_id == item_id)
        ).scalars()
    )
    image_processing_run = (
        db_session.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.closet_item_id == item_id,
                ProcessingRun.run_type == ProcessingRunType.IMAGE_PROCESSING,
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        )
        .scalars()
        .first()
    )
    assert image_processing_run is not None
    provider_results = list(
        db_session.execute(
            select(ProviderResult).where(
                ProviderResult.processing_run_id == image_processing_run.id
            )
        ).scalars()
    )
    audit_events = list(
        db_session.execute(
            select(ClosetItemAuditEvent).where(ClosetItemAuditEvent.closet_item_id == item_id)
        ).scalars()
    )

    active_processed = [
        item_image
        for item_image in item_images
        if item_image.role == ClosetItemImageRole.PROCESSED and item_image.is_active
    ]
    active_thumbnails = [
        item_image
        for item_image in item_images
        if item_image.role == ClosetItemImageRole.THUMBNAIL and item_image.is_active
    ]

    assert item.lifecycle_status == LifecycleStatus.REVIEW
    assert item.processing_status == ProcessingStatus.COMPLETED
    assert item.failure_summary is None
    assert image_processing_run.status == ProcessingStatus.COMPLETED
    assert len(provider_results) == 1
    assert provider_results[0].status == ProviderResultStatus.SUCCEEDED
    assert len(active_processed) == 1
    assert len(active_thumbnails) == 1
    assert any(
        item_image.asset_id == old_processed_asset.id and not item_image.is_active
        for item_image in item_images
    )
    assert any(
        item_image.asset_id == old_thumbnail_asset.id and not item_image.is_active
        for item_image in item_images
    )
    assert "image_processing_started" in [event.event_type for event in audit_events]
    assert "image_processing_completed" in [event.event_type for event in audit_events]


def test_image_processing_worker_falls_back_when_provider_fails(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
) -> None:
    fake_background_removal_provider.fail(
        payload={"reason_code": "provider_failed", "message": "Fallback expected."}
    )
    headers = register_and_get_headers(client, email="fallback@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-fallback",
        complete_key="complete-fallback",
    )

    job = run_worker_once(db_session, fake_storage_client, fake_background_removal_provider)
    assert job is not None

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    item_images = list(
        db_session.execute(
            select(ClosetItemImage).where(ClosetItemImage.closet_item_id == item_id)
        ).scalars()
    )
    image_processing_run = (
        db_session.execute(
            select(ProcessingRun)
            .where(
                ProcessingRun.closet_item_id == item_id,
                ProcessingRun.run_type == ProcessingRunType.IMAGE_PROCESSING,
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        )
        .scalars()
        .first()
    )
    assert image_processing_run is not None
    provider_result = db_session.execute(
        select(ProviderResult).where(ProviderResult.processing_run_id == image_processing_run.id)
    ).scalar_one()

    assert item.lifecycle_status == LifecycleStatus.REVIEW
    assert item.processing_status == ProcessingStatus.COMPLETED_WITH_ISSUES
    assert item.failure_summary == (
        "Background removal was unavailable, so we kept a cleaned version of the original image."
    )
    assert image_processing_run.status == ProcessingStatus.COMPLETED_WITH_ISSUES
    assert provider_result.status == ProviderResultStatus.FAILED
    assert any(
        item_image.role == ClosetItemImageRole.PROCESSED and item_image.is_active
        for item_image in item_images
    )
    assert any(
        item_image.role == ClosetItemImageRole.THUMBNAIL and item_image.is_active
        for item_image in item_images
    )


def test_image_processing_worker_marks_item_failed_when_original_missing(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="hard-failure@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-hard-failure",
        complete_key="complete-hard-failure",
    )

    db_session.expire_all()
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

    job = run_worker_once(db_session, fake_storage_client, fake_background_removal_provider)
    assert job is not None

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    item_images = list(
        db_session.execute(
            select(ClosetItemImage).where(ClosetItemImage.closet_item_id == item_id)
        ).scalars()
    )

    assert item.lifecycle_status == LifecycleStatus.REVIEW
    assert item.processing_status == ProcessingStatus.FAILED
    assert item.failure_summary == (
        "We couldn't finish processing this image. Try reprocessing it or upload a new original."
    )
    assert any(
        item_image.role == ClosetItemImageRole.ORIGINAL and item_image.is_active
        for item_image in item_images
    )
    assert not any(
        item_image.role in {ClosetItemImageRole.PROCESSED, ClosetItemImageRole.THUMBNAIL}
        and item_image.is_active
        for item_image in item_images
    )

    status_response = client.get(f"/closet/items/{item_id}/processing", headers=headers)
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["display_image"]["role"] == "original"
    assert body["thumbnail_image"] is None
    assert body["failure_summary"] == item.failure_summary


def test_processing_status_endpoint_prefers_processed_and_is_user_scoped(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
) -> None:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(size=(70, 90), color=(200, 200, 200, 0)),
    )
    owner_headers = register_and_get_headers(client, email="owner-status@example.com")
    item_id = create_uploaded_item(
        client,
        owner_headers,
        fake_storage_client,
        draft_key="draft-status-owner",
        complete_key="complete-status-owner",
    )
    intruder_headers = register_and_get_headers(client, email="intruder-status@example.com")

    job = run_worker_once(db_session, fake_storage_client, fake_background_removal_provider)
    assert job is not None

    response = client.get(f"/closet/items/{item_id}/processing", headers=owner_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["display_image"]["role"] == "processed"
    assert body["original_image"]["role"] == "original"
    assert body["thumbnail_image"]["role"] == "thumbnail"
    assert body["display_image"]["url"].startswith("https://fake-storage.local/download/")
    assert body["thumbnail_image"]["expires_at"] is not None

    intruder = client.get(f"/closet/items/{item_id}/processing", headers=intruder_headers)
    assert intruder.status_code == 404
    assert intruder.json()["detail"]["code"] == "closet_item_not_found"


def test_processing_status_endpoint_falls_back_to_original_before_processing_runs(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="status-fallback@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-status-fallback",
        complete_key="complete-status-fallback",
    )

    response = client.get(f"/closet/items/{item_id}/processing", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["latest_run"] is None
    assert body["display_image"]["role"] == "original"
    assert body["thumbnail_image"] is None


def test_reprocess_success_and_idempotent_replay(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    fake_background_removal_provider.fail()
    headers = register_and_get_headers(client, email="reprocess-success@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-reprocess-success",
        complete_key="complete-reprocess-success",
    )
    first_job = run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    assert first_job is not None

    first_response = client.post(
        f"/closet/items/{item_id}/reprocess",
        headers={**headers, "Idempotency-Key": "reprocess-key-1"},
    )
    second_response = client.post(
        f"/closet/items/{item_id}/reprocess",
        headers={**headers, "Idempotency-Key": "reprocess-key-1"},
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert first_response.json()["item_id"] == second_response.json()["item_id"]
    assert first_response.json()["processing_status"] == "pending"
    assert first_response.json()["can_reprocess"] is False

    db_session.expire_all()
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

    assert len(jobs) == 3
    assert len(
        [
            job
            for job in jobs
            if job.job_kind == ProcessingRunType.IMAGE_PROCESSING
            and job.status == ClosetJobStatus.PENDING
        ]
    ) == 1
    assert len(
        [
            job
            for job in jobs
            if job.job_kind == ProcessingRunType.METADATA_EXTRACTION
            and job.status == ClosetJobStatus.PENDING
        ]
    ) == 1
    assert "image_reprocess_requested" in [event.event_type for event in audit_events]


def test_reprocess_rejects_when_processing_is_already_scheduled(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="reprocess-conflict@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-reprocess-conflict",
        complete_key="complete-reprocess-conflict",
    )

    response = client.post(
        f"/closet/items/{item_id}/reprocess",
        headers={**headers, "Idempotency-Key": "reprocess-conflict-key"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "processing_already_scheduled"


def test_reprocess_rejects_confirmed_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="reprocess-confirmed@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-reprocess-confirmed",
        complete_key="complete-reprocess-confirmed",
    )

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    item.lifecycle_status = LifecycleStatus.CONFIRMED
    item.processing_status = ProcessingStatus.COMPLETED
    db_session.commit()

    response = client.post(
        f"/closet/items/{item_id}/reprocess",
        headers={**headers, "Idempotency-Key": "reprocess-confirmed-key"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_lifecycle_transition"


def test_reprocess_rejects_archived_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="reprocess-archived@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-reprocess-archived",
        complete_key="complete-reprocess-archived",
    )

    db_session.expire_all()
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
    item.lifecycle_status = LifecycleStatus.ARCHIVED
    item.processing_status = ProcessingStatus.COMPLETED
    db_session.commit()

    response = client.post(
        f"/closet/items/{item_id}/reprocess",
        headers={**headers, "Idempotency-Key": "reprocess-archived-key"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_lifecycle_transition"


def test_reprocess_rejects_when_original_is_missing(
    client: TestClient,
) -> None:
    headers = register_and_get_headers(client, email="reprocess-missing-original@example.com")
    draft = create_draft(client, headers, idempotency_key="draft-reprocess-missing").json()

    response = client.post(
        f"/closet/items/{draft['id']}/reprocess",
        headers={**headers, "Idempotency-Key": "reprocess-missing-key"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "missing_primary_image"


def test_worker_smoke_flow_enqueue_run_once_and_read_processing_status(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
) -> None:
    fake_background_removal_provider.fail(
        payload={"reason_code": "provider_disabled", "message": "Smoke fallback."}
    )
    headers = register_and_get_headers(client, email="worker-smoke@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-worker-smoke",
        complete_key="complete-worker-smoke",
    )

    job = run_worker_once(db_session, fake_storage_client, fake_background_removal_provider)
    assert job is not None

    response = client.get(f"/closet/items/{item_id}/processing", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "completed_with_issues"
    assert body["latest_run"]["run_type"] == "image_processing"
    assert body["provider_results"][0]["task_type"] == "background_removal"
    assert body["display_image"]["role"] == "processed"
