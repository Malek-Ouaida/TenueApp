from __future__ import annotations

from io import BytesIO
from typing import Any, cast
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.storage import InMemoryStorageClient
from app.domains.closet.worker import ClosetWorker
from app.domains.closet.worker_runner import build_worker_handlers


def register_and_get_headers(
    client: TestClient,
    *,
    email: str,
) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    access_token = response.json()["session"]["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


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


def create_draft(
    client: TestClient,
    headers: dict[str, str],
    *,
    idempotency_key: str,
    title: str,
) -> dict[str, Any]:
    response = client.post(
        "/closet/drafts",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"title": title},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


def create_upload_intent(
    client: TestClient,
    headers: dict[str, str],
    *,
    draft_id: str,
    filename: str,
    mime_type: str,
    file_size: int,
    sha256: str,
) -> dict[str, Any]:
    response = client.post(
        f"/closet/drafts/{draft_id}/upload-intents",
        headers=headers,
        json={
            "filename": filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "sha256": sha256,
        },
    )
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def upload_to_fake_storage(
    fake_storage_client: InMemoryStorageClient,
    *,
    upload_response: dict[str, Any],
    content: bytes,
) -> None:
    upload = cast(dict[str, Any], upload_response["upload"])
    fake_storage_client.put_via_presigned_upload(
        url=str(upload["url"]),
        headers=cast(dict[str, str], upload["headers"]),
        content=content,
    )


def complete_upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    draft_id: str,
    upload_intent_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    response = client.post(
        f"/closet/drafts/{draft_id}/uploads/complete",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"upload_intent_id": upload_intent_id},
    )
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def create_uploaded_item(
    client: TestClient,
    headers: dict[str, str],
    fake_storage_client: InMemoryStorageClient,
    *,
    title: str,
    key_prefix: str,
    image_bytes: bytes,
) -> UUID:
    draft = create_draft(
        client,
        headers,
        idempotency_key=f"draft-{key_prefix}",
        title=title,
    )
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=str(draft["id"]),
        filename=f"{key_prefix}.jpg",
        mime_type="image/jpeg",
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response,
        content=image_bytes,
    )
    complete_upload(
        client,
        headers,
        draft_id=str(draft["id"]),
        upload_intent_id=str(upload_response["upload_intent_id"]),
        idempotency_key=f"complete-{key_prefix}",
    )
    return UUID(str(draft["id"]))


def run_worker_once(
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> bool:
    worker = ClosetWorker(
        session=db_session,
        handlers=build_worker_handlers(
            storage=fake_storage_client,
            background_removal_provider=fake_background_removal_provider,
            metadata_extraction_provider=fake_metadata_extraction_provider,
        ),
    )
    return worker.run_once(worker_name="test-confirmed-item-worker") is not None


def create_confirmed_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    headers: dict[str, str],
    key_prefix: str,
    title: str,
) -> UUID:
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
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        }
    )
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        title=title,
        key_prefix=key_prefix,
        image_bytes=build_image_bytes(),
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

    review = client.get(f"/closet/items/{item_id}/review", headers=headers)
    assert review.status_code == 200
    patch = client.patch(
        f"/closet/items/{item_id}/review",
        headers=headers,
        json={
            "expected_review_version": review.json()["review_version"],
            "changes": [
                {"field_name": "category", "operation": "accept_suggestion"},
                {"field_name": "subcategory", "operation": "accept_suggestion"},
            ],
        },
    )
    assert patch.status_code == 200
    confirm = client.post(
        f"/closet/items/{item_id}/confirm",
        headers=headers,
        json={"expected_review_version": patch.json()["review_version"]},
    )
    assert confirm.status_code == 200
    return item_id


def test_confirmed_item_edit_snapshot_and_patch_updates_metadata(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="confirmed-edit@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        key_prefix="confirmed-edit",
        title="Confirmed edit tee",
    )

    before = client.get(f"/closet/items/{item_id}/edit", headers=headers)
    assert before.status_code == 200

    patch = client.patch(
        f"/closet/items/{item_id}/edit",
        headers=headers,
        json={
            "expected_item_version": before.json()["item_version"],
            "changes": [
                {"field_name": "brand", "operation": "set_value", "canonical_value": "COS"},
                {
                    "field_name": "fit_tags",
                    "operation": "set_value",
                    "canonical_value": ["oversized"],
                },
                {
                    "field_name": "season_tags",
                    "operation": "set_value",
                    "canonical_value": ["fall", "winter"],
                },
            ],
        },
    )

    assert patch.status_code == 200
    body = patch.json()
    assert body["metadata_projection"]["brand"] == "COS"
    assert body["metadata_projection"]["fit_tags"] == ["oversized"]
    assert body["metadata_projection"]["season_tags"] == ["fall", "winter"]
    brand_state = next(field for field in body["field_states"] if field["field_name"] == "brand")
    assert brand_state["source"] == "user"
    assert brand_state["review_state"] == "user_edited"
    assert body["item_version"] != before.json()["item_version"]


