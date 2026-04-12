from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_closet_confirmed_edit_and_media import create_confirmed_item
from test_closet_upload import build_image_bytes, sha256_hex, upload_to_fake_storage
from test_wear_logs import create_wear_log

from app.domains.lookbook.models import (
    Lookbook,
    LookbookEntry,
    LookbookEntryIntent,
    LookbookEntrySourceKind,
    LookbookEntryStatus,
    LookbookEntryType,
)
from app.domains.wear.models import WearLog


def create_lookbook_upload_intent(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str = "look.jpg",
    mime_type: str = "image/jpeg",
    file_size: int,
    sha256: str,
):
    return client.post(
        "/lookbook/uploads/intents",
        headers=headers,
        json={
            "filename": filename,
            "mime_type": mime_type,
            "file_size": file_size,
            "sha256": sha256,
        },
    )


def complete_lookbook_upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    upload_intent_id: UUID | str,
):
    return client.post(
        "/lookbook/uploads/complete",
        headers=headers,
        json={"upload_intent_id": str(upload_intent_id)},
    )


def upload_lookbook_image(
    client: TestClient,
    headers: dict[str, str],
    fake_storage_client: Any,
    *,
    filename: str = "look.jpg",
    image_bytes: bytes | None = None,
) -> dict[str, Any]:
    content = image_bytes or build_image_bytes(size=(48, 64))
    upload_intent_response = create_lookbook_upload_intent(
        client,
        headers,
        filename=filename,
        file_size=len(content),
        sha256=sha256_hex(content),
    )
    assert upload_intent_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=upload_intent_response.json(),
        content=content,
    )
    complete_response = complete_lookbook_upload(
        client,
        headers,
        upload_intent_id=upload_intent_response.json()["upload_intent_id"],
    )
    assert complete_response.status_code == 200
    return complete_response.json()


def create_gallery_entry(
    client: TestClient,
    headers: dict[str, str],
    *,
    primary_image_asset_id: UUID | str,
    intent: str = "inspiration",
    status: str = "draft",
    title: str | None = None,
    caption: str | None = None,
    notes: str | None = None,
    occasion_tag: str | None = None,
    season_tag: str | None = None,
    style_tag: str | None = None,
    linked_items: list[dict[str, Any]] | None = None,
):
    payload: dict[str, Any] = {
        "source_kind": "gallery_photo",
        "intent": intent,
        "status": status,
        "primary_image_asset_id": str(primary_image_asset_id),
        "linked_items": linked_items or [],
    }
    if title is not None:
        payload["title"] = title
    if caption is not None:
        payload["caption"] = caption
    if notes is not None:
        payload["notes"] = notes
    if occasion_tag is not None:
        payload["occasion_tag"] = occasion_tag
    if season_tag is not None:
        payload["season_tag"] = season_tag
    if style_tag is not None:
        payload["style_tag"] = style_tag
    return client.post("/lookbook/entries", headers=headers, json=payload)


def create_wear_log_entry(
    client: TestClient,
    headers: dict[str, str],
    *,
    source_wear_log_id: UUID | str,
    status: str = "draft",
    title: str | None = None,
    caption: str | None = None,
    notes: str | None = None,
    occasion_tag: str | None = None,
    season_tag: str | None = None,
    style_tag: str | None = None,
):
    payload: dict[str, Any] = {
        "source_kind": "wear_log",
        "source_wear_log_id": str(source_wear_log_id),
        "status": status,
    }
    if title is not None:
        payload["title"] = title
    if caption is not None:
        payload["caption"] = caption
    if notes is not None:
        payload["notes"] = notes
    if occasion_tag is not None:
        payload["occasion_tag"] = occasion_tag
    if season_tag is not None:
        payload["season_tag"] = season_tag
    if style_tag is not None:
        payload["style_tag"] = style_tag
    return client.post("/lookbook/entries", headers=headers, json=payload)


