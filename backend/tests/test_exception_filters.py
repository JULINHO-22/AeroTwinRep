from fastapi.testclient import TestClient

from tests.test_phase3_api import login


def _supervisor_headers(client: TestClient) -> dict[str, str]:
    token, _ = login(client, "supervisor01")
    return {"Authorization": f"Bearer {token}"}


def _exceptions(
    client: TestClient, headers: dict[str, str], **params: str | int | bool
) -> dict:
    response = client.get("/api/v1/exceptions", params=params, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_exception_filters_use_seeded_zone_and_type(api_client: TestClient) -> None:
    headers = _supervisor_headers(api_client)

    zone_a = _exceptions(api_client, headers, zone=" a ")
    assert zone_a["total"] == 5
    assert {item["location"] for item in zone_a["items"]} == {
        "A-01-02",
        "A-01-03",
        "A-02-01",
        "A-02-02",
    }
    assert {item["type"] for item in zone_a["items"]} == {
        "PALLET_MISMATCH",
        "LOW_QUALITY",
        "UNEXPECTED_PALLET",
        "HIGH_ROTATION",
        "HISTORICAL_ANOMALY",
    }

    mismatch = _exceptions(api_client, headers, type="pallet_mismatch")
    assert mismatch["total"] == 1
    item = mismatch["items"][0]
    assert item["location"] == "A-01-02"
    assert item["type"] == "PALLET_MISMATCH"
    assert item["severity"] == "MEDIUM"
    assert item["status"] == "OPEN"
    assert item["risk_score"] == 55


def test_exception_filters_resolve_lot_expiry_and_reading_quality(
    api_client: TestClient,
) -> None:
    headers = _supervisor_headers(api_client)

    lot = _exceptions(api_client, headers, lot="lot-008")
    assert lot["total"] == 2
    assert {(item["location"], item["type"]) for item in lot["items"]} == {
        ("A-01-02", "PALLET_MISMATCH"),
        ("B-01-03", "EXPIRING_SOON"),
    }

    expiry = _exceptions(api_client, headers, expiry=True)
    # LOT-008 is inside the 30-day risk horizon and so is the synthetic
    # unexpected PAL-011 / LOT-011 observation at A-02-02.
    assert expiry["total"] == 3
    assert {(item["location"], item["type"]) for item in expiry["items"]} == {
        ("A-01-02", "PALLET_MISMATCH"),
        ("A-02-02", "UNEXPECTED_PALLET"),
        ("B-01-03", "EXPIRING_SOON"),
    }

    low_quality = _exceptions(api_client, headers, quality_max=50)
    assert low_quality["total"] == 1
    assert low_quality["items"][0]["location"] == "A-01-03"
    assert low_quality["items"][0]["type"] == "LOW_QUALITY"

    # ``quality`` is the concise public alias; ``quality_max`` remains useful
    # for clients that want the threshold semantics explicit.
    assert _exceptions(api_client, headers, quality=50) == low_quality


def test_exception_filters_reject_an_unknown_type(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/exceptions",
        params={"type": "not-a-real-exception"},
        headers=_supervisor_headers(api_client),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_EXCEPTION_TYPE"
