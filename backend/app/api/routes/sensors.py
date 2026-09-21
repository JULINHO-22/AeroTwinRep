"""Device-facing and supervisor-facing Sensor Mode API."""

from __future__ import annotations

import hashlib
import secrets
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_sensor, require_roles
from app.api.errors import ApiError
from app.db.session import get_db
from app.domain.settings import load_business_rule_settings
from app.models.enums import InspectionStatus, SourceType, UserRole
from app.models.identity import SensorDevice, User
from app.models.inspection import Inspection, InspectionReading
from app.models.warehouse import Location, Pallet, WarehouseZone
from app.schemas.inspection import EvidenceSummary, InspectionResponse, ReadingCreateRequest, ReadingResponse
from app.schemas.sensor import (
    SensorLastReadingResponse,
    SensorMissionResponse,
    SensorNextObjectiveResponse,
    SensorRegisterRequest,
    SensorRegisterResponse,
    SensorStatusResponse,
    SensorTelemetryRequest,
)
from app.models.enums import ObservedState
from app.services.evidence_storage import EvidenceStorage, get_evidence_storage
from app.services.reading_service import ReadingCommand, ReadingService
from app.services.inspection_service import inspection_progress
from app.services.sensor_live import live_frames, live_telemetry
from app.services.live_inspection_service import next_objective
from app.config import get_settings


sensor_router = APIRouter(prefix="/sensor", tags=["sensor device"])
supervisor_router = APIRouter(prefix="/sensors", tags=["sensors"])
sensor_viewer = require_roles(UserRole.OPERATOR, UserRole.SUPERVISOR)


def _latest_active_inspection(session: Session) -> Inspection | None:
    """Return the demo mission that a just-started mobile sensor should follow."""
    return session.scalar(
        select(Inspection)
        .where(Inspection.status == InspectionStatus.IN_PROGRESS)
        .order_by(Inspection.started_at.desc())
        .limit(1)
    )


def _mission(session: Session, device: SensorDevice) -> SensorMissionResponse | None:
    inspection = session.get(Inspection, device.assigned_inspection_id) if device.assigned_inspection_id else None
    if inspection is None or inspection.status is not InspectionStatus.IN_PROGRESS:
        # Demo behaviour: there is one active operation, so a mobile sensor joins
        # it automatically. This removes the manual supervisor-only assignment
        # that stopped the phone at the waiting screen during the prototype.
        inspection = _latest_active_inspection(session) if get_settings().demo_mode else None
        if inspection is None:
            return None
        device.assigned_inspection_id = inspection.id
        session.commit()
    zone = session.get(WarehouseZone, inspection.zone_id)
    return SensorMissionResponse(
        inspection_id=inspection.id,
        zone=zone.code if zone else "",
        status=inspection.status.value,
    )


def _assigned_mission(session: Session, device: SensorDevice) -> SensorMissionResponse | None:
    """Read a device mission without assigning a historical device as a side effect."""
    inspection = session.get(Inspection, device.assigned_inspection_id) if device.assigned_inspection_id else None
    if inspection is None or inspection.status is not InspectionStatus.IN_PROGRESS:
        return None
    zone = session.get(WarehouseZone, inspection.zone_id)
    return SensorMissionResponse(
        inspection_id=inspection.id,
        zone=zone.code if zone else "",
        status=inspection.status.value,
    )


def _touch(session: Session, device: SensorDevice) -> None:
    device.status = "ONLINE"
    device.last_seen_at = datetime.now(timezone.utc)
    session.commit()