def test_lookbook_routes_require_authentication_with_fixture(client: TestClient) -> None:
    entry_id = uuid4()

    responses = (
        client.get("/lookbook/entries"),
        client.post(
            "/lookbook/uploads/intents",
            json={
                "filename": "look.jpg",
                "mime_type": "image/jpeg",
                "file_size": 100,
                "sha256": "a" * 64,
            },
        ),
        client.post("/lookbook/uploads/complete", json={"upload_intent_id": str(uuid4())}),
        client.post(
            "/lookbook/entries",
            json={
                "source_kind": "gallery_photo",
                "intent": "inspiration",
                "status": "draft",
                "primary_image_asset_id": str(uuid4()),
            },
        ),
        client.get(f"/lookbook/entries/{entry_id}"),
        client.patch(f"/lookbook/entries/{entry_id}", json={"title": "Updated"}),
        client.post(f"/lookbook/entries/{entry_id}/archive"),
        client.delete(f"/lookbook/entries/{entry_id}"),
        client.post(f"/lookbook/entries/{entry_id}/wear", json={}),
    )

    for response in responses:
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required."}


def test_create_gallery_entries_and_filter_single_feed(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-gallery@example.com")
    linked_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Ivory tee",
        key_prefix="lookbook-gallery-item",
    )
    published_asset = upload_lookbook_image(client, headers, fake_storage_client)
    draft_asset = upload_lookbook_image(
        client,
        headers,
        fake_storage_client,
        filename="draft.jpg",
        image_bytes=build_image_bytes(size=(64, 80), color=(180, 160, 150)),
    )

    published_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=published_asset["asset_id"],
        intent="inspiration",
        status="published",
        title="Coffee run",
        caption="Easy uniform.",
        notes="Good proportions for spring.",
        occasion_tag="work",
        season_tag="spring",
        style_tag="classic",
        linked_items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    draft_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=draft_asset["asset_id"],
        intent="recreate",
        status="draft",
        caption="Need to rebuild this look later.",
    )

    assert published_response.status_code == 201
    assert draft_response.status_code == 201

    published_body = published_response.json()
    assert published_body["source_kind"] == "gallery_photo"
    assert published_body["intent"] == "inspiration"
    assert published_body["status"] == "published"
    assert published_body["primary_image"]["asset_id"] == published_asset["asset_id"]
    assert published_body["linked_item_count"] == 1
    assert published_body["has_linked_items"] is True
    assert published_body["owned_outfit"] is not None
    assert published_body["linked_items"][0]["closet_item_id"] == str(linked_item_id)

    default_lookbooks = db_session.execute(
        select(Lookbook).where(Lookbook.is_default.is_(True))
    ).scalars().all()
    assert len(default_lookbooks) == 1

    list_response = client.get("/lookbook/entries?limit=10", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 2

    filtered_response = client.get(
        "/lookbook/entries?status=published&intent=inspiration&source_kind=gallery_photo&has_linked_items=true",
        headers=headers,
    )
    assert filtered_response.status_code == 200
    filtered_items = filtered_response.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["id"] == published_body["id"]

    detail_response = client.get(f"/lookbook/entries/{published_body['id']}", headers=headers)
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["title"] == "Coffee run"
    assert detail_body["occasion_tag"] == "work"
    assert detail_body["season_tag"] == "spring"
    assert detail_body["style_tag"] == "classic"
    assert detail_body["source_snapshot"] is None


def test_create_wear_log_entry_snapshots_source_and_survives_source_changes(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-wear-source@example.com")
    linked_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Slate tee",
        key_prefix="lookbook-wear-source-item",
    )
    wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-09",
        context="work",
        notes="Original wear log note.",
        items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    assert wear_log_response.status_code == 201
    wear_log_id = wear_log_response.json()["id"]

    create_response = create_wear_log_entry(
        client,
        headers,
        source_wear_log_id=wear_log_id,
        status="published",
        title="Office keeper",
        caption="Save this combination.",
        notes="Published from a daily log.",
        occasion_tag="work",
        season_tag="fall",
        style_tag="polished",
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["source_kind"] == "wear_log"
    assert body["intent"] == "logged"
    assert body["status"] == "published"
    assert body["source_wear_log_id"] == wear_log_id
    assert body["owned_outfit"] is not None
    assert body["source_snapshot"]["wear_log_id"] == wear_log_id
    assert body["source_snapshot"]["notes"] == "Original wear log note."
    assert body["source_snapshot"]["item_count"] == 1

    duplicate_response = create_wear_log_entry(
        client,
        headers,
        source_wear_log_id=wear_log_id,
        status="draft",
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "This daily log is already saved to the lookbook."
    }

    update_wear_log_response = client.patch(
        f"/wear-logs/{wear_log_id}",
        headers=headers,
        json={"notes": "Changed later on the wear log."},
    )
    assert update_wear_log_response.status_code == 200

    detail_after_update = client.get(f"/lookbook/entries/{body['id']}", headers=headers)
    assert detail_after_update.status_code == 200
    assert detail_after_update.json()["source_snapshot"]["notes"] == "Original wear log note."

    delete_wear_log_response = client.delete(f"/wear-logs/{wear_log_id}", headers=headers)
    assert delete_wear_log_response.status_code == 204

    detail_after_delete = client.get(f"/lookbook/entries/{body['id']}", headers=headers)
    assert detail_after_delete.status_code == 200
    assert detail_after_delete.json()["source_snapshot"]["wear_log_id"] == wear_log_id
    assert detail_after_delete.json()["source_snapshot"]["notes"] == "Original wear log note."


def test_update_gallery_entry_can_replace_photo_and_manage_linked_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-update@example.com")
    first_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Navy shirt",
        key_prefix="lookbook-update-first",
    )
    second_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Stone trousers",
        key_prefix="lookbook-update-second",
    )
    first_asset = upload_lookbook_image(client, headers, fake_storage_client)
    replacement_asset = upload_lookbook_image(
        client,
        headers,
        fake_storage_client,
        filename="replacement.jpg",
        image_bytes=build_image_bytes(size=(72, 96), color=(120, 120, 140)),
    )

    create_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=first_asset["asset_id"],
        intent="recreate",
        status="draft",
        caption="Start as a loose idea.",
    )
    assert create_response.status_code == 201
    entry_id = create_response.json()["id"]

    update_response = client.patch(
        f"/lookbook/entries/{entry_id}",
        headers=headers,
        json={
            "title": "Client dinner",
            "caption": "Sharper version.",
            "notes": "Swap sneakers for loafers if needed.",
            "occasion_tag": "work",
            "season_tag": "fall",
            "style_tag": "minimal",
            "status": "published",
            "primary_image_asset_id": replacement_asset["asset_id"],
            "linked_items": [
                {"closet_item_id": str(first_item_id), "role": "top", "sort_index": 2},
                {"closet_item_id": str(second_item_id), "role": "bottom", "sort_index": 0},
            ],
        },
    )

    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["title"] == "Client dinner"
    assert update_body["status"] == "published"
    assert update_body["published_at"] is not None
    assert update_body["primary_image"]["asset_id"] == replacement_asset["asset_id"]
    assert update_body["linked_item_count"] == 2
    assert [item["closet_item_id"] for item in update_body["linked_items"]] == [
        str(second_item_id),
        str(first_item_id),
    ]

    clear_items_response = client.patch(
        f"/lookbook/entries/{entry_id}",
        headers=headers,
        json={"linked_items": []},
    )
    assert clear_items_response.status_code == 200
    clear_body = clear_items_response.json()
    assert clear_body["owned_outfit"] is None
    assert clear_body["linked_item_count"] == 0
    assert clear_body["has_linked_items"] is False
    assert clear_body["linked_items"] == []


