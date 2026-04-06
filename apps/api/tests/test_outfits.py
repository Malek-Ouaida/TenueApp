from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_closet_browse import register_and_get_headers
from test_wear_logs import build_raw_fields, create_confirmed_item, create_wear_log


def create_outfit(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str | None,
    items: list[dict[str, Any]],
    notes: str | None = None,
    occasion: str | None = None,
    season: str | None = None,
    is_favorite: bool = False,
):
    payload: dict[str, Any] = {"items": items, "is_favorite": is_favorite}
    if title is not None:
        payload["title"] = title
    if notes is not None:
        payload["notes"] = notes
    if occasion is not None:
        payload["occasion"] = occasion
    if season is not None:
        payload["season"] = season
    return client.post("/outfits", headers=headers, json=payload)


def test_outfit_routes_require_authentication_with_fixture(client: TestClient) -> None:
    outfit_id = uuid4()

    list_response = client.get("/outfits")
    create_response = client.post(
        "/outfits",
        json={"items": [{"closet_item_id": str(uuid4())}]},
    )
    detail_response = client.get(f"/outfits/{outfit_id}")

    assert list_response.status_code == 401
    assert list_response.json() == {"detail": "Authentication required."}
    assert create_response.status_code == 401
    assert create_response.json() == {"detail": "Authentication required."}
    assert detail_response.status_code == 401
    assert detail_response.json() == {"detail": "Authentication required."}


def test_create_outfit_and_detail_from_confirmed_items(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="outfits-create@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Cream tee",
        key_prefix="outfits-create-top",
    )
    outerwear_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Camel coat",
        key_prefix="outfits-create-outerwear",
        raw_fields=build_raw_fields(category="outerwear", subcategory="coat", color="beige"),
    )

    response = create_outfit(
        client,
        headers,
        title="City layers",
        notes="Weekday staple",
        occasion="work",
        season="winter",
        is_favorite=True,
        items=[
            {
                "closet_item_id": str(outerwear_item_id),
                "role": "outerwear",
                "layer_index": 2,
                "sort_index": 8,
                "is_optional": True,
            },
            {
                "closet_item_id": str(top_item_id),
                "role": "top",
                "layer_index": 0,
                "sort_index": 0,
            },
        ],
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "City layers"
    assert body["notes"] == "Weekday staple"
    assert body["occasion"] == "work"
    assert body["season"] == "winter"
    assert body["source"] == "manual"
    assert body["is_favorite"] is True
    assert body["is_archived"] is False
    assert body["item_count"] == 2
    assert body["cover_image"] is not None
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(top_item_id),
        str(outerwear_item_id),
    ]
    assert body["items"][1]["layer_index"] == 2
    assert body["items"][1]["is_optional"] is True

    detail_response = client.get(f"/outfits/{body['id']}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "City layers"


def test_list_outfits_filters_pagination_and_archive(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="outfits-list@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="List tee",
        key_prefix="outfits-list-item",
    )

    created_ids: list[str] = []
    for title, season, is_favorite in (
        ("Morning fit", "summer", False),
        ("Office fit", "winter", True),
        ("Dinner fit", "winter", False),
    ):
        response = create_outfit(
            client,
            headers,
            title=title,
            season=season,
            is_favorite=is_favorite,
            items=[{"closet_item_id": str(item_id), "role": "top"}],
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    first_page = client.get("/outfits?limit=2", headers=headers)
    assert first_page.status_code == 200
    first_page_body = first_page.json()
    assert [item["title"] for item in first_page_body["items"]] == ["Dinner fit", "Office fit"]
    assert first_page_body["next_cursor"] is not None

    second_page = client.get(
        f"/outfits?limit=2&cursor={first_page_body['next_cursor']}",
        headers=headers,
    )
    assert second_page.status_code == 200
    assert [item["title"] for item in second_page.json()["items"]] == ["Morning fit"]

    favorite_filter = client.get("/outfits?is_favorite=true", headers=headers)
    assert favorite_filter.status_code == 200
    assert [item["title"] for item in favorite_filter.json()["items"]] == ["Office fit"]

    archive_response = client.post(f"/outfits/{created_ids[1]}/archive", headers=headers)
    assert archive_response.status_code == 204

    post_archive_list = client.get("/outfits", headers=headers)
    assert post_archive_list.status_code == 200
    assert [item["title"] for item in post_archive_list.json()["items"]] == [
        "Dinner fit",
        "Morning fit",
    ]

    archived_visible = client.get("/outfits?include_archived=true", headers=headers)
    assert archived_visible.status_code == 200
    archived_item = next(
        item for item in archived_visible.json()["items"] if item["id"] == created_ids[1]
    )
    assert archived_item["is_archived"] is True


def test_update_outfit_replaces_items_and_metadata(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="outfits-update@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Update top",
        key_prefix="outfits-update-top",
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Update bottom",
        key_prefix="outfits-update-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="black"),
    )
    shoes_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Update shoes",
        key_prefix="outfits-update-shoes",
        raw_fields=build_raw_fields(category="shoes", subcategory="sneakers", color="white"),
    )

    create_response = create_outfit(
        client,
        headers,
        title="Before patch",
        items=[{"closet_item_id": str(top_item_id), "role": "top"}],
    )
    assert create_response.status_code == 201
    outfit_id = create_response.json()["id"]

    patch_response = client.patch(
        f"/outfits/{outfit_id}",
        headers=headers,
        json={
            "title": "After patch",
            "notes": "Refined rotation",
            "occasion": "travel",
            "season": "winter",
            "is_favorite": True,
            "items": [
                {
                    "closet_item_id": str(shoes_item_id),
                    "role": "shoes",
                    "layer_index": 4,
                    "sort_index": 5,
                    "is_optional": True,
                },
                {"closet_item_id": str(bottom_item_id), "role": "bottom", "sort_index": 0},
            ],
        },
    )

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["title"] == "After patch"
    assert body["notes"] == "Refined rotation"
    assert body["occasion"] == "travel"
    assert body["season"] == "winter"
    assert body["is_favorite"] is True
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(bottom_item_id),
        str(shoes_item_id),
    ]
    assert body["items"][1]["layer_index"] == 4
    assert body["items"][1]["is_optional"] is True


