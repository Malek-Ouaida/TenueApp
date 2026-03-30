from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import CLOSET_UPLOAD_MAX_FILE_SIZE, settings
from app.core.storage import InMemoryStorageClient
from app.domains.auth.models import User
from app.domains.closet.models import (
    ClosetItem,
    ClosetItemAuditEvent,
    ClosetItemImage,
    ClosetJob,
    ClosetUploadIntent,
    LifecycleStatus,
    MediaAsset,
    ProcessingRun,
    ProcessingRunType,
)


def register_and_get_headers(
    client: TestClient,
    *,
    email: str = "closet-upload@example.com",
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
    idempotency_key: str = "draft-key-1",
    title: str | None = "Black tee",
):
    request_headers = {**headers, "Idempotency-Key": idempotency_key}
    payload: dict[str, str] = {}
    if title is not None:
        payload["title"] = title
    return client.post("/closet/drafts", headers=request_headers, json=payload)


def create_upload_intent(
    client: TestClient,
    headers: dict[str, str],
    *,
    draft_id: UUID | str,
    filename: str = "tee.jpg",
    mime_type: str = "image/jpeg",
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
    draft_id: UUID | str,
    upload_intent_id: UUID | str,
    idempotency_key: str = "complete-key-1",
):
    return client.post(
        f"/closet/drafts/{draft_id}/uploads/complete",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"upload_intent_id": str(upload_intent_id)},
    )


def upload_to_fake_storage(
    fake_storage_client: InMemoryStorageClient,
    *,
    upload_response: dict[str, object],
    content: bytes,
) -> None:
    upload = upload_response["upload"]
    assert isinstance(upload, dict)
    url = str(upload["url"])
    headers = dict(upload["headers"])
    fake_storage_client.put_via_presigned_upload(url=url, headers=headers, content=content)


def build_image_bytes(
    *,
    size: tuple[int, int] = (32, 32),
    color: tuple[int, int, int] = (24, 24, 24),
    image_format: str = "JPEG",
) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def sha256_hex(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def get_user_by_email(db_session: Session, *, email: str) -> User:
    statement = select(User).where(User.email == email)
    user = db_session.execute(statement).scalar_one()
    return user


def test_create_draft_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/closet/drafts",
        headers={"Idempotency-Key": "draft-key-1"},
        json={"title": "Black tee"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_create_draft_is_idempotent(client: TestClient) -> None:
    headers = register_and_get_headers(client)

    first = create_draft(client, headers, idempotency_key="draft-key-1", title="Black tee")
    second = create_draft(client, headers, idempotency_key="draft-key-1", title="Black tee")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    review = client.get("/closet/review", headers=headers)
    assert review.status_code == 200
    assert len(review.json()["items"]) == 1


def test_create_draft_rejects_idempotency_conflict(client: TestClient) -> None:
    headers = register_and_get_headers(client)

    first = create_draft(client, headers, idempotency_key="draft-key-2", title="Black tee")
    second = create_draft(client, headers, idempotency_key="draft-key-2", title="White tee")

    assert first.status_code == 201
    assert second.status_code == 409


def test_create_upload_intent_success(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()

    response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["upload"]["method"] == "PUT"
    assert body["upload"]["headers"]["Content-Type"] == "image/jpeg"

    upload_to_fake_storage(fake_storage_client, upload_response=body, content=image_bytes)


def test_create_upload_intent_rejects_other_user(client: TestClient) -> None:
    owner_headers = register_and_get_headers(client, email="owner@example.com")
    intruder_headers = register_and_get_headers(client, email="intruder@example.com")
    draft = create_draft(client, owner_headers).json()
    image_bytes = build_image_bytes()

    response = create_upload_intent(
        client,
        intruder_headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )

    assert response.status_code == 404


def test_create_upload_intent_rejects_unsupported_mime(client: TestClient) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()

    response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        mime_type="image/heic",
        file_size=1024,
        sha256="a" * 64,
    )

    assert response.status_code == 422


def test_create_upload_intent_rejects_file_size_cap(client: TestClient) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()

    response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=CLOSET_UPLOAD_MAX_FILE_SIZE + 1,
        sha256="a" * 64,
    )

    assert response.status_code == 422


def test_create_upload_intent_rejects_invalid_checksum_format(client: TestClient) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()

    response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=1024,
        sha256="not-a-sha",
    )

    assert response.status_code == 422


def test_create_second_upload_intent_after_primary_image_is_allowed(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()

    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=image_bytes,
    )
    complete = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )

    assert complete.status_code == 200

    second_intent = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert second_intent.status_code == 200
    assert second_intent.json()["upload_intent_id"] != upload_response.json()["upload_intent_id"]


