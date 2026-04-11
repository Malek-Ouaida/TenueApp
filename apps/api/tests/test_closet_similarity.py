from __future__ import annotations

from io import BytesIO
from typing import Any, cast
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import InMemoryStorageClient
from app.domains.auth.models import User
from app.domains.closet.models import (
    ApplicabilityState,
    AuditActorType,
    ClosetItemImageRole,
    ClosetJob,
    FieldReviewState,
    FieldSource,
    ProcessingRunType,
)
from app.domains.closet.repository import ClosetJobRepository, ClosetRepository
from app.domains.closet.service import ClosetLifecycleService
from app.domains.closet.similarity_service import ClosetSimilarityService
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


def build_patterned_image_bytes(
    *,
    accent: tuple[int, int, int],
    size: tuple[int, int] = (96, 96),
) -> bytes:
    image = Image.new("RGB", size, color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    for index in range(0, size[0], 12):
        draw.rectangle((index, 0, min(index + 5, size[0] - 1), size[1] - 1), fill=accent)
    draw.rectangle((20, 20, size[0] - 20, size[1] - 20), outline=(20, 20, 20), width=4)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_alternate_image_bytes() -> bytes:
    image = Image.new("RGB", (96, 96), color=(235, 235, 235))
    draw = ImageDraw.Draw(image)
    for index in range(0, 96, 10):
        draw.line((0, index, 95, 95 - index), fill=(20, 20, 20), width=3)
    draw.ellipse((18, 18, 78, 78), outline=(180, 40, 40), width=6)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
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
        filename=f"{key_prefix}.png",
        mime_type="image/png",
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
    return worker.run_once(worker_name="test-similarity-worker") is not None


def drain_worker(
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    max_iterations: int = 20,
) -> int:
    processed = 0
    for _ in range(max_iterations):
        if not run_worker_once(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        ):
            break
        processed += 1
    return processed


def read_review_snapshot(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
) -> dict[str, Any]:
    response = client.get(f"/closet/items/{item_id}/review", headers=headers)
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def patch_review(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
    expected_review_version: str,
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    response = client.patch(
        f"/closet/items/{item_id}",
        headers=headers,
        json={
            "expected_review_version": expected_review_version,
            "changes": changes,
        },
    )
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def confirm_review(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
    expected_review_version: str,
) -> dict[str, Any]:
    response = client.post(
        f"/closet/items/{item_id}/confirm",
        headers=headers,
        json={"expected_review_version": expected_review_version},
    )
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


def create_review_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    headers: dict[str, str],
    title: str,
    key_prefix: str,
    original_image_bytes: bytes,
    processed_image_bytes: bytes,
    raw_fields: dict[str, Any],
) -> UUID:
    fake_background_removal_provider.succeed(
        image_bytes=processed_image_bytes,
        mime_type="image/png",
    )
    fake_metadata_extraction_provider.succeed(raw_fields=raw_fields)
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        title=title,
        key_prefix=key_prefix,
        image_bytes=original_image_bytes,
    )
    processed_count = drain_worker(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        max_iterations=3,
    )
    assert processed_count == 3
    return item_id


def confirm_item_via_api(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
) -> dict[str, Any]:
    review = read_review_snapshot(client, headers, item_id=item_id)
    patched = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=str(review["review_version"]),
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )
    return confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=str(patched["review_version"]),
    )


def get_user_by_email(db_session: Session, *, email: str) -> User:
    return db_session.execute(select(User).where(User.email == email)).scalar_one()


def default_top_tshirt_raw_fields() -> dict[str, Any]:
    return {
        "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
        "subcategory": {
            "value": "tee shirt",
            "confidence": 0.97,
            "applicability_state": "value",
        },
    }


def confirm_item_directly(
    db_session: Session,
    *,
    user_id: UUID,
    item_id: UUID,
    category: str = "tops",
    subcategory: str = "t-shirt",
) -> None:
    lifecycle_service = ClosetLifecycleService(
        session=db_session,
        repository=ClosetRepository(db_session),
    )
    lifecycle_service.upsert_field_state(
        item_id=item_id,
        user_id=user_id,
        field_name="category",
        canonical_value=category,
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
    )
    lifecycle_service.upsert_field_state(
        item_id=item_id,
        user_id=user_id,
        field_name="subcategory",
        canonical_value=subcategory,
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
    )
    lifecycle_service.confirm_item(item_id=item_id, user_id=user_id)