def test_create_wear_log_from_entry_and_archive_delete_entry(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-loop@example.com")
    linked_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Loop tee",
        key_prefix="lookbook-loop-item",
    )
    asset = upload_lookbook_image(client, headers, fake_storage_client)
    create_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=asset["asset_id"],
        intent="inspiration",
        status="published",
        title="Loop look",
        caption="Should feed back into wear logs.",
        style_tag="casual",
        linked_items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    assert create_response.status_code == 201
    entry_body = create_response.json()
    entry_id = entry_body["id"]

    create_wear_response = client.post(
        f"/lookbook/entries/{entry_id}/wear",
        headers=headers,
        json={
            "wear_date": "2026-04-10",
            "context": "casual",
            "notes": "Looped back into wear logging.",
        },
    )
    assert create_wear_response.status_code == 201
    wear_body = create_wear_response.json()
    assert wear_body["source"] == "saved_outfit"
    assert wear_body["notes"] == "Looped back into wear logging."
    assert wear_body["linked_outfit"]["id"] == entry_body["owned_outfit"]["id"]

    archive_response = client.post(f"/lookbook/entries/{entry_id}/archive", headers=headers)
    assert archive_response.status_code == 204

    active_list_response = client.get("/lookbook/entries", headers=headers)
    assert active_list_response.status_code == 200
    assert active_list_response.json()["items"] == []

    archived_list_response = client.get("/lookbook/entries?include_archived=true", headers=headers)
    assert archived_list_response.status_code == 200
    archived_items = archived_list_response.json()["items"]
    assert len(archived_items) == 1
    assert archived_items[0]["id"] == entry_id
    assert archived_items[0]["archived_at"] is not None

    archived_wear_response = client.post(
        f"/lookbook/entries/{entry_id}/wear",
        headers=headers,
        json={"wear_date": "2026-04-11"},
    )
    assert archived_wear_response.status_code == 409
    assert archived_wear_response.json() == {
        "detail": "Archived lookbook entries cannot start a wear log."
    }

    delete_response = client.delete(f"/lookbook/entries/{entry_id}", headers=headers)
    assert delete_response.status_code == 204

    missing_response = client.get(f"/lookbook/entries/{entry_id}", headers=headers)
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Lookbook entry not found."}


