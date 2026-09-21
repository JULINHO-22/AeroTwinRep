from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.domain.settings import load_business_rule_settings
from app.models.enums import InspectionStatus, UserRole
from app.models.identity import SensorDevice, User
from app.models.inspection import Inspection, InspectionReading
from app.schemas.inspection import (
    InspectionCreateRequest,
    InspectionResponse,
    ReadingCreateRequest,
    ReadingResponse,
    EvidenceSummary,
    EmptyConfirmationRequest,
    EvidenceAttemptResponse,
    ReviewExceptionResponse,
    LiveInspectionStateResponse,
)
from app.models.enums import ObservedState, ReadingStatus
from app.models.warehouse import Pallet, Location
from app.domain.comparison import compare_inventory
from app.services.inspection_service import (
    create_inspection,
    get_active_inspection,
    get_visible_inspection,
    inspection_progress,
)
from app.services.flowtwin_service import persist
from app.services.reading_service import ReadingCommand, ReadingService
from app.services.evidence_storage import EvidenceStorage, get_evidence_storage
from app.services.live_inspection_service import live_state
from app.api.errors import ApiError


router = APIRouter(prefix="/inspections", tags=["inspections"])
operator_only = require_roles(UserRole.OPERATOR, UserRole.SUPERVISOR)
supervisor_only = require_roles(UserRole.SUPERVISOR)


@router.post("/{inspection_id}/complete", response_model=InspectionResponse)
def complete_inspection(
    inspection_id: int,
    user: Annotated[User, Depends(operator_only)],
    session: Annotated[Session, Depends(get_db)],
) -> InspectionResponse:
    """Explicit operational closure; FlowTwin persistence is part of the same transaction."""
    inspection = get_visible_inspection(session=session, inspection_id=inspection_id, user=user)
    if inspection.status is not InspectionStatus.IN_PROGRESS:
        raise ApiError(status_code=409, code="INSPECTION_NOT_IN_PROGRESS", message="La inspección ya no está activa.")
    inspection.status = InspectionStatus.COMPLETED
    inspection.completed_at = datetime.now(timezone.utc)
    session.flush()
    persist(session, inspection)
    session.commit()
    session.refresh(inspection)
    return InspectionResponse.model_validate(inspection_progress(session=session, inspection=inspection))


