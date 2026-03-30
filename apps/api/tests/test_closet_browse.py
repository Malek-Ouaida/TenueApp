from __future__ import annotations

from io import BytesIO
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import InMemoryStorageClient
from app.domains.closet.models import (
    ApplicabilityState,
    ClosetItem,
    FieldReviewState,
    FieldSource,
    ProcessingStatus,
    utcnow,
)
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.service import ClosetLifecycleService
from app.domains.closet.worker import ClosetWorker
from app.domains.closet.worker_runner import build_worker_handlers


def register_and_get_headers(
    client: TestClient,
    *,
    email: str = "closet-browse@example.com",
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
):
    return client.post(
        "/closet/drafts",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"title": title},
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


def create_uploaded_item(
    client: TestClient,
    headers: dict[str, str],
    fake_storage_client: InMemoryStorageClient,
    *,
    draft_key: str,
    complete_key: str,
    title: str,
) -> UUID:
    image_bytes = build_image_bytes()
    draft = create_draft(client, headers, idempotency_key=draft_key, title=title).json()
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
) -> bool:
    worker = ClosetWorker(
        session=db_session,
        handlers=build_worker_handlers(
            storage=fake_storage_client,
            background_removal_provider=fake_background_removal_provider,
            metadata_extraction_provider=fake_metadata_extraction_provider,
        ),
    )
    return worker.run_once(worker_name="test-closet-worker") is not None


def create_normalized_review_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    raw_fields: dict[str, Any],
    email: str,
    title: str,
) -> tuple[dict[str, str], UUID]:
    headers = register_and_get_headers(client, email=email)
    item_id = create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        raw_fields=raw_fields,
        title=title,
        key_prefix=email,
    )
    return headers, item_id


def create_normalized_review_item_for_user(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    headers: dict[str, str],
    raw_fields: dict[str, Any],
    title: str,
    key_prefix: str,
) -> UUID:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(raw_fields=raw_fields)
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key=f"draft-{key_prefix}",
        complete_key=f"complete-{key_prefix}",
        title=title,
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
    third_result = run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )
    if raw_fields:
        assert third_result
    return item_id


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
):
    return client.patch(
        f"/closet/items/{item_id}",
        headers=headers,
        json={
            "expected_review_version": expected_review_version,
            "changes": changes,
        },
    )


def confirm_review(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
    expected_review_version: str,
):
    return client.post(
        f"/closet/items/{item_id}/confirm",
        headers=headers,
        json={"expected_review_version": expected_review_version},
    )


def confirm_item_with_changes(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
    changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    review = read_review_snapshot(client, headers, item_id=item_id)
    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=review["review_version"],
        changes=changes
        or [
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )
    assert response.status_code == 200
    confirmed = confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=response.json()["review_version"],
    )
    assert confirmed.status_code == 200
    return cast(dict[str, Any], confirmed.json())


def test_browse_and_detail_require_authentication(client: TestClient) -> None:
    list_response = client.get("/closet/items")
    detail_response = client.get(f"/closet/items/{uuid4()}")

    assert list_response.status_code == 401
    assert list_response.json() == {"detail": "Authentication required."}
    assert detail_response.status_code == 401
    assert detail_response.json() == {"detail": "Authentication required."}


def test_confirmed_browse_excludes_unconfirmed_and_archived_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="browse-visible@example.com")
    confirmed_item_id = create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        title="Confirmed tee",
        key_prefix="browse-visible-confirmed",
    )
    confirm_item_with_changes(client, headers, item_id=confirmed_item_id)

    repository = ClosetRepository(db_session)
    lifecycle_service = ClosetLifecycleService(session=db_session, repository=repository)
    archived_item = repository.get_item(item_id=confirmed_item_id)
    assert archived_item is not None
    archived_copy = lifecycle_service.archive_item(
        item_id=archived_item.id,
        user_id=archived_item.user_id,
    )

    second_confirmed_item_id = create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        raw_fields={
            "category": {"value": "outerwear", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "jacket",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        title="Visible jacket",
        key_prefix="browse-visible-second-confirmed",
    )
    confirm_item_with_changes(client, headers, item_id=second_confirmed_item_id)

    hidden_review_item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-hidden-review",
        complete_key="complete-hidden-review",
        title="Hidden review item",
    )

    response = client.get("/closet/items", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [item["item_id"] for item in body["items"]] == [str(second_confirmed_item_id)]
    assert str(hidden_review_item_id) not in {item["item_id"] for item in body["items"]}
    assert str(archived_copy.id) not in {item["item_id"] for item in body["items"]}


def test_browse_never_leaks_unconfirmed_items_for_the_same_user(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "outerwear", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "jacket",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        email="browse-owner@example.com",
        title="Owner jacket",
    )
    confirm_item_with_changes(client, headers, item_id=item_id)
    unconfirmed_item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-owner-hidden",
        complete_key="complete-owner-hidden",
        title="Owner hidden item",
    )

    response = client.get("/closet/items", headers=headers)

    assert response.status_code == 200
    item_ids = {item["item_id"] for item in response.json()["items"]}
    assert str(item_id) in item_ids
    assert str(unconfirmed_item_id) not in item_ids


