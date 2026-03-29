from __future__ import annotations

from io import BytesIO
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import InMemoryStorageClient
from app.domains.closet.metadata_extraction import METADATA_EXTRACTION_TASK_TYPE
from app.domains.closet.models import (
    ApplicabilityState,
    ClosetItemAuditEvent,
    ClosetItemFieldState,
    ProcessingRunType,
    ProcessingStatus,
    ProviderResultStatus,
    utcnow,
)
from app.domains.closet.repository import ClosetRepository
from app.domains.closet.taxonomy import SUPPORTED_FIELD_ORDER
from app.domains.closet.worker import ClosetWorker
from app.domains.closet.worker_runner import build_worker_handlers


def register_and_get_headers(
    client: TestClient,
    *,
    email: str = "closet-review@example.com",
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


def field_state_map(db_session: Session, *, item_id: UUID) -> dict[str, ClosetItemFieldState]:
    return {
        field_state.field_name: field_state
        for field_state in db_session.execute(
            select(ClosetItemFieldState).where(ClosetItemFieldState.closet_item_id == item_id)
        ).scalars()
    }


def audit_events_for_item(db_session: Session, *, item_id: UUID) -> list[ClosetItemAuditEvent]:
    return list(
        db_session.execute(
            select(ClosetItemAuditEvent).where(ClosetItemAuditEvent.closet_item_id == item_id)
        ).scalars()
    )


def review_field(body: dict[str, Any], field_name: str) -> dict[str, Any]:
    return next(field for field in body["review_fields"] if field["field_name"] == field_name)


def create_normalized_review_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    raw_fields: dict[str, Any],
    email: str,
) -> tuple[dict[str, str], UUID]:
    fake_background_removal_provider.succeed(
        image_bytes=build_image_bytes(
            size=(80, 96),
            color=(255, 255, 255, 0),
            image_format="PNG",
            mode="RGBA",
        )
    )
    fake_metadata_extraction_provider.succeed(raw_fields=raw_fields)
    headers = register_and_get_headers(client, email=email)
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key=f"draft-{email}",
        complete_key=f"complete-{email}",
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
    return headers, item_id


def read_review_snapshot(
    client: TestClient,
    headers: dict[str, str],
    *,
    item_id: UUID,
) -> dict[str, Any]:
    response = client.get(f"/closet/items/{item_id}/review", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    return cast(dict[str, Any], payload)


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


def test_review_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/closet/items/{uuid4()}/review")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_review_endpoint_is_user_scoped(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    _, item_id = create_normalized_review_item(
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
        email="review-owner@example.com",
    )
    intruder_headers = register_and_get_headers(client, email="review-intruder@example.com")

    response = client.get(f"/closet/items/{item_id}/review", headers=intruder_headers)

    assert response.status_code == 404


def test_review_snapshot_merges_current_and_suggested_state_in_stable_order(
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
            "colors": {
                "value": ["grey", "navy blue"],
                "confidence": 0.85,
                "applicability_state": "value",
            },
            "brand": {"value": "Other Brand", "confidence": 0.3, "applicability_state": "value"},
        },
        email="review-merged@example.com",
    )

    body = read_review_snapshot(client, headers, item_id=item_id)

    assert [field["field_name"] for field in body["review_fields"]] == list(SUPPORTED_FIELD_ORDER)
    category_field = review_field(body, "category")
    colors_field = review_field(body, "colors")
    brand_field = review_field(body, "brand")

    assert category_field["current_state"]["review_state"] == "pending_user"
    assert category_field["suggested_state"]["canonical_value"] == "tops"
    assert category_field["suggested_state"]["is_derived"] is False
    assert colors_field["suggested_state"]["canonical_value"] == ["gray", "navy"]
    assert brand_field["suggested_state"]["canonical_value"] == "Other Brand"
    assert body["current_candidate_set"]["provider_result_id"] is not None


def test_patch_keeps_ai_suggestion_visible_and_bumps_review_version(
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
            "brand": {"value": "Other Brand", "confidence": 0.25, "applicability_state": "value"},
        },
        email="review-edit-visible@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {
                "field_name": "brand",
                "operation": "set_value",
                "canonical_value": "User Brand",
            }
        ],
    )

    assert response.status_code == 200
    body = response.json()
    brand_field = review_field(body, "brand")
    assert body["review_version"] != before["review_version"]
    assert brand_field["current_state"]["source"] == "user"
    assert brand_field["current_state"]["review_state"] == "user_edited"
    assert brand_field["current_state"]["canonical_value"] == "User Brand"
    assert brand_field["suggested_state"]["canonical_value"] == "Other Brand"

    event_types = [event.event_type for event in audit_events_for_item(db_session, item_id=item_id)]
    assert "field_state_user_edited" in event_types