def test_finalize_upload_success(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=image_bytes,
    )

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == draft["id"]
    assert body["lifecycle_status"] == "processing"
    assert body["processing_status"] == "pending"
    assert body["has_primary_image"] is True
    assert body["failure_summary"] is None


def test_finalize_upload_is_idempotent(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=image_bytes,
    )

    first = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
        idempotency_key="complete-key-2",
    )
    second = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
        idempotency_key="complete-key-2",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_finalize_upload_rejects_expired_intent(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    intent_id = UUID(upload_response.json()["upload_intent_id"])
    intent = db_session.execute(
        select(ClosetUploadIntent).where(ClosetUploadIntent.id == intent_id)
    ).scalar_one()
    intent.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=intent_id,
    )

    assert response.status_code == 409


def test_finalize_upload_rejects_missing_object(client: TestClient) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )

    assert response.status_code == 409


def test_finalize_upload_rejects_checksum_mismatch(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256="0" * 64,
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=image_bytes,
    )

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )

    assert response.status_code == 409


def test_finalize_upload_rejects_invalid_image_decode(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    raw_bytes = b"this is not an image"
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(raw_bytes),
        sha256=sha256_hex(raw_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=raw_bytes,
    )

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )

    assert response.status_code == 422


def test_finalize_upload_rejects_dimension_cap(
    client: TestClient,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    huge_image = build_image_bytes(size=(8001, 10), image_format="PNG")
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        filename="oversized.png",
        mime_type="image/png",
        file_size=len(huge_image),
        sha256=sha256_hex(huge_image),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=huge_image,
    )

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )

    assert response.status_code == 422


def test_finalize_upload_persists_asset_and_audit_run(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client)
    draft = create_draft(client, headers).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=image_bytes,
    )

    response = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
    )
    assert response.status_code == 200

    draft_id = UUID(draft["id"])
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == draft_id)).scalar_one()
    media_assets = list(db_session.execute(select(MediaAsset)).scalars())
    item_images = list(
        db_session.execute(
            select(ClosetItemImage).where(ClosetItemImage.closet_item_id == draft_id)
        ).scalars()
    )
    audit_events = list(
        db_session.execute(
            select(ClosetItemAuditEvent).where(ClosetItemAuditEvent.closet_item_id == draft_id)
        ).scalars()
    )
    processing_runs = list(
        db_session.execute(
            select(ProcessingRun).where(ProcessingRun.closet_item_id == draft_id)
        ).scalars()
    )
    jobs = list(
        db_session.execute(select(ClosetJob).where(ClosetJob.closet_item_id == draft_id)).scalars()
    )

    assert item.primary_image_id is not None
    assert item.lifecycle_status.value == "processing"
    assert item.processing_status.value == "pending"
    assert len(media_assets) == 1
    assert len(item_images) == 1
    assert any(event.event_type == "upload_finalized" for event in audit_events)
    assert any(event.event_type == "image_processing_enqueued" for event in audit_events)
    assert len(processing_runs) == 1
    assert processing_runs[0].run_type == ProcessingRunType.UPLOAD_VALIDATION
    assert len(jobs) == 1
    assert jobs[0].job_kind == ProcessingRunType.IMAGE_PROCESSING


