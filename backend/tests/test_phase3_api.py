import json
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from PIL import Image

from app.models.enums import ComparisonResult, InspectionStatus, ReadingStatus
from app.models.inspection import EvidenceFile, Inspection, InspectionReading


DEMO_PASSWORD = "AeroTwin123!"


def login(client: TestClient, username: str = "operator01") -> tuple[str, dict]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"], response.json()["user"]


def auth_headers(client: TestClient) -> dict[str, str]:
    token, _ = login(client)
    return {"Authorization": f"Bearer {token}"}


def create_inspection(client: TestClient, headers: dict[str, str], zone_id: int = 1) -> dict:
    response = client.post(
        "/api/v1/inspections", json={"zone_id": zone_id}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def lookup_location(client: TestClient, headers: dict[str, str], code: str) -> dict:
    response = client.get(f"/api/v1/locations/code/{code}", headers=headers)
    assert response.status_code == 200
    return response.json()


def reading_payload(
    *,
    location_id: int,
    pallet: str | None = "PAL-001",
    quality: int = 95,
    group_id=None,
    attempt: int = 1,
    client_id=None,
) -> dict:
    return {
        "client_reading_id": str(client_id or uuid4()),
        "location_id": location_id,
        "reading_group_id": str(group_id or uuid4()),
        "attempt_number": attempt,
        "observed_pallet_code": pallet,
        "observed_state": "PALLET",
        "quality_score": quality,
        "source_type": "MANUAL_DEMO",
        "empty_confirmed_by_operator": False,
    }


def evidence_jpeg() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (8, 6), color=(37, 99, 213)).save(stream, format="JPEG")
    return stream.getvalue()


def submit_reading(client: TestClient, inspection_id: int, headers: dict[str, str], payload: dict, evidence: bytes | None = None):
    files = {"evidence": ("evidence.jpg", evidence if evidence is not None else evidence_jpeg(), "image/jpeg")}
    return client.post(
        f"/api/v1/inspections/{inspection_id}/readings",
        data={"payload": json.dumps(payload)},
        files=files,
        headers=headers,
    )


def test_login_correct_returns_operator_token(api_client: TestClient) -> None:
    token, user = login(api_client)
    assert token
    assert user == {
        "id": 1,
        "username": "operator01",
        "full_name": "Operador Demo",
        "role": "OPERATOR",
    }