def test_stale_review_version_rejects_patch_and_confirm(
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
            "brand": {"value": "Provider Brand", "confidence": 0.4, "applicability_state": "value"},
        },
        email="review-stale-version@example.com",
    )
    first = read_review_snapshot(client, headers, item_id=item_id)

    accepted = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=first["review_version"],
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
        ],
    )
    assert accepted.status_code == 200

    stale_patch = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=first["review_version"],
        changes=[
            {
                "field_name": "brand",
                "operation": "set_value",
                "canonical_value": "User Brand",
            }
        ],
    )
    assert stale_patch.status_code == 409
    assert stale_patch.json()["detail"]["code"] == "stale_review_version"

    second = accepted.json()
    fresh = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=second["review_version"],
        changes=[
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )
    assert fresh.status_code == 200

    stale_confirm = confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=second["review_version"],
    )
    assert stale_confirm.status_code == 409
    assert stale_confirm.json()["detail"]["code"] == "stale_review_version"


@pytest.mark.parametrize(
    ("field_name", "provider_payload", "expected_applicability", "expected_value"),
    [
        (
            "brand",
            {"value": "Acme", "confidence": 0.7, "applicability_state": "value"},
            "value",
            "Acme",
        ),
        (
            "material",
            {"value": None, "confidence": 0.4, "applicability_state": "unknown"},
            "unknown",
            None,
        ),
        (
            "pattern",
            {"value": None, "confidence": 0.5, "applicability_state": "not_applicable"},
            "not_applicable",
            None,
        ),
    ],
)
def test_accept_suggestion_supports_value_unknown_and_not_applicable(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
    *,
    field_name: str,
    provider_payload: dict[str, Any],
    expected_applicability: str,
    expected_value: Any,
) -> None:
    headers, item_id = create_normalized_review_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        raw_fields={field_name: provider_payload},
        email=f"review-accept-{field_name}@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[{"field_name": field_name, "operation": "accept_suggestion"}],
    )

    assert response.status_code == 200
    state = field_state_map(db_session, item_id=item_id)[field_name]
    assert state.source.value == "user"
    assert state.review_state.value == "user_confirmed"
    assert state.applicability_state.value == expected_applicability
    assert state.canonical_value == expected_value


def test_clear_and_mark_not_applicable_mutations_materialize_user_states(
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
            "brand": {"value": "Provider Brand", "confidence": 0.4, "applicability_state": "value"},
            "occasion_tags": {
                "value": ["office"],
                "confidence": 0.6,
                "applicability_state": "value",
            },
        },
        email="review-clear-na@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {"field_name": "brand", "operation": "clear"},
            {"field_name": "occasion_tags", "operation": "mark_not_applicable"},
        ],
    )

    assert response.status_code == 200
    states = field_state_map(db_session, item_id=item_id)
    assert states["brand"].review_state.value == "user_edited"
    assert states["brand"].applicability_state.value == "unknown"
    assert states["brand"].canonical_value is None
    assert states["occasion_tags"].applicability_state.value == "not_applicable"
    assert states["occasion_tags"].canonical_value is None


def test_subcategory_only_patch_auto_aligns_category(
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
        email="review-auto-align@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {
                "field_name": "subcategory",
                "operation": "set_value",
                "canonical_value": "boots",
            }
        ],
    )

    assert response.status_code == 200
    states = field_state_map(db_session, item_id=item_id)
    assert states["subcategory"].canonical_value == "boots"
    assert states["category"].canonical_value == "shoes"
    assert states["category"].review_state.value == "user_edited"


def test_conflicting_category_and_subcategory_patch_is_rejected(
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
        raw_fields={},
        email="review-conflict@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {
                "field_name": "category",
                "operation": "set_value",
                "canonical_value": "tops",
            },
            {
                "field_name": "subcategory",
                "operation": "set_value",
                "canonical_value": "boots",
            },
        ],
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_review_mutation"


def test_duplicate_field_changes_are_rejected(
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
        raw_fields={},
        email="review-duplicate-fields@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {
                "field_name": "brand",
                "operation": "set_value",
                "canonical_value": "One",
            },
            {
                "field_name": "brand",
                "operation": "clear",
            },
        ],
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_review_mutation"


def test_confirm_requires_user_truth_and_keeps_optional_provider_values_out_of_projection(
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
            "brand": {"value": "Provider Brand", "confidence": 0.3, "applicability_state": "value"},
        },
        email="review-confirm@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)

    blocked = confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "missing_required_confirmation_fields"

    accepted = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )
    assert accepted.status_code == 200

    confirmed = confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=accepted.json()["review_version"],
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["lifecycle_status"] == "confirmed"
    assert body["review_status"] == "confirmed"

    projection = ClosetRepository(db_session).get_metadata_projection(item_id=item_id)
    assert projection is not None
    assert projection.category == "tops"
    assert projection.subcategory == "t-shirt"
    assert projection.brand is None