def list_similarity_jobs(db_session: Session, *, item_id: UUID) -> list[ClosetJob]:
    return ClosetJobRepository(db_session).list_jobs_for_item_kind(
        closet_item_id=item_id,
        job_kind=ProcessingRunType.SIMILARITY_RECOMPUTE,
    )


def delete_comparison_assets(
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    *,
    item_id: UUID,
) -> None:
    repository = ClosetRepository(db_session)
    item = repository.get_item(item_id=item_id)
    assert item is not None
    image_records = [
        repository.get_active_image_asset_by_role(
            closet_item_id=item_id,
            role=ClosetItemImageRole.THUMBNAIL,
        ),
        repository.get_active_image_asset_by_role(
            closet_item_id=item_id,
            role=ClosetItemImageRole.PROCESSED,
        ),
        repository.get_primary_image_asset(item=item),
    ]
    for record in image_records:
        if record is None:
            continue
        _, asset = record
        fake_storage_client.delete_object(bucket=asset.bucket, key=asset.key)


def test_similarity_status_is_not_requested_until_a_recompute_run_exists(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="similarity-not-requested@example.com")
    item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Navy tee",
        key_prefix="similarity-not-requested",
        original_image_bytes=build_patterned_image_bytes(accent=(30, 60, 120)),
        processed_image_bytes=build_patterned_image_bytes(accent=(30, 60, 120)),
        raw_fields=default_top_tshirt_raw_fields(),
    )
    user = get_user_by_email(db_session, email="similarity-not-requested@example.com")
    confirm_item_directly(db_session, user_id=user.id, item_id=item_id)

    response = client.get(f"/closet/items/{item_id}/similar", headers=headers)

    assert response.status_code == 200
    assert response.json()["similarity_status"] == "not_requested"
    assert response.json()["items"] == []


def test_similarity_worker_creates_duplicate_candidates_and_explanations(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="similarity-duplicates@example.com")
    processed_bytes = build_patterned_image_bytes(accent=(10, 90, 160))
    first_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="First tee",
        key_prefix="similarity-dup-first",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )
    second_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Second tee",
        key_prefix="similarity-dup-second",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )

    confirm_item_via_api(client, headers, item_id=first_item_id)
    confirm_item_via_api(client, headers, item_id=second_item_id)
    assert (
        drain_worker(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        )
        >= 2
    )

    first_response = client.get(f"/closet/items/{first_item_id}/duplicates", headers=headers)
    second_response = client.get(f"/closet/items/{second_item_id}/duplicates", headers=headers)

    assert first_response.status_code == 200
    assert first_response.json()["similarity_status"] == "completed"
    first_items = first_response.json()["items"]
    assert len(first_items) == 1
    assert first_items[0]["label"] == "possible_duplicate"
    assert first_items[0]["other_item"]["item_id"] == str(second_item_id)
    assert {signal["code"] for signal in first_items[0]["signals"]} >= {
        "category_match",
        "subcategory_match",
        "image_hash_match",
    }

    assert second_response.status_code == 200
    assert second_response.json()["items"][0]["other_item"]["item_id"] == str(first_item_id)


def test_similarity_other_item_matches_browse_item_contract(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="similarity-contract@example.com")
    processed_bytes = build_patterned_image_bytes(accent=(30, 70, 140))
    first_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Contract tee A",
        key_prefix="similarity-contract-a",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )
    second_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Contract tee B",
        key_prefix="similarity-contract-b",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )

    confirm_item_via_api(client, headers, item_id=first_item_id)
    confirm_item_via_api(client, headers, item_id=second_item_id)
    assert (
        drain_worker(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        )
        >= 2
    )

    browse_response = client.get("/closet/items", headers=headers)
    similar_response = client.get(f"/closet/items/{first_item_id}/duplicates", headers=headers)

    assert browse_response.status_code == 200
    assert similar_response.status_code == 200
    browse_items = {
        item["item_id"]: item
        for item in cast(list[dict[str, Any]], browse_response.json()["items"])
    }
    other_item = cast(dict[str, Any], similar_response.json()["items"][0]["other_item"])
    browse_item = browse_items[str(second_item_id)]

    assert set(other_item.keys()) == set(browse_item.keys())
    assert other_item["season_tags"] == browse_item["season_tags"]


