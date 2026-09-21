from unittest.mock import patch

from app.services.sensor_live import LiveFrames
from tests.test_sensor_api import _human_headers, _jpeg


def test_live_preview_two_devices_isolated_and_independent_of_readings(api_client):
    owner = _human_headers(api_client, "operator01")
    mission = api_client.post("/api/v1/inspections", json={"zone_id": 1}, headers=owner).json()
    devices = [api_client.post("/api/v1/sensor/register", json={"name": name}).json() for name in ("Dron A", "Dron B")]
    for device in devices:
        headers = {"X-Sensor-Token": device["device_token"]}
        assert api_client.get("/api/v1/sensor/mission", headers=headers).json()["inspection_id"] == mission["id"]
        assert api_client.post("/api/v1/sensor/preview", headers=headers, files={"frame": ("live.jpg", _jpeg(), "image/jpeg")}).status_code == 204
        preview = api_client.get(f"/api/v1/sensors/{device['id']}/preview", headers=owner)
        assert preview.status_code == 200
        assert preview.content == _jpeg()
        assert preview.headers["cache-control"] == "no-store"
        assert api_client.get(f"/api/v1/sensors/{device['id']}/preview").status_code == 401
    sensors = api_client.get("/api/v1/sensors", headers=owner).json()
    assert len(sensors) == 2
    assert all(sensor["last_reading"] is None for sensor in sensors)
    assert api_client.post("/api/v1/sensor/preview", files={"frame": ("live.jpg", _jpeg(), "image/jpeg")}).status_code == 401


def test_preview_rejects_invalid_data(api_client):
    owner = _human_headers(api_client, "operator01")
    api_client.post("/api/v1/inspections", json={"zone_id": 1}, headers=owner)
    device = api_client.post("/api/v1/sensor/register", json={"name": "Dron A"}).json()
    headers = {"X-Sensor-Token": device["device_token"]}
    assert api_client.post("/api/v1/sensor/preview", headers=headers, files={"frame": ("live.jpg", b"invalid", "image/jpeg")}).status_code == 422
    assert api_client.post("/api/v1/sensor/preview", headers=headers, files={"frame": ("live.jpg", b"x" * 512001, "image/jpeg")}).status_code == 413


def test_live_frame_expires_and_never_crosses_inspections():
    frames = LiveFrames()
    with patch("app.services.sensor_live.monotonic", return_value=10):
        frames.put(1, 4, b"first")
        frames.put(2, 5, b"second")
        assert frames.get(1, 4) == b"first"
        assert frames.get(1, 5) is None
        assert frames.get(2, 5) == b"second"
    with patch("app.services.sensor_live.monotonic", return_value=16):
        assert frames.get(1, 4) is None