def test_retry_defaults_to_image_processing_when_processing_failed(
    client: TestClient,
    db_session: Session,
    fake_storage_client: InMemoryStorageClient,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="review-retry-processing@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-review-retry-processing",
        complete_key="complete-review-retry-processing",
    )
    repository = ClosetRepository(db_session)
    item = repository.get_item(item_id=item_id)
    assert item is not None
    primary_record = repository.get_primary_image_asset(item=item)
    assert primary_record is not None
    _, primary_asset = primary_record
    fake_storage_client.delete_object(
        bucket=primary_asset.bucket,
        key=primary_asset.key,
    )
    assert run_worker_once(
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
    )

    response = client.post(f"/closet/items/{item_id}/retry", headers=headers, json={})

    assert response.status_code == 202
    body = response.json()
    assert body["processing_status"] == "pending"
    assert body["lifecycle_status"] == "processing"
    assert body["retry_action"]["can_retry"] is False

    event_types = [event.event_type for event in audit_events_for_item(db_session, item_id=item_id)]
    assert "item_retry_requested" in event_types


def test_retry_defaults_to_metadata_extraction_when_extraction_failed(
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
    fake_metadata_extraction_provider.fail()
    headers = register_and_get_headers(client, email="review-retry-extraction@example.com")
    item_id = create_uploaded_item(
        client,
        headers,
        fake_storage_client,
        draft_key="draft-review-retry-extraction",
        complete_key="complete-review-retry-extraction",
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

    response = client.post(f"/closet/items/{item_id}/retry", headers=headers, json={})

    assert response.status_code == 202
    assert response.json()["extraction_status"] == "pending"


def test_retry_defaults_to_normalization_when_latest_run_failed(
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
        email="review-retry-normalization-failed@example.com",
    )
    repository = ClosetRepository(db_session)
    repository.create_processing_run(
        closet_item_id=item_id,
        run_type=ProcessingRunType.NORMALIZATION_PROJECTION,
        status=ProcessingStatus.FAILED,
        retry_count=1,
        started_at=utcnow(),
        completed_at=utcnow(),
        failure_code="seeded_failure",
        failure_payload={"reason": "seeded"},
    )
    db_session.commit()

    response = client.post(f"/closet/items/{item_id}/retry", headers=headers, json={})

    assert response.status_code == 202
    assert response.json()["normalization_status"] == "pending"


def test_retry_defaults_to_normalization_when_field_states_are_stale(
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
        email="review-retry-normalization-stale@example.com",
    )
    repository = ClosetRepository(db_session)
    provider_result = repository.create_provider_result(
        closet_item_id=item_id,
        processing_run_id=None,
        provider_name="fake_metadata_extraction",
        provider_model=None,
        provider_version="test",
        task_type=METADATA_EXTRACTION_TASK_TYPE,
        status=ProviderResultStatus.SUCCEEDED,
        raw_payload={"message": "new extraction"},
    )
    repository.create_field_candidate(
        closet_item_id=item_id,
        field_name="category",
        raw_value="shoe",
        normalized_candidate=None,
        confidence=0.9,
        provider_result_id=provider_result.id,
        applicability_state=ApplicabilityState.VALUE,
        conflict_notes=None,
    )
    repository.create_field_candidate(
        closet_item_id=item_id,
        field_name="subcategory",
        raw_value="boots",
        normalized_candidate=None,
        confidence=0.88,
        provider_result_id=provider_result.id,
        applicability_state=ApplicabilityState.VALUE,
        conflict_notes=None,
    )
    db_session.commit()

    before = read_review_snapshot(client, headers, item_id=item_id)
    assert before["field_states_stale"] is True
    assert before["retry_action"]["default_step"] == "normalization_projection"

    response = client.post(f"/closet/items/{item_id}/retry", headers=headers, json={})

    assert response.status_code == 202
    assert response.json()["normalization_status"] == "pending"


def test_retry_rejects_when_no_actionable_step_exists(
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
        email="review-retry-none@example.com",
    )

    response = client.post(f"/closet/items/{item_id}/retry", headers=headers, json={})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "retry_not_available"


def test_confirmed_items_can_be_read_but_not_mutated_through_review_actions(
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
        email="review-confirmed-readable@example.com",
    )
    before = read_review_snapshot(client, headers, item_id=item_id)
    accepted = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=before["review_version"],
        changes=[
            {"field_name": "category", "operation": "accept_suggestion"},
            {"field_name": "subcategory", "operation": "accept_suggestion"},
        ],
    )
    assert accepted.status_code == 200
    confirmed = confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=accepted.json()["review_version"],
    )
    assert confirmed.status_code == 200

    readable = client.get(f"/closet/items/{item_id}/review", headers=headers)
    assert readable.status_code == 200
    assert readable.json()["lifecycle_status"] == "confirmed"

    patch_response = patch_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=readable.json()["review_version"],
        changes=[
            {
                "field_name": "brand",
                "operation": "set_value",
                "canonical_value": "After Confirm",
            }
        ],
    )
    retry_response = client.post(f"/closet/items/{item_id}/retry", headers=headers, json={})
    confirm_response = confirm_review(
        client,
        headers,
        item_id=item_id,
        expected_review_version=readable.json()["review_version"],
    )

    assert patch_response.status_code == 409
    assert retry_response.status_code == 409
    assert confirm_response.status_code == 409
    assert patch_response.json()["detail"]["code"] == "invalid_lifecycle_transition"