def test_similarity_metadata_only_fallback_returns_similar_items_with_issues(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    email = "similarity-fallback@example.com"
    headers = register_and_get_headers(client, email=email)
    first_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Fallback tee A",
        key_prefix="similarity-fallback-a",
        original_image_bytes=build_patterned_image_bytes(accent=(20, 60, 120)),
        processed_image_bytes=build_patterned_image_bytes(accent=(20, 60, 120)),
        raw_fields=default_top_tshirt_raw_fields(),
    )
    second_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Fallback tee B",
        key_prefix="similarity-fallback-b",
        original_image_bytes=build_alternate_image_bytes(),
        processed_image_bytes=build_alternate_image_bytes(),
        raw_fields=default_top_tshirt_raw_fields(),
    )
    user = get_user_by_email(db_session, email=email)
    confirm_item_directly(db_session, user_id=user.id, item_id=first_item_id)
    confirm_item_directly(db_session, user_id=user.id, item_id=second_item_id)
    delete_comparison_assets(db_session, fake_storage_client, item_id=second_item_id)

    similarity_service = ClosetSimilarityService(
        session=db_session,
        repository=ClosetRepository(db_session),
        job_repository=ClosetJobRepository(db_session),
        storage=fake_storage_client,
    )
    first_item = ClosetRepository(db_session).get_item(item_id=first_item_id)
    assert first_item is not None
    similarity_service.enqueue_similarity_for_item(
        item=first_item,
        actor_type=AuditActorType.SYSTEM,
        actor_user_id=None,
        raise_on_duplicate=False,
        trigger="test",
    )
    db_session.commit()
    assert (
        drain_worker(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        )
        >= 1
    )

    response = client.get(f"/closet/items/{first_item_id}/similar", headers=headers)

    assert response.status_code == 200
    assert response.json()["similarity_status"] == "completed_with_issues"
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["other_item"]["item_id"] == str(second_item_id)
    assert response.json()["items"][0]["label"] == "similar_item"


def test_similarity_actions_are_idempotent_and_visible_from_both_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="similarity-actions@example.com")
    processed_bytes = build_patterned_image_bytes(accent=(40, 80, 150))
    first_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Action tee A",
        key_prefix="similarity-action-a",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )
    second_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Action tee B",
        key_prefix="similarity-action-b",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )
    confirm_item_via_api(client, headers, item_id=first_item_id)
    confirm_item_via_api(client, headers, item_id=second_item_id)
    assert (
        drain_worker(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        )
        >= 2
    )

    duplicates = client.get(f"/closet/items/{first_item_id}/duplicates", headers=headers)
    edge_id = duplicates.json()["items"][0]["edge_id"]

    dismiss_first = client.post(f"/closet/similarity/{edge_id}/dismiss", headers=headers)
    dismiss_second = client.post(f"/closet/similarity/{edge_id}/dismiss", headers=headers)

    assert dismiss_first.status_code == 200
    assert dismiss_first.json()["decision_status"] == "dismissed"
    assert dismiss_second.status_code == 200
    assert dismiss_second.json()["decision_status"] == "dismissed"
    duplicates_after_dismiss = client.get(
        f"/closet/items/{first_item_id}/duplicates",
        headers=headers,
    )
    assert duplicates_after_dismiss.json()["items"] == []

    mark_duplicate = client.post(
        f"/closet/similarity/{edge_id}/mark-duplicate",
        headers=headers,
    )
    mark_duplicate_repeat = client.post(
        f"/closet/similarity/{edge_id}/mark-duplicate",
        headers=headers,
    )

    assert mark_duplicate.status_code == 200
    assert mark_duplicate.json()["decision_status"] == "marked_duplicate"
    assert mark_duplicate.json()["similarity_type"] == "duplicate"
    assert mark_duplicate_repeat.status_code == 200
    assert mark_duplicate_repeat.json()["decision_status"] == "marked_duplicate"

    first_duplicates = client.get(f"/closet/items/{first_item_id}/duplicates", headers=headers)
    second_duplicates = client.get(f"/closet/items/{second_item_id}/duplicates", headers=headers)
    assert first_duplicates.json()["items"][0]["label"] == "duplicate"
    assert second_duplicates.json()["items"][0]["other_item"]["item_id"] == str(first_item_id)