def test_browse_cursor_pagination_is_stable_for_confirmed_at_ties(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="browse-cursor@example.com")
    confirmed_ids: list[UUID] = []
    for index in range(3):
        item_id = create_normalized_review_item_for_user(
            client,
            db_session,
            fake_storage_client,
            fake_background_removal_provider,
            fake_metadata_extraction_provider,
            headers=headers,
            raw_fields={
                "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
                "subcategory": {
                    "value": "tee shirt",
                    "confidence": 0.97,
                    "applicability_state": "value",
                },
            },
            title=f"Cursor item {index}",
            key_prefix=f"browse-cursor-{index}",
        )
        confirm_item_with_changes(client, headers, item_id=item_id)
        confirmed_ids.append(item_id)

    tied_timestamp = utcnow()
    for item_id in confirmed_ids:
        item = db_session.execute(select(ClosetItem).where(ClosetItem.id == item_id)).scalar_one()
        item.confirmed_at = tied_timestamp
    db_session.commit()

    page_one = client.get("/closet/items?limit=2", headers=headers)
    assert page_one.status_code == 200
    page_one_body = page_one.json()
    assert len(page_one_body["items"]) == 2
    assert page_one_body["next_cursor"] is not None

    page_two = client.get(
        f"/closet/items?limit=2&cursor={page_one_body['next_cursor']}",
        headers=headers,
    )
    assert page_two.status_code == 200
    page_two_body = page_two.json()
    assert len(page_two_body["items"]) == 1
    assert page_two_body["next_cursor"] is None

    first_page_ids = {item["item_id"] for item in page_one_body["items"]}
    second_page_ids = {item["item_id"] for item in page_two_body["items"]}
    assert first_page_ids.isdisjoint(second_page_ids)
    assert first_page_ids | second_page_ids == {str(item_id) for item_id in confirmed_ids}


def test_browse_search_and_filters_use_confirmed_projection_only(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "brand": {"value": "Ghost Brand", "confidence": 0.82, "applicability_state": "value"},
            "colors": {"value": ["blue"], "confidence": 0.8, "applicability_state": "value"},
        },
        email="browse-projection-only@example.com",
        title="Projection only tee",
    )
    confirm_item_with_changes(client, headers, item_id=item_id)

    search_response = client.get("/closet/items?query=ghost", headers=headers)
    color_response = client.get("/closet/items?color=blue", headers=headers)

    assert search_response.status_code == 200
    assert search_response.json()["items"] == []
    assert color_response.status_code == 200
    assert color_response.json()["items"] == []


def test_browse_search_is_case_insensitive_and_combines_with_filters(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="browse-search@example.com")
    jacket_id = create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        raw_fields={
            "category": {"value": "outerwear", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "jacket",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "material": {"value": "suede", "confidence": 0.8, "applicability_state": "value"},
        },
        title="Brown Jacket",
        key_prefix="browse-search-jacket",
    )
    confirm_item_with_changes(
        client,
        headers,
        item_id=jacket_id,
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
            {"field_name": "material", "operation": "accept_suggestion"},
        ],
    )

    tee_id = create_normalized_review_item_for_user(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "material": {"value": "cotton", "confidence": 0.8, "applicability_state": "value"},
        },
        title="Black Tee",
        key_prefix="browse-search-tee",
    )
    confirm_item_with_changes(client, headers, item_id=tee_id)

    response = client.get(
        "/closet/items?query=%20%20JACKET%20%20&category=outerwear&material=suede",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["item_id"] for item in body["items"]] == [str(jacket_id)]