def test_lookbook_creation_enforces_asset_and_wear_log_ownership(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    owner_headers = register_and_get_headers(client, email="lookbook-owner@example.com")
    intruder_headers = register_and_get_headers(client, email="lookbook-intruder@example.com")

    owner_asset = upload_lookbook_image(client, owner_headers, fake_storage_client)
    gallery_response = create_gallery_entry(
        client,
        intruder_headers,
        primary_image_asset_id=owner_asset["asset_id"],
        intent="inspiration",
        status="draft",
    )
    assert gallery_response.status_code == 404
    assert gallery_response.json() == {"detail": "Lookbook image asset not found."}

    linked_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=owner_headers,
        title="Owner item",
        key_prefix="lookbook-owner-item",
    )
    wear_log_response = create_wear_log(
        client,
        owner_headers,
        wear_date="2026-04-09",
        items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    assert wear_log_response.status_code == 201

    wear_log_entry_response = create_wear_log_entry(
        client,
        intruder_headers,
        source_wear_log_id=wear_log_response.json()["id"],
        status="draft",
    )
    assert wear_log_entry_response.status_code == 404
    assert wear_log_entry_response.json() == {"detail": "Wear log not found."}


def test_published_entries_require_titles_and_preserve_published_timestamp_on_edit(
    client: TestClient,
    fake_storage_client: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-publish-rules@example.com")
    asset = upload_lookbook_image(client, headers, fake_storage_client)

    untitled_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=asset["asset_id"],
        intent="inspiration",
        status="published",
    )
    assert untitled_response.status_code == 422
    assert untitled_response.json() == {
        "detail": "A published lookbook entry requires a title."
    }

    create_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=asset["asset_id"],
        intent="inspiration",
        status="published",
        title="Weekend formula",
        caption="Initial caption.",
    )
    assert create_response.status_code == 201
    created_body = create_response.json()

    repeated_publish_response = client.patch(
        f"/lookbook/entries/{created_body['id']}",
        headers=headers,
        json={
            "caption": "Refined caption.",
            "status": "published",
        },
    )
    assert repeated_publish_response.status_code == 200
    repeated_publish_body = repeated_publish_response.json()
    assert repeated_publish_body["published_at"] == created_body["published_at"]
    assert repeated_publish_body["caption"] == "Refined caption."

    noop_response = client.patch(
        f"/lookbook/entries/{created_body['id']}",
        headers=headers,
        json={},
    )
    assert noop_response.status_code == 200
    assert noop_response.json()["updated_at"] == repeated_publish_body["updated_at"]
    assert noop_response.json()["published_at"] == repeated_publish_body["published_at"]