def _reading_response(result) -> ReadingResponse:
    reading = result.reading
    return ReadingResponse(
        id=reading.id,
        inspection_id=reading.inspection_id,
        client_reading_id=reading.client_reading_id,
        location_id=reading.location_id,
        location_code=result.location_code,
        reading_group_id=reading.reading_group_id,
        attempt_number=reading.attempt_number,
        expected_pallet_code=result.expected_pallet_code,
        observed_pallet_code=result.observed_pallet_code,
        observed_state=reading.observed_state,
        quality_score=reading.quality_score,
        reading_status=reading.reading_status,
        comparison_result=reading.comparison_result,
        is_final=reading.is_final,
        risk_score=result.risk_score,
        severity=result.severity,
        risk_breakdown=result.risk_breakdown,
        idempotent=result.idempotent,
        evidence=EvidenceSummary(
            id=result.evidence.id,
            mime_type=result.evidence.mime_type,
            evidence_type=result.evidence.evidence_type,
        ),
        created_at=reading.created_at,
    )


def _status_response(session: Session, device: SensorDevice) -> SensorStatusResponse:
    last_reading = session.get(InspectionReading, device.last_reading_id) if device.last_reading_id else None
    last_reading_response = None
    if last_reading and last_reading.inspection_id == device.assigned_inspection_id:
        location = session.get(Location, last_reading.location_id)
        pallet = session.get(Pallet, last_reading.observed_pallet_id) if last_reading.observed_pallet_id else None
        last_reading_response = SensorLastReadingResponse(
            evidence_id=last_reading.evidence_files[0].id,
            location_code=location.code if location else "",
            observed_pallet_code=pallet.pallet_code if pallet else None,
            comparison_result=last_reading.comparison_result.value,
            created_at=last_reading.created_at,
        )
    is_online = (
        device.last_seen_at is not None
        and (datetime.now(timezone.utc) - device.last_seen_at).total_seconds() <= 12
    )
    mission = _assigned_mission(session, device)
    telemetry = live_telemetry.get(device.id, mission.inspection_id) if mission else None
    return SensorStatusResponse(
        id=device.id,
        device_code=device.device_code,
        name=device.name,
        status="ONLINE" if is_online else "OFFLINE",
        last_seen_at=device.last_seen_at,
        mission=mission,
        last_reading=last_reading_response,
        live_message=telemetry.message if telemetry else None,
        last_detected_code=telemetry.detected_code if telemetry else None,
    )