def test_create_outfit_from_wear_log_and_preserve_source_wear_log(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="outfits-from-wear-log@example.com")
    top_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Wear log top",
        key_prefix="outfits-from-wear-log-top",
    )
    bottom_item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Wear log bottom",
        key_prefix="outfits-from-wear-log-bottom",
        raw_fields=build_raw_fields(category="bottom", subcategory="trousers", color="navy"),
    )

    wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[
            {"closet_item_id": str(top_item_id), "role": "top", "sort_index": 9},
            {"closet_item_id": str(bottom_item_id), "role": "bottom", "sort_index": 0},
        ],
    )
    assert wear_log_response.status_code == 201
    wear_log_id = wear_log_response.json()["id"]

    response = client.post(
        f"/outfits/from-wear-log/{wear_log_id}",
        headers=headers,
        json={"title": "Derived outfit", "occasion": "work", "is_favorite": True},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Derived outfit"
    assert body["source"] == "derived_from_wear_log"
    assert body["occasion"] == "work"
    assert body["is_favorite"] is True
    assert [item["closet_item_id"] for item in body["items"]] == [
        str(bottom_item_id),
        str(top_item_id),
    ]

    wear_log_detail = client.get(f"/wear-logs/{wear_log_id}", headers=headers)
    assert wear_log_detail.status_code == 200
    assert wear_log_detail.json()["source"] == "manual_items"


def test_create_outfit_from_wear_log_rejects_now_archived_closet_item(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="outfits-archived-item@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Archive me",
        key_prefix="outfits-archived-item",
    )

    wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    assert wear_log_response.status_code == 201

    archive_response = client.post(f"/closet/items/{item_id}/archive", headers=headers)
    assert archive_response.status_code == 204

    response = client.post(
        f"/outfits/from-wear-log/{wear_log_response.json()['id']}",
        headers=headers,
        json={"title": "Should fail"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "One or more closet items could not be found for confirmed outfit composition."
    }


def test_archived_outfit_cannot_be_used_for_saved_outfit_wear_logging(
    client: TestClient,
    db_session: Session,
    fake_storage_client: Any,
    fake_background_removal_provider: Any,
    fake_metadata_extraction_provider: Any,
) -> None:
    headers = register_and_get_headers(client, email="outfits-archive-wear@example.com")
    item_id = create_confirmed_item(
        client,
        db_session,
        fake_storage_client,
        fake_background_removal_provider,
        fake_metadata_extraction_provider,
        headers=headers,
        title="Archive outfit item",
        key_prefix="outfits-archive-wear-item",
    )

    outfit_response = create_outfit(
        client,
        headers,
        title="Archive outfit",
        items=[{"closet_item_id": str(item_id), "role": "top"}],
    )
    assert outfit_response.status_code == 201
    outfit_id = outfit_response.json()["id"]

    archive_response = client.post(f"/outfits/{outfit_id}/archive", headers=headers)
    assert archive_response.status_code == 204

    wear_log_response = create_wear_log(
        client,
        headers,
        wear_date="2026-04-06",
        outfit_id=outfit_id,
    )

    assert wear_log_response.status_code == 409
    assert wear_log_response.json() == {
        "detail": "Archived outfits cannot be used for wear logging."
    }
