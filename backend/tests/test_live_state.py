from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services.sensor_live import live_telemetry
from tests.test_phase3_api import (
    auth_headers,
    create_inspection,
    lookup_location,
    reading_payload,
    submit_reading,
)


def _live_state(
    client: TestClient, inspection_id: int, headers: dict[str, str]
) -> dict:
    response = client.get(
        f"/api/v1/inspections/{inspection_id}/live-state", headers=headers
    )
    assert response.status_code == 200
    return response.json()


def _location_by_code(payload: dict, code: str) -> dict:
    return next(location for location in payload["locations"] if location["code"] == code)


def _assert_progress(
    payload: dict,
    *,
    inspected: int,
    validated: int,
    review_required: int,
) -> None:
    assert payload["total"] == 6
    assert payload["inspected"] == inspected
    assert payload["validated"] == validated
    assert payload["review_required"] == review_required
    assert payload["pending"] == 6 - inspected
    assert payload["coverage_percent"] == pytest.approx(round(inspected / 6 * 100, 1))


def _clear_live_telemetry() -> None:
    # The demo telemetry store is intentionally in-memory.  Database IDs reset
    # between integration tests, so isolate this test from a recent prior mission.
    with live_telemetry.lock:
        live_telemetry.items.clear()


@pytest.fixture(autouse=True)
def _isolated_live_telemetry():
    _clear_live_telemetry()
    yield
    _clear_live_telemetry()


def test_live_state_starts_with_an_uninspected_twin(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)

    state = _live_state(api_client, inspection["id"], headers)

    assert set(state) == {
        "inspection_id",
        "zone",
        "total",
        "inspected",
        "validated",
        "review_required",
        "pending",
        "coverage_percent",
        "last_final_reading",
        "current_target",
        "locations",
    }
    assert state["inspection_id"] == inspection["id"]
    assert state["zone"] == "A"
    _assert_progress(state, inspected=0, validated=0, review_required=0)
    assert state["last_final_reading"] is None
    assert len(state["locations"]) == 6
    assert {location["physical_state"] for location in state["locations"]} == {
        "UNINSPECTED"
    }
    target = state["current_target"]
    assert isinstance(target["action"], str) and target["action"]
    assert isinstance(target["reason"], str) and target["reason"]
    assert isinstance(target["priority"], int)
    assert target["location_code"] in {location["code"] for location in state["locations"]}