@sensor_router.post("/register", status_code=201, response_model=SensorRegisterResponse)
def register_sensor(
    payload: SensorRegisterRequest,
    session: Annotated[Session, Depends(get_db)],
) -> SensorRegisterResponse:
    # Pairing is intentionally simple for the local demo; a deployment would protect it.
    token = secrets.token_urlsafe(32)
    device = SensorDevice(
        device_code=f"SENSOR-{secrets.token_hex(3).upper()}",
        name=payload.name.strip(),
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        status="ONLINE",
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    return SensorRegisterResponse(
        id=device.id, device_code=device.device_code, name=device.name, device_token=token
    )


@sensor_router.get("/mission", response_model=SensorMissionResponse | None)
def sensor_mission(
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
) -> SensorMissionResponse | None:
    _touch(session, device)
    return _mission(session, device)


@sensor_router.get("/locations/code/{code}")
def sensor_location(
    code: str,
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, int | str]:
    mission = _mission(session, device)
    if mission is None:
        raise ApiError(status_code=409, code="SENSOR_NO_MISSION", message="El sensor no tiene una misión activa.")
    location = session.scalar(select(Location).where(Location.code == code.strip().upper()))
    if location is None or not location.is_active:
        raise ApiError(status_code=404, code="LOCATION_NOT_FOUND", message="La ubicación no existe o no está activa.")
    inspection = session.get(Inspection, mission.inspection_id)
    if location.zone_id != inspection.zone_id:
        raise ApiError(status_code=409, code="LOCATION_OUTSIDE_INSPECTION_ZONE", message="La ubicación no pertenece a la zona asignada.")
    _touch(session, device)
    return {"id": location.id, "code": location.code}


@sensor_router.get("/mission/next", response_model=SensorNextObjectiveResponse)
def sensor_next_objective(
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
) -> SensorNextObjectiveResponse:
    """Return the deterministic Core-owned next target for this sensor."""
    mission = _mission(session, device)
    if mission is None:
        raise ApiError(status_code=409, code="SENSOR_NO_MISSION", message="El sensor no tiene una misión activa.")
    inspection = session.get(Inspection, mission.inspection_id)
    if inspection is None:
        raise ApiError(status_code=409, code="SENSOR_MISSION_INVALID", message="La misión del sensor ya no está disponible.")
    _touch(session, device)
    return SensorNextObjectiveResponse.model_validate(
        next_objective(session=session, inspection=inspection)
    )


@sensor_router.get("/mission/progress", response_model=InspectionResponse)
def sensor_mission_progress(
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
) -> InspectionResponse:
    """Lets a device refresh the Core-owned counter without a human session."""
    mission = _mission(session, device)
    if mission is None:
        raise ApiError(status_code=409, code="SENSOR_NO_MISSION", message="No hay inspección activa.")
    inspection = session.get(Inspection, mission.inspection_id)
    _touch(session, device)
    return InspectionResponse.model_validate(inspection_progress(session=session, inspection=inspection))


@sensor_router.post("/preview", status_code=204)
async def upload_preview(
    frame: Annotated[UploadFile, File()],
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    mission = _mission(session, device)
    if mission is None:
        raise ApiError(status_code=409, code="SENSOR_NO_MISSION", message="No hay inspección activa.")
    data = await frame.read(512_001)
    if len(data) > 512_000:
        raise ApiError(status_code=413, code="FRAME_TOO_LARGE", message="La vista es demasiado grande.")
    try:
        with Image.open(BytesIO(data)) as img:
            if img.format != "JPEG" or max(img.size) > 1280:
                raise ValueError("Invalid preview")
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ApiError(status_code=422, code="INVALID_FRAME", message="La vista debe ser un JPEG válido de hasta 1280 píxeles.")
    live_frames.put(device.id, mission.inspection_id, data)
    _touch(session, device)
    return Response(status_code=204)


@sensor_router.post("/telemetry", status_code=204)
def sensor_telemetry(
    payload: SensorTelemetryRequest,
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    mission = _mission(session, device)
    if mission is None:
        raise ApiError(status_code=409, code="SENSOR_NO_MISSION", message="No hay inspección activa.")
    live_telemetry.put(device.id, mission.inspection_id, payload.message, payload.detected_code)
    _touch(session, device)
    return Response(status_code=204)


@supervisor_router.get("/{sensor_id}/preview")
def view_preview(
    sensor_id: int,
    user: Annotated[User, Depends(sensor_viewer)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    device = session.get(SensorDevice, sensor_id)
    if device is None:
        raise ApiError(status_code=404, code="SENSOR_NOT_FOUND", message="El sensor no existe.")
    inspection = session.get(Inspection, device.assigned_inspection_id) if device.assigned_inspection_id else None
    if inspection is None or (user.role is UserRole.OPERATOR and inspection.started_by != user.id):
        raise ApiError(status_code=403, code="SENSOR_FORBIDDEN", message="No tienes acceso a este sensor.")
    jpeg = live_frames.get(device.id, inspection.id) if inspection.status is InspectionStatus.IN_PROGRESS else None
    headers = {"Cache-Control": "no-store"}
    return Response(content=jpeg, media_type="image/jpeg", headers=headers) if jpeg else Response(status_code=204, headers=headers)


@sensor_router.post("/mission/readings", status_code=201, response_model=ReadingResponse)
async def submit_sensor_reading(
    payload: Annotated[str, Form()],
    evidence: Annotated[UploadFile, File()],
    response: Response,
    device: Annotated[SensorDevice, Depends(get_current_sensor)],
    session: Annotated[Session, Depends(get_db)],
    evidence_storage: Annotated[EvidenceStorage, Depends(get_evidence_storage)],
) -> ReadingResponse:
    mission = _mission(session, device)
    if mission is None:
        raise ApiError(status_code=409, code="SENSOR_NO_MISSION", message="El sensor no tiene una misión activa.")
    try:
        reading_payload = ReadingCreateRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise ApiError(status_code=422, code="VALIDATION_ERROR", message="La lectura del sensor contiene datos inválidos.") from exc
    if reading_payload.source_type is not SourceType.ANDROID_CAMERA:
        raise ApiError(status_code=422, code="SENSOR_SOURCE_REQUIRED", message="El sensor solo puede enviar lecturas ANDROID_CAMERA.")
    if reading_payload.observed_state is ObservedState.EMPTY or reading_payload.empty_confirmed_by_operator:
        raise ApiError(
            status_code=403,
            code="SENSOR_CANNOT_CONFIRM_EMPTY",
            message="El sensor no puede confirmar una posición vacía; debe reportar UNRESOLVED.",
        )
    inspection = session.get(Inspection, mission.inspection_id)
    owner = session.get(User, inspection.started_by) if inspection else None
    if inspection is None or owner is None:
        raise ApiError(status_code=409, code="SENSOR_MISSION_INVALID", message="La misión del sensor ya no está disponible.")
    staged_evidence = await evidence_storage.stage(evidence)
    try:
        result = ReadingService(settings=load_business_rule_settings()).process(
            session=session,
            inspection_id=inspection.id,
            user=owner,
            command=ReadingCommand(
                client_reading_id=reading_payload.client_reading_id,
                location_id=reading_payload.location_id,
                reading_group_id=reading_payload.reading_group_id,
                attempt_number=reading_payload.attempt_number,
                observed_pallet_code=reading_payload.observed_pallet_code,
                observed_state=reading_payload.observed_state,
                quality_score=reading_payload.quality_score,
                source_type=reading_payload.source_type,
                empty_confirmed_by_operator=reading_payload.empty_confirmed_by_operator,
            ),
            staged_evidence=staged_evidence,
            evidence_storage=evidence_storage,
        )
    except Exception:
        evidence_storage.discard(staged_evidence)
        raise
    device.last_reading_id = result.reading.id
    device.status = "ONLINE"
    device.last_seen_at = datetime.now(timezone.utc)
    session.commit()
    if result.reading.is_final:
        # The final persisted reading now owns the cell state. Candidate
        # telemetry must not keep it visually stuck in SCANNING.
        live_telemetry.clear(device.id, inspection.id)
    if result.idempotent:
        response.status_code = 200
    return _reading_response(result)


@supervisor_router.get("", response_model=list[SensorStatusResponse])
def list_sensors(
    user: Annotated[User, Depends(sensor_viewer)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SensorStatusResponse]:
    query = select(SensorDevice).order_by(SensorDevice.name)
    if user.role is UserRole.OPERATOR:
        query = query.join(Inspection, SensorDevice.assigned_inspection_id == Inspection.id).where(Inspection.started_by == user.id)
    return [_status_response(session, device) for device in session.scalars(query).all()]


@supervisor_router.get("/{sensor_id}/status", response_model=SensorStatusResponse)
def sensor_status(
    sensor_id: int,
    user: Annotated[User, Depends(sensor_viewer)],
    session: Annotated[Session, Depends(get_db)],
) -> SensorStatusResponse:
    device = session.get(SensorDevice, sensor_id)
    if device is None:
        raise ApiError(status_code=404, code="SENSOR_NOT_FOUND", message="El sensor indicado no existe.")
    if user.role is UserRole.OPERATOR:
        mission = _mission(session, device)
        inspection = session.get(Inspection, mission.inspection_id) if mission else None
        if inspection is None or inspection.started_by != user.id:
            raise ApiError(status_code=403, code="SENSOR_FORBIDDEN", message="No tienes acceso a este sensor.")
    return _status_response(session, device)