def test_confirmed_item_edit_rejects_stale_versions_and_required_field_clears(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="confirmed-edit-stale@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        key_prefix="confirmed-edit-stale",
        title="Confirmed stale tee",
    )

    before = client.get(f"/closet/items/{item_id}/edit", headers=headers)
    assert before.status_code == 200
    fresh = client.patch(
        f"/closet/items/{item_id}/edit",
        headers=headers,
        json={
            "expected_item_version": before.json()["item_version"],
            "changes": [{"field_name": "brand", "operation": "set_value", "canonical_value": "COS"}],
        },
    )
    assert fresh.status_code == 200

    stale = client.patch(
        f"/closet/items/{item_id}/edit",
        headers=headers,
        json={
            "expected_item_version": before.json()["item_version"],
            "changes": [{"field_name": "material", "operation": "set_value", "canonical_value": "cotton"}],
        },
    )
    invalid = client.patch(
        f"/closet/items/{item_id}/edit",
        headers=headers,
        json={
            "expected_item_version": fresh.json()["item_version"],
            "changes": [{"field_name": "category", "operation": "clear"}],
        },
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_review_version"
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_review_mutation"


def test_confirmed_item_media_flow_add_primary_remove_and_prevent_last_remove(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="confirmed-media@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        key_prefix="confirmed-media",
        title="Confirmed media tee",
    )

    extra_image_bytes = build_image_bytes(color=(200, 200, 200))
    upload_intent = client.post(
        f"/closet/items/{item_id}/images/upload-intents",
        headers=headers,
        json={
            "filename": "back.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(extra_image_bytes),
            "sha256": sha256_hex(extra_image_bytes),
        },
    )
    assert upload_intent.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=cast(dict[str, Any], upload_intent.json()),
        content=extra_image_bytes,
    )
    completed = client.post(
        f"/closet/items/{item_id}/images/uploads/complete",
        headers=headers,
        json={"upload_intent_id": upload_intent.json()["upload_intent_id"]},
    )
    assert completed.status_code == 200
    assert len(completed.json()["original_images"]) == 2

    original_images = completed.json()["original_images"]
    second_image_id = next(
        image["image_id"] for image in original_images if image["position"] == 1
    )
    promote = client.post(
        f"/closet/items/{item_id}/images/{second_image_id}/primary",
        headers=headers,
    )
    assert promote.status_code == 200
    assert promote.json()["processing_status"] == "pending"
    assert promote.json()["original_images"][0]["image_id"] == second_image_id
    assert promote.json()["original_images"][0]["is_primary"] is True

    old_primary_id = next(
        image["image_id"] for image in promote.json()["original_images"] if not image["is_primary"]
    )
    removed = client.delete(f"/closet/items/{item_id}/images/{old_primary_id}", headers=headers)
    assert removed.status_code == 200
    assert len(removed.json()["original_images"]) == 1
    assert removed.json()["original_images"][0]["is_primary"] is True

    last_remove = client.delete(
        f"/closet/items/{item_id}/images/{removed.json()['original_images'][0]['image_id']}",
        headers=headers,
    )
    assert last_remove.status_code == 409
    assert last_remove.json()["detail"]["code"] == "last_confirmed_item_image_required"


def test_archive_restore_and_include_archived_work_for_confirmed_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="confirmed-restore@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        key_prefix="confirmed-restore",
        title="Confirmed restore tee",
    )

    archive = client.post(f"/closet/items/{item_id}/archive", headers=headers)
    hidden_detail = client.get(f"/closet/items/{item_id}", headers=headers)
    archived_detail = client.get(f"/closet/items/{item_id}?include_archived=true", headers=headers)
    archived_list = client.get("/closet/items?include_archived=true", headers=headers)

    assert archive.status_code == 204
    assert hidden_detail.status_code == 404
    assert archived_detail.status_code == 200
    assert archived_detail.json()["lifecycle_status"] == "archived"
    assert str(item_id) in {item["item_id"] for item in archived_list.json()["items"]}

    restore = client.post(f"/closet/items/{item_id}/restore", headers=headers)
    restored_detail = client.get(f"/closet/items/{item_id}", headers=headers)

    assert restore.status_code == 204
    assert restored_detail.status_code == 200
    assert restored_detail.json()["lifecycle_status"] == "confirmed"
