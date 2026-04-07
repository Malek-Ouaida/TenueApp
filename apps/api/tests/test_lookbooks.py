from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_closet_upload import build_image_bytes, sha256_hex, upload_to_fake_storage
from test_outfits import create_outfit
from test_wear_logs import create_confirmed_item

from app.domains.lookbook.models import Lookbook, LookbookUploadIntent


def create_lookbook(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
    description: str | None = None,
):
    payload: dict[str, Any] = {"title": title}
    if description is not None:
        payload["description"] = description
    return client.post("/lookbooks", headers=headers, json=payload)


def create_lookbook_upload_intent(
    client: TestClient,
    headers: dict[str, str],
    *,
    lookbook_id: UUID | str,
    filename: str = "look.jpg",
    mime_type: str = "image/jpeg",
    file_size: int,
    sha256: str,
):
    return client.post(
        f"/lookbooks/{lookbook_id}/upload-intents",
        headers=headers,
        json={
            "filename": filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "sha256": sha256,
        },
    )


def create_lookbook_entry(
    client: TestClient,
    headers: dict[str, str],
    *,
    lookbook_id: UUID | str,
    payload: dict[str, Any],
):
    return client.post(f"/lookbooks/{lookbook_id}/entries", headers=headers, json=payload)


def test_lookbook_routes_require_authentication_with_fixture(client: TestClient) -> None:
    lookbook_id = uuid4()
    entry_id = uuid4()

    responses = (
        client.get("/lookbooks"),
        client.post("/lookbooks", json={"title": "Weekend"}),
        client.get(f"/lookbooks/{lookbook_id}"),
        client.post(
            f"/lookbooks/{lookbook_id}/upload-intents",
            json={
                "filename": "look.jpg",
                "mime_type": "image/jpeg",
                "file_size": 100,
                "sha256": "a" * 64,
            },
        ),
        client.get(f"/lookbooks/{lookbook_id}/entries"),
        client.post(
            f"/lookbooks/{lookbook_id}/entries", json={"entry_type": "note", "note_text": "Weekend"}
        ),
        client.patch(
            f"/lookbooks/{lookbook_id}/entries/reorder",
            json={"entry_ids": [str(entry_id)]},
        ),
        client.delete(f"/lookbooks/{lookbook_id}/entries/{entry_id}"),
    )

    for response in responses:
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required."}