def test_live_state_counts_final_readings_and_projects_physical_results(
    api_client: TestClient,
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    locations = {
        code: lookup_location(api_client, headers, code)
        for code in (
            "A-01-01",
            "A-01-02",
            "A-01-03",
            "A-02-01",
            "A-02-02",
            "A-02-03",
        )
    }

    first = submit_reading(
        api_client,
        inspection["id"],
        headers,
        reading_payload(location_id=locations["A-01-01"]["id"], pallet="PAL-001"),
    )
    assert first.status_code == 201
    assert first.json()["reading_status"] == "ACCEPTED"
    state = _live_state(api_client, inspection["id"], headers)
    _assert_progress(state, inspected=1, validated=1, review_required=0)
    assert _location_by_code(state, "A-01-01")["physical_state"] == "CORRECT"
    assert state["last_final_reading"]["id"] == first.json()["id"]

    review_group = uuid4()
    rescan = submit_reading(
        api_client,
        inspection["id"],
        headers,
        reading_payload(
            location_id=locations["A-01-02"]["id"],
            quality=40,
            group_id=review_group,
            attempt=1,
        ),
    )
    assert rescan.status_code == 201
    assert rescan.json()["reading_status"] == "RESCAN_REQUIRED"
    assert rescan.json()["is_final"] is False
    state = _live_state(api_client, inspection["id"], headers)
    _assert_progress(state, inspected=1, validated=1, review_required=0)
    # A retry for a location takes precedence over a fresh queue target.
    assert state["current_target"]["location_code"] == "A-01-02"

    human_review = submit_reading(
        api_client,
        inspection["id"],
        headers,
        reading_payload(
            location_id=locations["A-01-02"]["id"],
            quality=40,
            group_id=review_group,
            attempt=2,
        ),
    )
    assert human_review.status_code == 201
    assert human_review.json()["reading_status"] == "HUMAN_REVIEW_REQUIRED"
    assert human_review.json()["is_final"] is True
    state = _live_state(api_client, inspection["id"], headers)
    _assert_progress(state, inspected=2, validated=1, review_required=1)
    assert _location_by_code(state, "A-01-02")["physical_state"] == "REVIEW_REQUIRED"
    assert state["last_final_reading"]["id"] == human_review.json()["id"]

    mismatch = submit_reading(
        api_client,
        inspection["id"],
        headers,
        reading_payload(location_id=locations["A-01-03"]["id"], pallet="PAL-008"),
    )
    assert mismatch.status_code == 201
    assert mismatch.json()["comparison_result"] == "PALLET_MISMATCH"
    state = _live_state(api_client, inspection["id"], headers)
    _assert_progress(state, inspected=3, validated=2, review_required=1)
    mismatch_location = _location_by_code(state, "A-01-03")
    assert mismatch_location["physical_state"] == "DISCREPANCY"
    assert mismatch_location["expected_pallet_code"] == "PAL-003"
    assert mismatch_location["observed_pallet_code"] == "PAL-008"

    remaining_readings = (
        ("A-02-01", "PAL-004", 4, 3, 1, "CORRECT"),
        ("A-02-02", "PAL-011", 5, 4, 1, "DISCREPANCY"),
        ("A-02-03", "PAL-005", 6, 5, 1, "CORRECT"),
    )
    for code, pallet, inspected, validated, review_required, physical_state in remaining_readings:
        reading = submit_reading(
            api_client,
            inspection["id"],
            headers,
            reading_payload(location_id=locations[code]["id"], pallet=pallet),
        )
        assert reading.status_code == 201
        assert reading.json()["reading_status"] == "ACCEPTED"
        state = _live_state(api_client, inspection["id"], headers)
        _assert_progress(
            state,
            inspected=inspected,
            validated=validated,
            review_required=review_required,
        )
        assert _location_by_code(state, code)["physical_state"] == physical_state


def test_live_state_marks_sensor_telemetry_as_scanning_then_uses_final_result(
    api_client: TestClient,
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    device = api_client.post(
        "/api/v1/sensor/register", json={"name": "Sensor de estado vivo"}
    )
    assert device.status_code == 201
    sensor_headers = {"X-Sensor-Token": device.json()["device_token"]}
    mission = api_client.get("/api/v1/sensor/mission", headers=sensor_headers)
    assert mission.status_code == 200
    assert mission.json()["inspection_id"] == inspection["id"]
    telemetry = api_client.post(
        "/api/v1/sensor/telemetry",
        json={
            "message": "Ubicación detectada; analizando pallet",
            "detected_code": "LOC:A-01-01",
        },
        headers=sensor_headers,
    )
    assert telemetry.status_code == 204

    state = _live_state(api_client, inspection["id"], headers)
    _assert_progress(state, inspected=0, validated=0, review_required=0)
    assert _location_by_code(state, "A-01-01")["physical_state"] == "SCANNING"

    location = lookup_location(api_client, headers, "A-01-01")
    final = submit_reading(
        api_client,
        inspection["id"],
        headers,
        reading_payload(location_id=location["id"], pallet="PAL-001"),
    )
    assert final.status_code == 201

    state = _live_state(api_client, inspection["id"], headers)
    _assert_progress(state, inspected=1, validated=1, review_required=0)
    # Persisted final evidence wins over short-lived candidate telemetry.
    assert _location_by_code(state, "A-01-01")["physical_state"] == "CORRECT"