def test_marked_duplicates_survive_recompute_even_after_algorithmic_score_drops(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    email = "similarity-persist@example.com"
    headers = register_and_get_headers(client, email=email)
    processed_bytes = build_patterned_image_bytes(accent=(60, 90, 170))
    first_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Persist tee A",
        key_prefix="similarity-persist-a",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )
    second_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Persist tee B",
        key_prefix="similarity-persist-b",
        original_image_bytes=processed_bytes,
        processed_image_bytes=processed_bytes,
        raw_fields=default_top_tshirt_raw_fields(),
    )
    confirm_item_via_api(client, headers, item_id=first_item_id)
    confirm_item_via_api(client, headers, item_id=second_item_id)
    assert (
        drain_worker(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        )
        >= 2
    )

    duplicate_response = client.get(
        f"/closet/items/{first_item_id}/duplicates",
        headers=headers,
    )
    edge_id = duplicate_response.json()["items"][0]["edge_id"]
    mark_duplicate = client.post(f"/closet/similarity/{edge_id}/mark-duplicate", headers=headers)
    assert mark_duplicate.status_code == 200

    repository = ClosetRepository(db_session)
    projection = repository.get_metadata_projection(item_id=second_item_id)
    assert projection is not None
    projection.category = "outerwear"
    projection.subcategory = "jacket"
    db_session.commit()

    similarity_service = ClosetSimilarityService(
        session=db_session,
        repository=repository,
        job_repository=ClosetJobRepository(db_session),
        storage=fake_storage_client,
    )
    first_item = repository.get_item(item_id=first_item_id)
    assert first_item is not None
    similarity_service.enqueue_similarity_for_item(
        item=first_item,
        actor_type=AuditActorType.SYSTEM,
        actor_user_id=None,
        raise_on_duplicate=False,
        trigger="test",
    )
    db_session.commit()
    assert (
        drain_worker(
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
        )
        >= 1
    )

    duplicates = client.get(f"/closet/items/{first_item_id}/duplicates", headers=headers)

    assert duplicates.status_code == 200
    assert len(duplicates.json()["items"]) == 1
    assert duplicates.json()["items"][0]["label"] == "duplicate"
    assert duplicates.json()["items"][0]["decision_status"] == "marked_duplicate"


def test_similarity_backfill_only_enqueues_missing_completed_runs(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    email = "similarity-backfill@example.com"
    headers = register_and_get_headers(client, email=email)
    first_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Backfill tee A",
        key_prefix="similarity-backfill-a",
        original_image_bytes=build_patterned_image_bytes(accent=(20, 100, 150)),
        processed_image_bytes=build_patterned_image_bytes(accent=(20, 100, 150)),
        raw_fields=default_top_tshirt_raw_fields(),
    )
    second_item_id = create_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Backfill tee B",
        key_prefix="similarity-backfill-b",
        original_image_bytes=build_patterned_image_bytes(accent=(25, 105, 155)),
        processed_image_bytes=build_patterned_image_bytes(accent=(25, 105, 155)),
        raw_fields=default_top_tshirt_raw_fields(),
    )
    user = get_user_by_email(db_session, email=email)
    confirm_item_directly(db_session, user_id=user.id, item_id=first_item_id)
    confirm_item_directly(db_session, user_id=user.id, item_id=second_item_id)

    similarity_service = ClosetSimilarityService(
        session=db_session,
        repository=ClosetRepository(db_session),
        job_repository=ClosetJobRepository(db_session),
        storage=fake_storage_client,
    )

    first_count = similarity_service.enqueue_similarity_backfill()
    second_count = similarity_service.enqueue_similarity_backfill()

    assert first_count == 2
    assert second_count == 0
    assert len(list_similarity_jobs(db_session, item_id=first_item_id)) == 1
    assert len(list_similarity_jobs(db_session, item_id=second_item_id)) == 1