def test_create_update_list_and_delete_lookbooks(
    client: TestClient,
) -> None:
    headers = register_and_get_headers(client, email="lookbooks-basic@example.com")

    first = create_lookbook(client, headers, title="Weekend Capsule", description="Off-duty looks")
    second = create_lookbook(client, headers, title="Work Uniform")

    assert first.status_code == 201
    assert second.status_code == 201
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    update_response = client.patch(
        f"/lookbooks/{first_id}",
        headers=headers,
        json={"title": "Weekend Rotation", "description": "Edited description"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Weekend Rotation"
    assert update_response.json()["description"] == "Edited description"

    list_response = client.get("/lookbooks?limit=1", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == first_id
    assert list_response.json()["next_cursor"] is not None

    page_two = client.get(
        f"/lookbooks?limit=1&cursor={list_response.json()['next_cursor']}",
        headers=headers,
    )
    assert page_two.status_code == 200
    assert page_two.json()["items"][0]["id"] == second_id

    detail_response = client.get(f"/lookbooks/{first_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["entry_count"] == 0
    assert detail_response.json()["cover_image"] is None

    delete_response = client.delete(f"/lookbooks/{second_id}", headers=headers)
    assert delete_response.status_code == 204
    missing_response = client.get(f"/lookbooks/{second_id}", headers=headers)
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Lookbook not found."}


def test_mixed_entries_support_cover_hydration_and_updated_at_reordering(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbooks-mixed@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Cream knit",
        key_prefix="lookbooks-mixed-item",
    )
    outfit_response = create_outfit(
        client,
        headers,
        title="Soft layers",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
        is_favorite=True,
    )
    assert outfit_response.status_code == 201
    outfit_id = outfit_response.json()["id"]

    archive_outfit_response = client.post(f"/outfits/{outfit_id}/archive", headers=headers)
    assert archive_outfit_response.status_code == 204

    first_lookbook = create_lookbook(client, headers, title="Primary")
    second_lookbook = create_lookbook(client, headers, title="Secondary")
    assert first_lookbook.status_code == 201
    assert second_lookbook.status_code == 201
    first_lookbook_id = first_lookbook.json()["id"]
    second_lookbook_id = second_lookbook.json()["id"]

    outfit_entry = create_lookbook_entry(
        client,
        headers,
        lookbook_id=first_lookbook_id,
        payload={"entry_type": "outfit", "outfit_id": outfit_id, "caption": "Reliable base"},
    )
    assert outfit_entry.status_code == 201
    assert outfit_entry.json()["outfit"]["is_archived"] is True
    assert outfit_entry.json()["outfit"]["cover_image"] is not None

    note_entry = create_lookbook_entry(
        client,
        headers,
        lookbook_id=first_lookbook_id,
        payload={"entry_type": "note", "note_text": "Add silver jewelry."},
    )
    assert note_entry.status_code == 201

    entries_response = client.get(f"/lookbooks/{first_lookbook_id}/entries", headers=headers)
    assert entries_response.status_code == 200
    entries = entries_response.json()["items"]
    assert [entry["entry_type"] for entry in entries] == ["outfit", "note"]
    assert [entry["sort_index"] for entry in entries] == [0, 1]

    detail_response = client.get(f"/lookbooks/{first_lookbook_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["entry_count"] == 2
    assert detail_response.json()["cover_image"] is not None

    reordered_list = client.get("/lookbooks", headers=headers)
    assert reordered_list.status_code == 200
    assert [item["id"] for item in reordered_list.json()["items"]][:2] == [
        first_lookbook_id,
        second_lookbook_id,
    ]


def test_create_image_entry_from_upload_intent_and_prefer_image_cover(
    client: TestClient,
    fake_storage_client: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbooks-image@example.com")
    lookbook_response = create_lookbook(client, headers, title="Mirror Looks")
    assert lookbook_response.status_code == 201
    lookbook_id = lookbook_response.json()["id"]

    image_bytes = build_image_bytes(size=(48, 64))
    upload_intent_response = create_lookbook_upload_intent(
        client,
        headers,
        lookbook_id=lookbook_id,
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert upload_intent_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_intent_response.json(),
        content=image_bytes,
    )

    image_entry_response = create_lookbook_entry(
        client,
        headers,
        lookbook_id=lookbook_id,
        payload={
            "entry_type": "image",
            "upload_intent_id": upload_intent_response.json()["upload_intent_id"],
            "caption": "Mirror test",
        },
    )
    assert image_entry_response.status_code == 201
    body = image_entry_response.json()
    assert body["entry_type"] == "image"
    assert body["image"] is not None
    assert body["caption"] == "Mirror test"
    assert body["image"]["mime_type"] == "image/jpeg"

    detail_response = client.get(f"/lookbooks/{lookbook_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["cover_image"]["asset_id"] == body["image"]["asset_id"]


def test_upload_intent_expiry_and_wrong_lookbook_are_rejected(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
) -> None:
    owner_headers = register_and_get_headers(client, email="lookbooks-expiry-owner@example.com")
    intruder_headers = register_and_get_headers(
        client, email="lookbooks-expiry-intruder@example.com"
    )
    owner_lookbook = create_lookbook(client, owner_headers, title="Owner board")
    other_lookbook = create_lookbook(client, owner_headers, title="Other board")
    intruder_lookbook = create_lookbook(client, intruder_headers, title="Intruder board")
    assert owner_lookbook.status_code == 201
    assert other_lookbook.status_code == 201
    assert intruder_lookbook.status_code == 201

    image_bytes = build_image_bytes()
    upload_intent_response = create_lookbook_upload_intent(
        client,
        owner_headers,
        lookbook_id=owner_lookbook.json()["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert upload_intent_response.status_code == 200
    upload_intent_id = UUID(upload_intent_response.json()["upload_intent_id"])

    upload_intent = db_session.execute(
        select(LookbookUploadIntent).where(LookbookUploadIntent.id == upload_intent_id)
    ).scalar_one()
    upload_intent.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    expired_response = create_lookbook_entry(
        client,
        owner_headers,
        lookbook_id=owner_lookbook.json()["id"],
        payload={"entry_type": "image", "upload_intent_id": str(upload_intent_id)},
    )
    assert expired_response.status_code == 409
    assert expired_response.json() == {"detail": "The upload intent has expired."}

    fresh_intent_response = create_lookbook_upload_intent(
        client,
        owner_headers,
        lookbook_id=owner_lookbook.json()["id"],
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert fresh_intent_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=fresh_intent_response.json(),
        content=image_bytes,
    )

    wrong_lookbook_response = create_lookbook_entry(
        client,
        owner_headers,
        lookbook_id=other_lookbook.json()["id"],
        payload={
            "entry_type": "image",
            "upload_intent_id": fresh_intent_response.json()["upload_intent_id"],
        },
    )
    assert wrong_lookbook_response.status_code == 404
    assert wrong_lookbook_response.json() == {"detail": "Lookbook upload intent not found."}

    intruder_response = create_lookbook_entry(
        client,
        intruder_headers,
        lookbook_id=intruder_lookbook.json()["id"],
        payload={
            "entry_type": "image",
            "upload_intent_id": fresh_intent_response.json()["upload_intent_id"],
        },
    )
    assert intruder_response.status_code == 404
    assert intruder_response.json() == {"detail": "Lookbook upload intent not found."}


def test_reorder_requires_exact_entry_set_and_delete_reindexes(
    client: TestClient,
) -> None:
    headers = register_and_get_headers(client, email="lookbooks-reorder@example.com")
    lookbook_response = create_lookbook(client, headers, title="Reorder board")
    assert lookbook_response.status_code == 201
    lookbook_id = lookbook_response.json()["id"]

    first_entry = create_lookbook_entry(
        client,
        headers,
        lookbook_id=lookbook_id,
        payload={"entry_type": "note", "note_text": "First"},
    )
    second_entry = create_lookbook_entry(
        client,
        headers,
        lookbook_id=lookbook_id,
        payload={"entry_type": "note", "note_text": "Second"},
    )
    third_entry = create_lookbook_entry(
        client,
        headers,
        lookbook_id=lookbook_id,
        payload={"entry_type": "note", "note_text": "Third"},
    )
    assert first_entry.status_code == 201
    assert second_entry.status_code == 201
    assert third_entry.status_code == 201

    invalid_reorder = client.patch(
        f"/lookbooks/{lookbook_id}/entries/reorder",
        headers=headers,
        json={"entry_ids": [first_entry.json()["id"], second_entry.json()["id"]]},
    )
    assert invalid_reorder.status_code == 422
    assert invalid_reorder.json() == {
        "detail": "Reorder requests must include every current lookbook entry exactly once."
    }

    reorder_response = client.patch(
        f"/lookbooks/{lookbook_id}/entries/reorder",
        headers=headers,
        json={
            "entry_ids": [
                third_entry.json()["id"],
                first_entry.json()["id"],
                second_entry.json()["id"],
            ]
        },
    )
    assert reorder_response.status_code == 204

    ordered_entries = client.get(f"/lookbooks/{lookbook_id}/entries", headers=headers)
    assert ordered_entries.status_code == 200
    assert [entry["id"] for entry in ordered_entries.json()["items"]] == [
        third_entry.json()["id"],
        first_entry.json()["id"],
        second_entry.json()["id"],
    ]
    assert [entry["sort_index"] for entry in ordered_entries.json()["items"]] == [0, 1, 2]

    delete_response = client.delete(
        f"/lookbooks/{lookbook_id}/entries/{first_entry.json()['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    after_delete = client.get(f"/lookbooks/{lookbook_id}/entries", headers=headers)
    assert after_delete.status_code == 200
    assert [entry["sort_index"] for entry in after_delete.json()["items"]] == [0, 1]


def test_outfit_entry_rejects_cross_user_outfit(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    owner_headers = register_and_get_headers(client, email="lookbooks-owner@example.com")
    intruder_headers = register_and_get_headers(client, email="lookbooks-intruder@example.com")
    lookbook_response = create_lookbook(client, intruder_headers, title="Intruder board")
    assert lookbook_response.status_code == 201

    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=owner_headers,
        title="Owner item",
        key_prefix="lookbooks-owner-item",
    )
    outfit_response = create_outfit(
        client,
        owner_headers,
        title="Owner outfit",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    assert outfit_response.status_code == 201

    entry_response = create_lookbook_entry(
        client,
        intruder_headers,
        lookbook_id=lookbook_response.json()["id"],
        payload={"entry_type": "outfit", "outfit_id": outfit_response.json()["id"]},
    )
    assert entry_response.status_code == 404
    assert entry_response.json() == {"detail": "Outfit not found."}


def test_delete_lookbook_cascades_entries_and_upload_intents(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = register_and_get_headers(client, email="lookbooks-delete@example.com")
    lookbook_response = create_lookbook(client, headers, title="Cascade board")
    assert lookbook_response.status_code == 201
    lookbook_id = UUID(lookbook_response.json()["id"])

    note_entry = create_lookbook_entry(
        client,
        headers,
        lookbook_id=lookbook_id,
        payload={"entry_type": "note", "note_text": "One"},
    )
    assert note_entry.status_code == 201

    image_bytes = build_image_bytes()
    upload_intent_response = create_lookbook_upload_intent(
        client,
        headers,
        lookbook_id=lookbook_id,
        file_size=len(image_bytes),
        sha256=sha256_hex(image_bytes),
    )
    assert upload_intent_response.status_code == 200

    delete_response = client.delete(f"/lookbooks/{lookbook_id}", headers=headers)
    assert delete_response.status_code == 204

    deleted_lookbook = db_session.execute(
        select(Lookbook).where(Lookbook.id == lookbook_id)
    ).scalar_one_or_none()
    deleted_intent = db_session.execute(select(LookbookUploadIntent)).scalar_one_or_none()
    assert deleted_lookbook is None
    assert deleted_intent is None
