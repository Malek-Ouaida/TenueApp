from fastapi.testclient import TestClient


def register_user(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    session = body["session"]
    assert isinstance(session, dict)
    access_token = session["access_token"]
    assert isinstance(access_token, str)
    return access_token


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_get_my_profile_returns_default_identity_fields(client: TestClient) -> None:
    access_token = register_user(client, "person@example.com")

    response = client.get("/profiles/me", headers=auth_headers(access_token))

    assert response.status_code == 200
    assert response.json()["profile"]["username"] is None
    assert response.json()["profile"]["display_name"] is None
    assert response.json()["profile"]["bio"] is None
    assert response.json()["profile"]["avatar_url"] is None


def test_patch_my_profile_updates_identity_fields(client: TestClient) -> None:
    access_token = register_user(client, "person@example.com")

    response = client.patch(
        "/profiles/me",
        headers=auth_headers(access_token),
        json={
            "username": "Style.Edit",
            "display_name": "Malek Ouaida",
            "bio": "Curating a smarter closet.",
            "avatar_path": "profiles/avatar-123.png",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["username"] == "style.edit"
    assert body["profile"]["display_name"] == "Malek Ouaida"
    assert body["profile"]["bio"] == "Curating a smarter closet."
    assert body["profile"]["avatar_url"] == "profiles/avatar-123.png"

    by_username_response = client.get(
        "/profiles/style.edit",
        headers=auth_headers(access_token),
    )

    assert by_username_response.status_code == 200
    assert by_username_response.json()["profile"]["username"] == "style.edit"


def test_patch_my_profile_rejects_reserved_username(client: TestClient) -> None:
    access_token = register_user(client, "person@example.com")

    response = client.patch(
        "/profiles/me",
        headers=auth_headers(access_token),
        json={"username": "me"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "That username is reserved."}


def test_patch_my_profile_rejects_duplicate_username(client: TestClient) -> None:
    first_access_token = register_user(client, "first@example.com")
    second_access_token = register_user(client, "second@example.com")

    first_response = client.patch(
        "/profiles/me",
        headers=auth_headers(first_access_token),
        json={"username": "closet.coded"},
    )
    assert first_response.status_code == 200

    second_response = client.patch(
        "/profiles/me",
        headers=auth_headers(second_access_token),
        json={"username": "closet.coded"},
    )

    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Username is already taken."}


def test_profile_by_username_requires_authentication(client: TestClient) -> None:
    access_token = register_user(client, "person@example.com")
    client.patch(
        "/profiles/me",
        headers=auth_headers(access_token),
        json={"username": "closet.coded"},
    )

    response = client.get("/profiles/closet.coded")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_patch_my_profile_clears_nullable_fields(client: TestClient) -> None:
    access_token = register_user(client, "person@example.com")
    seeded_response = client.patch(
        "/profiles/me",
        headers=auth_headers(access_token),
        json={
            "username": "closet.coded",
            "display_name": "Malek Ouaida",
            "bio": "Closet-first identity.",
            "avatar_path": "profiles/avatar-123.png",
        },
    )
    assert seeded_response.status_code == 200

    response = client.patch(
        "/profiles/me",
        headers=auth_headers(access_token),
        json={
            "username": "",
            "display_name": " ",
            "bio": "",
            "avatar_path": " ",
        },
    )

    assert response.status_code == 200
    assert response.json()["profile"]["username"] is None
    assert response.json()["profile"]["display_name"] is None
    assert response.json()["profile"]["bio"] is None
    assert response.json()["profile"]["avatar_url"] is None
