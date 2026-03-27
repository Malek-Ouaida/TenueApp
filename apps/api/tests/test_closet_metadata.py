from fastapi.testclient import TestClient

from app.domains.closet.models import LifecycleStatus, ProcessingStatus, ReviewStatus
from app.domains.closet.taxonomy import (
    CATEGORY_SUBCATEGORIES,
    OCCASION_TAGS,
    REQUIRED_CONFIRMATION_FIELDS,
    SEASON_TAGS,
    STYLE_TAGS,
    TAXONOMY_VERSION,
)


def register_and_get_access_token(client: TestClient) -> str:
    response = client.post(
        "/auth/register",
        json={"email": "closet-user@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    return str(response.json()["session"]["access_token"])


def test_metadata_options_requires_authentication(client: TestClient) -> None:
    response = client.get("/closet/metadata/options")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_metadata_options_returns_expected_contract(client: TestClient) -> None:
    access_token = register_and_get_access_token(client)

    response = client.get(
        "/closet/metadata/options",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["taxonomy_version"] == TAXONOMY_VERSION
    assert body["required_confirmation_fields"] == list(REQUIRED_CONFIRMATION_FIELDS)
    assert body["lifecycle_statuses"] == [status.value for status in LifecycleStatus]
    assert body["processing_statuses"] == [status.value for status in ProcessingStatus]
    assert body["review_statuses"] == [status.value for status in ReviewStatus]
    assert body["style_tags"] == STYLE_TAGS
    assert body["occasion_tags"] == OCCASION_TAGS
    assert body["season_tags"] == SEASON_TAGS


def test_metadata_options_returns_full_category_mapping(client: TestClient) -> None:
    access_token = register_and_get_access_token(client)

    response = client.get(
        "/closet/metadata/options",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    category_map = {entry["name"]: entry["subcategories"] for entry in body["categories"]}
    assert category_map == CATEGORY_SUBCATEGORIES