@router.get("/{inspection_id}/review-exceptions", response_model=list[ReviewExceptionResponse])
def review_exceptions(
    inspection_id: int,
    user: Annotated[User, Depends(operator_only)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ReviewExceptionResponse]:
    inspection = get_visible_inspection(session=session, inspection_id=inspection_id, user=user)
    unresolved = session.scalars(
        select(InspectionReading).where(
            InspectionReading.inspection_id == inspection.id,
            InspectionReading.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED,
            InspectionReading.is_final.is_(True),
        )
    ).all()
    responses = []
    for final in unresolved:
        attempts = session.scalars(
            select(InspectionReading).where(
                InspectionReading.inspection_id == inspection.id,
                InspectionReading.reading_group_id == final.reading_group_id,
            ).order_by(InspectionReading.attempt_number)
        ).all()
        location = session.get(Location, final.location_id)
        expected = session.get(Pallet, final.expected_pallet_id_at_inspection) if final.expected_pallet_id_at_inspection else None
        evidence_attempts = [
            EvidenceAttemptResponse(
                id=attempt.id,
                attempt_number=attempt.attempt_number,
                evidence_id=evidence.id,
                captured_at=evidence.captured_at,
            )
            for attempt in attempts for evidence in attempt.evidence_files
        ]
        responses.append(ReviewExceptionResponse(
            reading_group_id=final.reading_group_id,
            location_code=location.code if location else "",
            expected_pallet_code=expected.pallet_code if expected else None,
            status=final.reading_status,
            attempts=len(attempts),
            evidence_attempts=evidence_attempts,
        ))
    return responses


@router.post("/{inspection_id}/review-exceptions/confirm-empty", response_model=ReadingResponse)
def confirm_exception_empty(
    inspection_id: int,
    payload: EmptyConfirmationRequest,
    user: Annotated[User, Depends(supervisor_only)],
    session: Annotated[Session, Depends(get_db)],
) -> ReadingResponse:
    inspection = session.get(Inspection, inspection_id)
    if inspection is None:
        raise ApiError(status_code=404, code="INSPECTION_NOT_FOUND", message="La inspección no existe.")
    reading = session.scalar(select(InspectionReading).where(
        InspectionReading.inspection_id == inspection_id,
        InspectionReading.reading_group_id == payload.reading_group_id,
        InspectionReading.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED,
        InspectionReading.is_final.is_(True),
    ))
    if reading is None:
        raise ApiError(status_code=404, code="REVIEW_EXCEPTION_NOT_FOUND", message="No existe una excepción pendiente para confirmar.")
    reading.observed_state = ObservedState.EMPTY
    reading.empty_confirmed_by_operator = True
    reading.reading_status = ReadingStatus.ACCEPTED
    reading.comparison_result = compare_inventory(
        expected_pallet_id=reading.expected_pallet_id_at_inspection,
        observed_state=ObservedState.EMPTY,
        observed_pallet_id=None,
        empty_confirmed_by_operator=True,
    )
    session.commit()
    session.refresh(reading)
    result = ReadingService(settings=load_business_rule_settings())._build_result(session=session, reading=reading, idempotent=False)
    evidence = reading.evidence_files[-1]
    return ReadingResponse(
        id=reading.id, inspection_id=reading.inspection_id, client_reading_id=reading.client_reading_id,
        location_id=reading.location_id, location_code=session.get(Location, reading.location_id).code,
        reading_group_id=reading.reading_group_id, attempt_number=reading.attempt_number,
        expected_pallet_code=(session.get(Pallet, reading.expected_pallet_id_at_inspection).pallet_code if reading.expected_pallet_id_at_inspection else None),
        observed_pallet_code=None, observed_state=reading.observed_state, quality_score=reading.quality_score,
        reading_status=reading.reading_status, comparison_result=reading.comparison_result,
        is_final=reading.is_final, risk_score=result.risk_score, severity=result.severity, risk_breakdown=result.risk_breakdown, idempotent=False,
        evidence=EvidenceSummary(id=evidence.id, mime_type=evidence.mime_type, evidence_type=evidence.evidence_type),
        created_at=reading.created_at,
    )


@router.post("", status_code=201, response_model=InspectionResponse)
def start_inspection(
    payload: InspectionCreateRequest,
    user: Annotated[User, Depends(operator_only)],
    session: Annotated[Session, Depends(get_db)],
) -> InspectionResponse:
    inspection = create_inspection(session=session, zone_id=payload.zone_id, user=user)
    return InspectionResponse.model_validate(
        inspection_progress(session=session, inspection=inspection)
    )


@router.get("/active", response_model=InspectionResponse | None)
def active_inspection(
    user: Annotated[User, Depends(operator_only)],
    session: Annotated[Session, Depends(get_db)],
) -> InspectionResponse | None:
    inspection = get_active_inspection(session=session, user=user)
    if inspection is None:
        return None
    return InspectionResponse.model_validate(
        inspection_progress(session=session, inspection=inspection)
    )


@router.get("/{inspection_id}/live-state", response_model=LiveInspectionStateResponse)
def inspection_live_state(
    inspection_id: int,
    user: Annotated[User, Depends(operator_only)],
    session: Annotated[Session, Depends(get_db)],
) -> LiveInspectionStateResponse:
    """Light polling projection for Home, Gemelo and Monitor.

    The endpoint is intentionally read-only: only final persisted readings are
    counted, while fresh sensor telemetry may temporarily mark a cell as
    ``SCANNING``.  This makes polling safe at the one-second cadence used by
    Android.
    """

    inspection = get_visible_inspection(
        session=session, inspection_id=inspection_id, user=user
    )
    return LiveInspectionStateResponse.model_validate(
        live_state(session=session, inspection=inspection)
    )


@router.get("/{inspection_id}", response_model=InspectionResponse)
def inspection_detail(
    inspection_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> InspectionResponse:
    inspection = get_visible_inspection(
        session=session, inspection_id=inspection_id, user=user
    )
    return InspectionResponse.model_validate(
        inspection_progress(session=session, inspection=inspection)
    )


@router.post("/{inspection_id}/assign-sensor/{sensor_id}", response_model=InspectionResponse)
def assign_sensor(
    inspection_id: int,
    sensor_id: int,
    _user: Annotated[User, Depends(supervisor_only)],
    session: Annotated[Session, Depends(get_db)],
) -> InspectionResponse:
    inspection = session.get(Inspection, inspection_id)
    if inspection is None:
        raise ApiError(status_code=404, code="INSPECTION_NOT_FOUND", message="La inspección indicada no existe.")
    if inspection.status is not InspectionStatus.IN_PROGRESS:
        raise ApiError(status_code=409, code="INSPECTION_NOT_IN_PROGRESS", message="La inspección no puede asignarse porque no está activa.")
    sensor = session.get(SensorDevice, sensor_id)
    if sensor is None:
        raise ApiError(status_code=404, code="SENSOR_NOT_FOUND", message="El sensor indicado no existe.")
    sensor.assigned_inspection_id = inspection.id
    session.commit()
    return InspectionResponse.model_validate(inspection_progress(session=session, inspection=inspection))


@router.post("/{inspection_id}/readings", status_code=201, response_model=ReadingResponse)
async def submit_reading(
    inspection_id: int,
    payload: Annotated[str, Form()],
    evidence: Annotated[UploadFile, File()],
    response: Response,
    user: Annotated[User, Depends(operator_only)],
    session: Annotated[Session, Depends(get_db)],
    evidence_storage: Annotated[EvidenceStorage, Depends(get_evidence_storage)],
) -> ReadingResponse:
    try:
        reading_payload = ReadingCreateRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="El payload de lectura contiene datos inválidos.",
            details={"fields": exc.errors()},
        ) from exc
    staged_evidence = await evidence_storage.stage(evidence)
    service = ReadingService(settings=load_business_rule_settings())
    try:
        result = service.process(
            session=session,
            inspection_id=inspection_id,
            user=user,
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
    if result.idempotent:
        response.status_code = 200
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