def test_finalize_additional_upload_appends_original_image_without_reenqueuing_processing(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="closet-upload-multi@example.com")
    draft = create_draft(client, headers, idempotency_key="draft-key-multi").json()
    first_image_bytes = build_image_bytes(color=(24, 24, 24))
    first_upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(first_image_bytes),
        sha256=sha256_hex(first_image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=first_upload_response.json(),
        content=first_image_bytes,
    )
    first_complete = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=first_upload_response.json()["upload_intent_id"],
        idempotency_key="complete-key-multi-1",
    )
    assert first_complete.status_code == 200

    second_image_bytes = build_image_bytes(color=(220, 220, 220))
    second_upload_response = create_upload_intent(
        client,
        headers,
        draft_id=draft["id"],
        file_size=len(second_image_bytes),
        sha256=sha256_hex(second_image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=second_upload_response.json(),
        content=second_image_bytes,
    )

    second_complete = complete_upload(
        client,
        headers,
        draft_id=draft["id"],
        upload_intent_id=second_upload_response.json()["upload_intent_id"],
        idempotency_key="complete-key-multi-2",
    )

    assert second_complete.status_code == 200
    body = second_complete.json()
    assert len(body["original_images"]) == 2
    assert sum(1 for image in body["original_images"] if image["is_primary"]) == 1
    assert [image["position"] for image in body["original_images"]] == [0, 1]

    draft_id = UUID(draft["id"])
    item = db_session.execute(select(ClosetItem).where(ClosetItem.id == draft_id)).scalar_one()
    item_images = list(
        db_session.execute(
            select(ClosetItemImage)
            .where(ClosetItemImage.closet_item_id == draft_id)
            .order_by(ClosetItemImage.position.asc(), ClosetItemImage.id.asc())
        ).scalars()
    )
    processing_runs = list(
        db_session.execute(
            select(ProcessingRun).where(ProcessingRun.closet_item_id == draft_id)
        ).scalars()
    )
    jobs = list(
        db_session.execute(select(ClosetJob).where(ClosetJob.closet_item_id == draft_id)).scalars()
    )

    assert len(item_images) == 2
    assert item.primary_image_id == item_images[0].id
    assert [item_image.position for item_image in item_images] == [0, 1]
    assert len(processing_runs) == 2
    assert all(run.run_type == ProcessingRunType.UPLOAD_VALIDATION for run in processing_runs)
    assert len(jobs) == 1
    assert jobs[0].job_kind == ProcessingRunType.IMAGE_PROCESSING


def test_review_queue_excludes_confirmed_and_archived_items(
    client: TestClient,
    db_session: Session,
) -> None:
    email = "review-user@example.com"
    headers = register_and_get_headers(client, email=email)
    visible_draft = create_draft(client, headers, idempotency_key="draft-1").json()
    confirmed_draft = create_draft(client, headers, idempotency_key="draft-2").json()
    archived_draft = create_draft(client, headers, idempotency_key="draft-3").json()

    confirmed_item = db_session.execute(
        select(ClosetItem).where(ClosetItem.id == UUID(confirmed_draft["id"]))
    ).scalar_one()
    confirmed_item.lifecycle_status = LifecycleStatus.CONFIRMED
    archived_item = db_session.execute(
        select(ClosetItem).where(ClosetItem.id == UUID(archived_draft["id"]))
    ).scalar_one()
    archived_item.lifecycle_status = LifecycleStatus.ARCHIVED
    db_session.commit()

    response = client.get("/closet/review", headers=headers)
    assert response.status_code == 200

    ids = [entry["id"] for entry in response.json()["items"]]
    assert ids == [visible_draft["id"]]


def test_review_queue_cursor_pagination_is_stable(
    client: TestClient,
    db_session: Session,
) -> None:
    email = "cursor-user@example.com"
    headers = register_and_get_headers(client, email=email)
    first = create_draft(client, headers, idempotency_key="cursor-1", title="One").json()
    second = create_draft(client, headers, idempotency_key="cursor-2", title="Two").json()
    third = create_draft(client, headers, idempotency_key="cursor-3", title="Three").json()
    user = get_user_by_email(db_session, email=email)
    now = datetime.now(UTC)

    for item_id, updated_at in [
        (UUID(first["id"]), now),
        (UUID(second["id"]), now - timedelta(minutes=1)),
        (UUID(third["id"]), now - timedelta(minutes=2)),
    ]:
        item = db_session.execute(
            select(ClosetItem).where(ClosetItem.id == item_id, ClosetItem.user_id == user.id)
        ).scalar_one()
        item.updated_at = updated_at
    db_session.commit()

    page_one = client.get("/closet/review?limit=2", headers=headers)
    assert page_one.status_code == 200
    page_one_body = page_one.json()
    assert [entry["id"] for entry in page_one_body["items"]] == [first["id"], second["id"]]
    assert page_one_body["next_cursor"] is not None

    page_two = client.get(
        f"/closet/review?limit=2&cursor={page_one_body['next_cursor']}",
        headers=headers,
    )
    assert page_two.status_code == 200
    page_two_body = page_two.json()
    assert [entry["id"] for entry in page_two_body["items"]] == [third["id"]]
    assert page_two_body["next_cursor"] is None


@pytest.mark.db_integration
def test_minio_presigned_upload_smoke(
    client_without_storage_override: TestClient,
) -> None:
    try:
        httpx.get(settings.minio_endpoint, timeout=1.0)
    except httpx.HTTPError:
        pytest.skip("Local MinIO is not reachable.")

    headers = register_and_get_headers(
        client_without_storage_override,
        email="minio-smoke@example.com",
    )
    draft = create_draft(
        client_without_storage_override,
        headers,
        idempotency_key="smoke-draft",
    ).json()
    image_bytes = build_image_bytes()
    upload_response = create_upload_intent(
        client_without_storage_override,
        headers,
        draft_id=draft["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert upload_response.status_code == 200

    upload = upload_response.json()["upload"]
    put_response = httpx.put(
        upload["url"],
        headers=upload["headers"],
        content=image_bytes,
        timeout=10.0,
    )
    assert put_response.status_code in {200, 204}

    finalize_response = complete_upload(
        client_without_storage_override,
        headers,
        draft_id=draft["id"],
        upload_intent_id=upload_response.json()["upload_intent_id"],
        idempotency_key="smoke-complete",
    )
    assert finalize_response.status_code == 200
    assert finalize_response.json()["has_primary_image"] is True
