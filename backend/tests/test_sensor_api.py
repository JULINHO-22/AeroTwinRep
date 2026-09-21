import json
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image


PASSWORD = "AeroTwin123!"


def _human_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _jpeg() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (20, 20), color=(37, 99, 213)).save(stream, format="JPEG")
    return stream.getvalue()


def test_no_active_inspection_is_a_normal_empty_response(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/inspections/active", headers=_human_headers(api_client, "operator01"))
    assert response.status_code == 200
    assert response.json() is None


def test_sensor_device_pairing_mission_and_camera_reading(api_client: TestClient) -> None:
    paired = api_client.post("/api/v1/sensor/register", json={"name": "Sensor 01"})
    assert paired.status_code == 201
    device = paired.json()
    assert device["device_code"].startswith("SENSOR-")
    sensor_headers = {"X-Sensor-Token": device["device_token"]}

    assert api_client.get("/api/v1/sensor/mission", headers=sensor_headers).json() is None

    supervisor_headers = _human_headers(api_client, "supervisor01")
    inspection = api_client.post("/api/v1/inspections", json={"zone_id": 1}, headers=supervisor_headers)
    assert inspection.status_code == 201
    assigned = api_client.post(
        f"/api/v1/inspections/{inspection.json()['id']}/assign-sensor/{device['id']}",
        headers=supervisor_headers,
    )
    assert assigned.status_code == 200

    mission = api_client.get("/api/v1/sensor/mission", headers=sensor_headers)
    assert mission.status_code == 200
    assert mission.json() == {"inspection_id": inspection.json()["id"], "zone": "A", "status": "IN_PROGRESS"}

    location = api_client.get("/api/v1/sensor/locations/code/A-01-01", headers=sensor_headers)
    assert location.status_code == 200
    payload = {
        "client_reading_id": str(uuid4()),
        "location_id": location.json()["id"],
        "reading_group_id": str(uuid4()),
        "attempt_number": 1,
        "observed_pallet_code": "PAL-001",
        "observed_state": "PALLET",
        "quality_score": 95,
        "source_type": "ANDROID_CAMERA",
        "empty_confirmed_by_operator": False,
    }
    response = api_client.post(
        "/api/v1/sensor/mission/readings",
        data={"payload": json.dumps(payload)},
        files={"evidence": ("sensor.jpg", _jpeg(), "image/jpeg")},
        headers=sensor_headers,
    )
    assert response.status_code == 201
    assert response.json()["comparison_result"] == "CORRECT"

    dashboard = api_client.get("/api/v1/sensors", headers=supervisor_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()[0]["status"] == "ONLINE"
    assert dashboard.json()[0]["last_reading"]["location_code"] == "A-01-01"


def test_sensor_automatically_joins_latest_active_inspection(api_client: TestClient) -> None:
    paired = api_client.post("/api/v1/sensor/register", json={"name": "Dron móvil"}).json()
    sensor_headers = {"X-Sensor-Token": paired["device_token"]}
    supervisor_headers = _human_headers(api_client, "supervisor01")
    inspection = api_client.post("/api/v1/inspections", json={"zone_id": 1}, headers=supervisor_headers).json()

    mission = api_client.get("/api/v1/sensor/mission", headers=sensor_headers)

    assert mission.status_code == 200
    assert mission.json()["inspection_id"] == inspection["id"]
    assert mission.json()["zone"] == "A"


def test_sensor_rejects_human_or_drone_source(api_client: TestClient) -> None:
    paired = api_client.post("/api/v1/sensor/register", json={"name": "Sensor 01"}).json()
    sensor_headers = {"X-Sensor-Token": paired["device_token"]}
    supervisor_headers = _human_headers(api_client, "supervisor01")
    inspection = api_client.post("/api/v1/inspections", json={"zone_id": 1}, headers=supervisor_headers).json()
    api_client.post(f"/api/v1/inspections/{inspection['id']}/assign-sensor/{paired['id']}", headers=supervisor_headers)
    location = api_client.get("/api/v1/sensor/locations/code/A-01-01", headers=sensor_headers).json()
    payload = {
        "client_reading_id": str(uuid4()), "location_id": location["id"], "reading_group_id": str(uuid4()),
        "attempt_number": 1, "observed_pallet_code": "PAL-001", "observed_state": "PALLET",
        "quality_score": 95, "source_type": "DRONE", "empty_confirmed_by_operator": False,
    }
    response = api_client.post("/api/v1/sensor/mission/readings", data={"payload": json.dumps(payload)}, files={"evidence": ("sensor.jpg", _jpeg(), "image/jpeg")}, headers=sensor_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SENSOR_SOURCE_REQUIRED"


def test_operator_can_monitor_only_its_assigned_sensor(api_client: TestClient) -> None:
    paired = api_client.post("/api/v1/sensor/register", json={"name": "Sensor monitor"}).json()
    operator_headers = _human_headers(api_client, "operator01")
    inspection = api_client.post("/api/v1/inspections", json={"zone_id": 1}, headers=operator_headers).json()
    supervisor_headers = _human_headers(api_client, "supervisor01")
    assigned = api_client.post(
        f"/api/v1/inspections/{inspection['id']}/assign-sensor/{paired['id']}",
        headers=supervisor_headers,
    )
    assert assigned.status_code == 200
    monitored = api_client.get("/api/v1/sensors", headers=operator_headers)
    assert monitored.status_code == 200
    assert [item["id"] for item in monitored.json()] == [paired["id"]]