def test_lookbook_upload_completion_rejects_checksum_mismatches_and_repeat_finalize(
    client: TestClient,
    fake_storage_client: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-upload-edge@example.com")
    content = build_image_bytes(size=(64, 64), color=(72, 92, 122))

    checksum_response = create_lookbook_upload_intent(
        client,
        headers,
        filename="bad-checksum.jpg",
        file_size=len(content),
        sha256="0" * 64,
    )
    assert checksum_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=checksum_response.json(),
        content=content,
    )
    checksum_complete_response = complete_lookbook_upload(
        client,
        headers,
        upload_intent_id=checksum_response.json()["upload_intent_id"],
    )
    assert checksum_complete_response.status_code == 409
    assert checksum_complete_response.json() == {
        "detail": "The uploaded checksum did not match the declared upload."
    }

    success_response = create_lookbook_upload_intent(
        client,
        headers,
        filename="good.jpg",
        file_size=len(content),
        sha256=sha256_hex(content),
    )
    assert success_response.status_code == 200
    upload_to_fake_storage(
        fake_storage_client,
        upload_response=success_response.json(),
        content=content,
    )
    first_complete = complete_lookbook_upload(
        client,
        headers,
        upload_intent_id=success_response.json()["upload_intent_id"],
    )
    assert first_complete.status_code == 200

    second_complete = complete_lookbook_upload(
        client,
        headers,
        upload_intent_id=success_response.json()["upload_intent_id"],
    )
    assert second_complete.status_code == 409
    assert second_complete.json() == {
        "detail": "The upload intent has already been finalized."
    }


def test_invalid_linked_closet_items_are_rejected_cleanly(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    owner_headers = register_and_get_headers(client, email="lookbook-linked-owner@example.com")
    intruder_headers = register_and_get_headers(client, email="lookbook-linked-intruder@example.com")

    owner_asset = upload_lookbook_image(client, owner_headers, fake_storage_client)
    owner_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=owner_headers,
        title="Owner item",
        key_prefix="lookbook-linked-owner",
    )
    intruder_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=intruder_headers,
        title="Intruder item",
        key_prefix="lookbook-linked-intruder",
    )

    intruder_link_response = create_gallery_entry(
        client,
        owner_headers,
        primary_image_asset_id=owner_asset["asset_id"],
        intent="inspiration",
        status="draft",
        linked_items=[{"closet_item_id": str(intruder_item_id), "role": "top"}],
    )
    assert intruder_link_response.status_code == 404
    assert intruder_link_response.json() == {
        "detail": "One or more linked closet items could not be found."
    }

    duplicate_link_response = create_gallery_entry(
        client,
        owner_headers,
        primary_image_asset_id=owner_asset["asset_id"],
        intent="inspiration",
        status="draft",
        linked_items=[
            {"closet_item_id": str(owner_item_id), "role": "top"},
            {"closet_item_id": str(owner_item_id), "role": "bottom"},
        ],
    )
    assert duplicate_link_response.status_code == 422
    assert duplicate_link_response.json() == {
        "detail": "A closet item can appear only once in a lookbook entry."
    }


