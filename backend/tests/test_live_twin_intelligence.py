"""Operational live-twin signals stay server-side and deterministic."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.warehouse import Location
from tests.test_phase3_api import auth_headers, create_inspection


def _state(client: TestClient, inspection_id: int, headers: dict) -> dict:
    response = client.get(
        f"/api/v1/inspections/{inspection_id}/live-state", headers=headers
    )
    assert response.status_code == 200
    return response.json()


def _location(state: dict, code: str) -> dict:
    return next(item for item in state["locations"] if item["code"] == code)


def test_adaptive_queue_prefers_recurrent_location_before_physical_order(
    api_client: TestClient,
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=1)

    state = _state(api_client, inspection["id"], headers)

    # Seeded A-01-02 has the same physical mismatch in two final inspections;
    # A-01-01 is physically earlier but is not recurrent.
    assert state["current_target"] == {
        "action": "CONTINUE_AUTONOMOUS",
        "location_id": _location(state, "A-01-02")["id"],
        "location_code": "A-01-02",
        "reason": "Ubicación con anomalía recurrente.",
        "priority": 1,
    }


def test_live_twin_exposes_excess_expiry_signal_without_changing_risk_score(
    api_client: TestClient,
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=2)

    state = _state(api_client, inspection["id"], headers)
    galak = _location(state, "B-01-03")

    assert galak["loss_prevention_signal"] == "EXCESS_EXPIRY_RISK"
    assert galak["loss_prevention_reason"]
    assert "EXCESO" in galak["badges"]
    assert galak["lot"] == "LOT-008"
    assert galak["days_to_expiry"] is not None
    assert galak["coverage_days"] is not None
    assert galak["coverage_days"] > galak["days_to_expiry"]
    assert galak["rotation"] in {"HIGH", "MEDIUM", "LOW"}
    assert isinstance(galak["fefo_risk"], bool)
    # The planning signal does not fabricate a new central Risk Score.
    assert galak["risk_score"] == 0


def test_slotting_suggestion_requires_high_rotation_and_less_accessible_level(
    api_client: TestClient, test_engine
) -> None:
    with Session(test_engine) as session:
        location = session.query(Location).filter_by(code="A-02-01").one()
        location.level = 2
        session.commit()

    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=1)
    state = _state(api_client, inspection["id"], headers)

    high_rotation = _location(state, "A-02-01")
    assert high_rotation["slotting_suggestion"] == (
        "Producto de alta rotación. Revisar una posición de mayor accesibilidad."
    )
    # A normal position at the same accessibility level has no invented advice.
    assert _location(state, "A-01-01")["slotting_suggestion"] is None


def test_sensor_next_objective_is_the_same_core_target_as_live_state(
    api_client: TestClient,
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=1)
    paired = api_client.post("/api/v1/sensor/register", json={"name": "Dron cola"})
    assert paired.status_code == 201
    sensor_headers = {"X-Sensor-Token": paired.json()["device_token"]}
    assert api_client.get("/api/v1/sensor/mission", headers=sensor_headers).status_code == 200

    target = api_client.get("/api/v1/sensor/mission/next", headers=sensor_headers)
    assert target.status_code == 200
    live_target = _state(api_client, inspection["id"], headers)["current_target"]
    assert target.json() == live_target
