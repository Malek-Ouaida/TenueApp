from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok_and_sets_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}
    assert response.headers["X-Request-ID"]


def test_health_ready_reports_closet_dependencies(client: TestClient) -> None:
    response = client.get("/health/ready", headers={"X-Request-ID": "health-ready-test"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    dependency_by_name = {dependency["name"]: dependency for dependency in body["dependencies"]}
    assert dependency_by_name["database"]["status"] == "ok"
    assert dependency_by_name["database_schema"]["status"] == "skipped"
    assert dependency_by_name["database_schema"]["critical"] is False
    assert dependency_by_name["object_storage"]["status"] == "ok"
    assert dependency_by_name["background_removal_provider"]["critical"] is False
    assert response.headers["X-Request-ID"] == "health-ready-test"