def test_single_feed_routes_ignore_non_default_lookbook_entries(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-legacy-nondefault@example.com")
    asset = upload_lookbook_image(client, headers, fake_storage_client)
    user_id = db_session.execute(
        select(Lookbook.user_id).where(Lookbook.is_default.is_(True))
    ).scalar_one()

    legacy_lookbook = Lookbook(
        user_id=user_id,
        title="Legacy board",
        description=None,
        is_default=False,
    )
    db_session.add(legacy_lookbook)
    db_session.flush()

    legacy_entry = LookbookEntry(
        lookbook_id=legacy_lookbook.id,
        entry_type=LookbookEntryType.IMAGE,
        outfit_id=None,
        image_asset_id=UUID(asset["asset_id"]),
        caption="Legacy entry",
        note_text=None,
        sort_index=0,
        source_kind=LookbookEntrySourceKind.GALLERY_PHOTO,
        intent=LookbookEntryIntent.INSPIRATION,
        status=LookbookEntryStatus.PUBLISHED,
        title="Legacy entry",
        notes=None,
        occasion_tag=None,
        season_tag=None,
        style_tag=None,
        source_wear_log_id=None,
        owned_outfit_id=None,
        source_snapshot_json=None,
        published_at=datetime.now(UTC),
        archived_at=None,
    )
    db_session.add(legacy_entry)
    db_session.commit()

    list_response = client.get("/lookbook/entries", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []

    detail_response = client.get(f"/lookbook/entries/{legacy_entry.id}", headers=headers)
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": "Lookbook entry not found."}


def test_archived_wear_logs_cannot_be_saved_and_deleted_entries_leave_source_logs_intact(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-wear-archive@example.com")
    linked_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Archive blocker item",
        key_prefix="lookbook-wear-archive-item",
    )
    archived_wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-08",
        items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    assert archived_wear_log_response.status_code == 201
    archived_wear_log_id = UUID(archived_wear_log_response.json()["id"])
    archived_wear_log = db_session.get(WearLog, archived_wear_log_id)
    assert archived_wear_log is not None
    archived_wear_log.archived_at = datetime.now(UTC)
    db_session.commit()

    archived_create_response = create_wear_log_entry(
        client,
        headers,
        source_wear_log_id=archived_wear_log_id,
        status="draft",
    )
    assert archived_create_response.status_code == 409
    assert archived_create_response.json() == {
        "detail": "Archived daily logs cannot be saved to the lookbook."
    }

    active_wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-09",
        items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    assert active_wear_log_response.status_code == 201
    active_wear_log_id = active_wear_log_response.json()["id"]

    entry_response = create_wear_log_entry(
        client,
        headers,
        source_wear_log_id=active_wear_log_id,
        status="draft",
        title="Delete safe look",
    )
    assert entry_response.status_code == 201

    delete_response = client.delete(
        f"/lookbook/entries/{entry_response.json()['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    wear_log_detail_response = client.get(f"/wear-logs/{active_wear_log_id}", headers=headers)
    assert wear_log_detail_response.status_code == 200
    assert wear_log_detail_response.json()["id"] == active_wear_log_id


def test_archived_wear_log_entry_can_be_saved_again_after_archiving_previous_entry(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-resave-after-archive@example.com")
    linked_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Re-save item",
        key_prefix="lookbook-resave-item",
    )
    wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-09",
        items=[{"closet_item_id": str(linked_item_id), "role": "top"}],
    )
    assert wear_log_response.status_code == 201
    wear_log_id = wear_log_response.json()["id"]

    first_entry_response = create_wear_log_entry(
        client,
        headers,
        source_wear_log_id=wear_log_id,
        status="draft",
        title="First save",
    )
    assert first_entry_response.status_code == 201

    archive_response = client.post(
        f"/lookbook/entries/{first_entry_response.json()['id']}/archive",
        headers=headers,
    )
    assert archive_response.status_code == 204

    second_entry_response = create_wear_log_entry(
        client,
        headers,
        source_wear_log_id=wear_log_id,
        status="draft",
        title="Second save",
    )
    assert second_entry_response.status_code == 201
    assert second_entry_response.json()["id"] != first_entry_response.json()["id"]


def test_list_and_detail_contracts_stay_aligned(
    client: TestClient,
    fake_storage_client: Any,
) -> None:
    headers = register_and_get_headers(client, email="lookbook-contracts@example.com")
    asset = upload_lookbook_image(client, headers, fake_storage_client)
    create_response = create_gallery_entry(
        client,
        headers,
        primary_image_asset_id=asset["asset_id"],
        intent="inspiration",
        status="draft",
        title="Contract look",
        caption="Contract caption",
    )
    assert create_response.status_code == 201
    entry_id = create_response.json()["id"]

    list_response = client.get("/lookbook/entries?limit=1", headers=headers)
    assert list_response.status_code == 200
    detail_response = client.get(f"/lookbook/entries/{entry_id}", headers=headers)
    assert detail_response.status_code == 200

    list_item = list_response.json()["items"][0]
    detail_item = detail_response.json()

    assert set(list_item.keys()) == set(detail_item.keys()) - {"linked_items"}


def test_invalid_lookbook_filters_return_422(client: TestClient) -> None:
    headers = register_and_get_headers(client, email="lookbook-invalid-filter@example.com")

    response = client.get("/lookbook/entries?style_tag=not-a-real-style", headers=headers)

    assert response.status_code == 422
    assert "style_tag must be one of" in response.json()["detail"]