def test_invalid_browse_cursor_and_filters_return_422(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        email="browse-invalids@example.com",
        title="Invalids tee",
    )
    confirm_item_with_changes(client, headers, item_id=item_id)

    invalid_cursor = client.get("/closet/items?cursor=not-a-cursor", headers=headers)
    invalid_subcategory = client.get("/closet/items?subcategory=not-real", headers=headers)
    invalid_pair = client.get(
        "/closet/items?category=shoes&subcategory=t-shirt",
        headers=headers,
    )

    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["detail"] == "Invalid browse cursor."
    assert invalid_subcategory.status_code == 422
    assert invalid_pair.status_code == 422


def test_detail_returns_404_for_other_users_and_unconfirmed_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    owner_headers, confirmed_item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        email="browse-detail-owner@example.com",
        title="Owner detail tee",
    )
    confirm_item_with_changes(client, owner_headers, item_id=confirmed_item_id)

    unconfirmed_item_id = create_uploaded_item(
        client,
        owner_headers,
        fake_storage_client,
        draft_key="detail-unconfirmed-draft",
        complete_key="detail-unconfirmed-complete",
        title="Unconfirmed detail item",
    )
    intruder_headers = register_and_get_headers(client, email="browse-detail-intruder@example.com")

    intruder_response = client.get(f"/closet/items/{confirmed_item_id}", headers=intruder_headers)
    own_unconfirmed_response = client.get(
        f"/closet/items/{unconfirmed_item_id}",
        headers=owner_headers,
    )

    assert intruder_response.status_code == 404
    assert intruder_response.json()["detail"]["code"] == "closet_item_not_found"
    assert own_unconfirmed_response.status_code == 404
    assert own_unconfirmed_response.json()["detail"]["code"] == "closet_item_not_found"