def test_login_incorrect_uses_structured_401(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/auth/login",
        json={"username": "operator01", "password": "incorrecta"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_accepts_valid_token(api_client: TestClient) -> None:
    token, _ = login(api_client)
    response = api_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "operator01"


def test_me_rejects_invalid_token(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_validation_errors_use_structured_contract(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/inspections",
        json={"zone_id": 0},
        headers=auth_headers(api_client),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_and_get_active_inspection(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    created = create_inspection(api_client, headers)
    active = api_client.get("/api/v1/inspections/active", headers=headers)
    assert active.status_code == 200
    assert active.json() == created
    assert created["zone_code"] == "A"
    assert created["total_locations"] == 6
    assert created["completed_locations"] == 0


def test_create_inspection_rejects_invalid_zone(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/inspections",
        json={"zone_id": 9999},
        headers=auth_headers(api_client),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ZONE_NOT_FOUND"


def test_location_lookup_does_not_reveal_expected_pallet(api_client: TestClient) -> None:
    location = lookup_location(api_client, auth_headers(api_client), "a-01-01")
    assert location["code"] == "A-01-01"
    assert "expected_pallet" not in location
    assert "expected_pallet_code" not in location


def test_correct_reading_is_persisted_with_expected_snapshot(
    api_client: TestClient, test_engine
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"]))
    assert response.status_code == 201
    body = response.json()
    assert body["comparison_result"] == ComparisonResult.CORRECT
    assert body["reading_status"] == ReadingStatus.ACCEPTED
    assert body["expected_pallet_code"] == "PAL-001"
    assert body["is_final"] is True
    with Session(test_engine) as session:
        stored = session.get(InspectionReading, body["id"])
        assert stored is not None
        assert stored.expected_pallet_id_at_inspection is not None


def test_mismatch_returns_initial_risk(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-02")
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"], pallet="PAL-008"))
    assert response.status_code == 201
    body = response.json()
    assert body["comparison_result"] == "PALLET_MISMATCH"
    assert body["risk_score"] == min(sum(body["risk_breakdown"].values()), 100)
    assert body["risk_breakdown"]["PALLET_MISMATCH"] == 35
    assert body["severity"] in {"MEDIUM", "HIGH", "CRITICAL"}


def test_low_quality_first_attempt_requires_rescan_without_comparison(
    api_client: TestClient,
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=2)
    location = lookup_location(api_client, headers, "B-01-01")
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"], pallet="PAL-008", quality=42))
    body = response.json()
    assert response.status_code == 201
    assert body["reading_status"] == "RESCAN_REQUIRED"
    assert body["comparison_result"] == "UNRESOLVED"
    assert body["is_final"] is False
    assert body["risk_score"] == 0


def test_high_quality_second_attempt_is_accepted(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=2)
    location = lookup_location(api_client, headers, "B-01-01")
    group_id = uuid4()
    first = reading_payload(
        location_id=location["id"], pallet="PAL-006", quality=42, group_id=group_id
    )
    second = reading_payload(
        location_id=location["id"],
        pallet="PAL-006",
        quality=94,
        group_id=group_id,
        attempt=2,
    )
    submit_reading(api_client, inspection["id"], headers, first)
    response = submit_reading(api_client, inspection["id"], headers, second)
    assert response.status_code == 201
    assert response.json()["reading_status"] == "ACCEPTED"
    assert response.json()["comparison_result"] == "CORRECT"
    assert response.json()["is_final"] is True


def test_exhausted_low_quality_requires_human_review(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    group_id = uuid4()
    for attempt in (1, 2):
        response = submit_reading(api_client, inspection["id"], headers, reading_payload(
            location_id=location["id"], quality=40, group_id=group_id, attempt=attempt,
        ))
    body = response.json()
    assert body["reading_status"] == "HUMAN_REVIEW_REQUIRED"
    assert body["comparison_result"] == "UNRESOLVED"
    assert body["is_final"] is True
    assert body["risk_breakdown"] == {"LOW_QUALITY": 10}


def test_supervisor_review_exposes_every_attempt_and_is_the_only_empty_confirmation(api_client: TestClient) -> None:
    operator_headers = auth_headers(api_client)
    inspection = create_inspection(api_client, operator_headers)
    location = lookup_location(api_client, operator_headers, "A-01-01")
    group_id = uuid4()
    for attempt in (1, 2):
        response = submit_reading(api_client, inspection["id"], operator_headers, reading_payload(
            location_id=location["id"], quality=40, group_id=group_id, attempt=attempt,
        ))
    assert response.json()["reading_status"] == "HUMAN_REVIEW_REQUIRED"

    operator_confirm = api_client.post(
        f"/api/v1/inspections/{inspection['id']}/review-exceptions/confirm-empty",
        json={"reading_group_id": str(group_id)}, headers=operator_headers,
    )
    assert operator_confirm.status_code == 403

    supervisor_token, _ = login(api_client, "supervisor01")
    supervisor_headers = {"Authorization": f"Bearer {supervisor_token}"}
    exceptions = api_client.get(
        f"/api/v1/inspections/{inspection['id']}/review-exceptions", headers=supervisor_headers,
    )
    assert exceptions.status_code == 200
    assert exceptions.json()[0]["reading_group_id"] == str(group_id)
    assert [item["attempt_number"] for item in exceptions.json()[0]["evidence_attempts"]] == [1, 2]

    confirmed = api_client.post(
        f"/api/v1/inspections/{inspection['id']}/review-exceptions/confirm-empty",
        json={"reading_group_id": str(group_id)}, headers=supervisor_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["observed_state"] == "EMPTY"


def test_client_reading_id_is_idempotent(api_client: TestClient, test_engine) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    payload = reading_payload(location_id=location["id"])
    first = submit_reading(api_client, inspection["id"], headers, payload)
    second = submit_reading(api_client, inspection["id"], headers, payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["idempotent"] is True
    with Session(test_engine) as session:
        count = session.scalar(
            select(func.count()).select_from(InspectionReading).where(
                InspectionReading.client_reading_id == payload["client_reading_id"]
            )
        )
        assert count == 1
        evidence_count = session.scalar(
            select(func.count()).select_from(EvidenceFile).where(
                EvidenceFile.reading_id == first.json()["id"]
            )
        )
        assert evidence_count == 1


def test_invalid_pallet_is_rejected(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"], pallet="PAL-999"))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PALLET_NOT_FOUND"


def test_location_from_wrong_zone_is_rejected(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=1)
    location = lookup_location(api_client, headers, "B-01-01")
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"], pallet="PAL-006"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LOCATION_OUTSIDE_INSPECTION_ZONE"


def test_completed_inspection_rejects_reading(api_client: TestClient, test_engine) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    with Session(test_engine) as session:
        stored = session.get(Inspection, inspection["id"])
        assert stored is not None
        stored.status = InspectionStatus.COMPLETED
        session.commit()
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"]))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSPECTION_NOT_IN_PROGRESS"


def test_e2e_login_create_lookup_submit_and_verify_progress(
    api_client: TestClient, test_engine
) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    reading = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"]))
    progress = api_client.get(
        f"/api/v1/inspections/{inspection['id']}", headers=headers
    )
    assert reading.status_code == 201
    assert progress.status_code == 200
    assert progress.json()["completed_locations"] == 1
    with Session(test_engine) as session:
        stored = session.get(InspectionReading, reading.json()["id"])
        assert stored is not None
        assert stored.comparison_result is ComparisonResult.CORRECT


def test_reading_persists_evidence_metadata_and_serves_it(api_client: TestClient, test_engine) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    response = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"]))
    assert response.status_code == 201
    evidence = response.json()["evidence"]
    assert evidence["mime_type"] == "image/jpeg"
    assert evidence["evidence_type"] == "ORIGINAL"
    with Session(test_engine) as session:
        stored = session.get(EvidenceFile, evidence["id"])
        assert stored is not None
        assert len(stored.checksum or "") == 64
        assert stored.width == 8
        assert stored.height == 6
        assert not stored.file_path.startswith("C:")
    served = api_client.get(f"/api/v1/evidence/{evidence['id']}", headers=headers)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert served.content == evidence_jpeg()


def test_reading_requires_jpeg_evidence(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    missing = api_client.post(
        f"/api/v1/inspections/{inspection['id']}/readings",
        data={"payload": json.dumps(reading_payload(location_id=location["id"]))},
        headers=headers,
    )
    assert missing.status_code == 422
    unsupported = api_client.post(
        f"/api/v1/inspections/{inspection['id']}/readings",
        data={"payload": json.dumps(reading_payload(location_id=location["id"]))},
        files={"evidence": ("evidence.png", evidence_jpeg(), "image/png")},
        headers=headers,
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_EVIDENCE_MIME"
    invalid = submit_reading(
        api_client,
        inspection["id"],
        headers,
        reading_payload(location_id=location["id"]),
        evidence=b"not-a-jpeg",
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_JPEG_EVIDENCE"


def test_empty_and_oversized_evidence_are_rejected(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    payload = reading_payload(location_id=location["id"])
    empty = submit_reading(api_client, inspection["id"], headers, payload, evidence=b"")
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "EMPTY_EVIDENCE_FILE"
    oversized = submit_reading(api_client, inspection["id"], headers, reading_payload(location_id=location["id"]), evidence=b"x" * (5 * 1024 * 1024 + 1))
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "EVIDENCE_FILE_TOO_LARGE"


def test_empty_requires_confirmation_and_keeps_empty_confirmation_evidence(api_client: TestClient) -> None:
    token, _ = login(api_client, "supervisor01")
    headers = {"Authorization": f"Bearer {token}"}
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-02")
    payload = reading_payload(location_id=location["id"], pallet=None)
    payload.update(observed_state="EMPTY", empty_confirmed_by_operator=False)
    rejected = submit_reading(api_client, inspection["id"], headers, payload)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "EMPTY_CONFIRMATION_REQUIRED"
    payload["client_reading_id"] = str(uuid4())
    payload["empty_confirmed_by_operator"] = True
    accepted = submit_reading(api_client, inspection["id"], headers, payload)
    assert accepted.status_code == 201
    assert accepted.json()["evidence"]["evidence_type"] == "EMPTY_CONFIRMATION"


def test_rescan_attempts_each_keep_evidence(api_client: TestClient, test_engine) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers, zone_id=2)
    location = lookup_location(api_client, headers, "B-01-01")
    group_id = uuid4()
    first = submit_reading(api_client, inspection["id"], headers, reading_payload(
        location_id=location["id"], pallet="PAL-006", quality=42, group_id=group_id,
    ))
    second = submit_reading(api_client, inspection["id"], headers, reading_payload(
        location_id=location["id"], pallet="PAL-006", quality=94, group_id=group_id, attempt=2,
    ))
    assert first.json()["evidence"]["evidence_type"] == "ORIGINAL"
    assert second.json()["evidence"]["evidence_type"] == "RESCAN"
    with Session(test_engine) as session:
        stored = session.scalars(
            select(EvidenceFile).join(InspectionReading).where(
                InspectionReading.reading_group_id == group_id
            )
        ).all()
        assert len(stored) == 2


def test_android_camera_source_is_accepted_but_drone_is_rejected(api_client: TestClient) -> None:
    headers = auth_headers(api_client)
    inspection = create_inspection(api_client, headers)
    location = lookup_location(api_client, headers, "A-01-01")
    camera_payload = reading_payload(location_id=location["id"])
    camera_payload["source_type"] = "ANDROID_CAMERA"
    accepted = submit_reading(api_client, inspection["id"], headers, camera_payload)
    assert accepted.status_code == 201

    location_two = lookup_location(api_client, headers, "A-01-02")
    drone_payload = reading_payload(location_id=location_two["id"])
    drone_payload["source_type"] = "DRONE"
    rejected = submit_reading(api_client, inspection["id"], headers, drone_payload)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "SOURCE_NOT_AVAILABLE"
