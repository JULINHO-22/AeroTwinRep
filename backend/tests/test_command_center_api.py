from fastapi.testclient import TestClient

from tests.test_phase3_api import auth_headers


def test_dashboard_is_client_agnostic_and_contains_operational_aggregates(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/dashboard", headers=auth_headers(api_client))
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"inspection", "exceptions", "inventory_risks", "priorities", "sensors"}
    assert {"verified", "total", "coverage_percent"} <= set(payload["inspection"])
    assert {"open", "critical", "human_review"} <= set(payload["exceptions"])


def test_exception_list_is_sorted_and_detail_has_risk_breakdown(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    response = api_client.get("/api/v1/exceptions", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["risk_score"] for item in items] == sorted((item["risk_score"] for item in items), reverse=True)
    if items:
        detail = api_client.get(f"/api/v1/exceptions/{items[0]['id']}", headers=headers)
        assert detail.status_code == 200
        assert isinstance(detail.json()["risk_breakdown"], dict)