def test_detail_returns_signed_images_and_ordered_field_states(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "colors": {"value": ["black"], "confidence": 0.86, "applicability_state": "value"},
            "brand": {"value": "Tenue", "confidence": 0.84, "applicability_state": "value"},
        },
        email="browse-detail-images@example.com",
        title="Detail image tee",
    )
    confirm_item_with_changes(
        client,
        headers,
        item_id=item_id,
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
            {"field_name": "colors", "operation": "accept_suggestion"},
            {"field_name": "brand", "operation": "accept_suggestion"},
        ],
    )

    response = client.get(f"/closet/items/{item_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["display_image"]["url"].startswith("https://fake-storage.local/download/")
    assert body["thumbnail_image"]["url"].startswith("https://fake-storage.local/download/")
    assert body["original_image"]["url"].startswith("https://fake-storage.local/download/")
    assert body["metadata_projection"]["brand"] == "Tenue"
    field_names = [field["field_name"] for field in body["field_states"]]
    assert field_names.index("category") < field_names.index("subcategory")
    assert field_names.index("subcategory") < field_names.index("colors")
    assert field_names.index("colors") < field_names.index("brand")


def test_detail_includes_all_original_images_for_confirmed_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "top", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "tee shirt",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        email="browse-detail-multi@example.com",
        title="Multi image tee",
    )
    extra_image_bytes = build_image_bytes(color=(220, 220, 220))
    upload_response = create_upload_intent(
        client,
        headers,
        draft_id=str(item_id),
        filename="tee-back.jpg",
        mime_type="image/jpeg",
        file_size=len(extra_image_bytes),
        sha256=sha256_hex(extra_image_bytes),
    )
    assert upload_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_response.json(),
        content=extra_image_bytes,
    )
    complete_response = complete_upload(
        client,
        headers,
        draft_id=str(item_id),
        upload_intent_id=upload_response.json()["upload_intent_id"],
        idempotency_key="detail-multi-extra-complete",
    )
    assert complete_response.status_code == 200
    assert len(complete_response.json()["original_images"]) == 2

    confirm_item_with_changes(
        client,
        headers,
        item_id=item_id,
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )

    response = client.get(f"/closet/items/{item_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["original_images"]) == 2
    assert sum(1 for image in body["original_images"] if image["is_primary"]) == 1
    assert body["original_images"][0]["position"] == 0
    assert body["original_images"][1]["position"] == 1
    assert all(
        image["url"].startswith("https://fake-storage.local/download/")
        for image in body["original_images"]
    )


def test_detail_falls_back_to_original_when_no_processed_asset_exists(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
) -> None:
    headers = register_and_get_headers(client, email="browse-original-fallback@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="fallback-draft",
        complete_key="fallback-complete",
        title="Original only tee",
    )

    repository = ClosetRepository(db_session)
    item = repository.get_item(item_id=item_id)
    assert item is not None
    lifecycle_service = ClosetLifecycleService(session=db_session, repository=repository)
    lifecycle_service.update_processing_state(
        item_id=item.id,
        user_id=item.user_id,
        processing_status=ProcessingStatus.FAILED,
        failure_summary="Manual fallback into review.",
    )
    item = repository.get_item(item_id=item_id)
    assert item is not None
    lifecycle_service.save_field_state(
        item=item,
        field_name="category",
        canonical_value="tops",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
    )
    lifecycle_service.save_field_state(
        item=item,
        field_name="subcategory",
        canonical_value="t-shirt",
        source=FieldSource.USER,
        review_state=FieldReviewState.USER_CONFIRMED,
        applicability_state=ApplicabilityState.VALUE,
    )
    db_session.commit()
    lifecycle_service.confirm_item(item_id=item.id, user_id=item.user_id)

    response = client.get(f"/closet/items/{item_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["display_image"]["asset_id"] == body["original_image"]["asset_id"]
    assert body["thumbnail_image"] is None


def test_confirmed_item_from_existing_review_flow_is_immediately_browsable(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "outerwear", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "jacket",
                "confidence": 0.97,
                "applicability_state": "value",
            },
            "material": {"value": "suede", "confidence": 0.83, "applicability_state": "value"},
        },
        email="browse-regression@example.com",
        title="Regression jacket",
    )
    confirm_item_with_changes(
        client,
        headers,
        item_id=item_id,
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
            {"field_name": "material", "operation": "accept_suggestion"},
        ],
    )

    list_response = client.get("/closet/items?category=outerwear", headers=headers)
    detail_response = client.get(f"/closet/items/{item_id}", headers=headers)

    assert list_response.status_code == 200
    assert [item["item_id"] for item in list_response.json()["items"]] == [str(item_id)]
    assert detail_response.status_code == 200
    assert detail_response.json()["metadata_projection"]["material"] == "suede"


def test_archive_endpoint_hides_item_from_browse_and_history_is_paginated(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={
            "category": {"value": "outerwear", "confidence": 0.98, "applicability_state": "value"},
            "subcategory": {
                "value": "jacket",
                "confidence": 0.97,
                "applicability_state": "value",
            },
        },
        email="browse-archive-history@example.com",
        title="Archive jacket",
    )
    confirm_item_with_changes(
        client,
        headers,
        item_id=item_id,
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )

    archive_response = client.post(f"/closet/items/{item_id}/archive", headers=headers)
    list_response = client.get("/closet/items", headers=headers)
    detail_response = client.get(f"/closet/items/{item_id}", headers=headers)
    history_page_one = client.get(f"/closet/items/{item_id}/history?limit=2", headers=headers)

    assert archive_response.status_code == 204
    assert str(item_id) not in {item["item_id"] for item in list_response.json()["items"]}
    assert detail_response.status_code == 404
    assert history_page_one.status_code == 200
    assert history_page_one.json()["items"][0]["event_type"] == "item_archived"
    assert history_page_one.json()["next_cursor"] is not None

    history_page_two = client.get(
        f"/closet/items/{item_id}/history?limit=2&cursor={history_page_one.json()['next_cursor']}",
        headers=headers,
    )

    assert history_page_two.status_code == 200
    page_one_ids = [event["id"] for event in history_page_one.json()["items"]]
    page_two_ids = [event["id"] for event in history_page_two.json()["items"]]
    assert set(page_one_ids).isdisjoint(page_two_ids)
    assert history_page_two.json()["items"]
