from fastapi.testclient import TestClient


def test_register_returns_user_and_session(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "person@example.com"
    assert body["user"]["auth_provider"] == "supabase"
    assert body["email_verification_required"] is False
    assert body["session"]["token_type"] == "bearer"
    assert body["session"]["access_token"]
    assert body["session"]["refresh_token"]


def test_register_can_require_email_verification(
    client: TestClient,
    fake_auth_provider,
) -> None:
    fake_auth_provider.require_email_verification_on_signup = True

    response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "person@example.com"
    assert body["email_verification_required"] is True
    assert body["session"] is None


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_login_reuses_existing_user(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )
    first_user_id = register_response.json()["user"]["id"]

    response = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == first_user_id


def test_login_preflight_allows_local_expo_web_origin(client: TestClient) -> None:
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_me_returns_current_user(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )
    access_token = register_response.json()["session"]["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "person@example.com"


def test_refresh_rotates_session_tokens(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )
    refresh_token = register_response.json()["session"]["refresh_token"]
    original_access_token = register_response.json()["session"]["access_token"]

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    assert response.json()["session"]["access_token"] != original_access_token


def test_logout_invalidates_the_current_session(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )
    access_token = register_response.json()["session"]["access_token"]

    logout_response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert logout_response.status_code == 200
    assert logout_response.json() == {"success": True}
    assert me_response.status_code == 401


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "wrong-pass-123"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid login credentials."}
