from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.domain.comparison import InvalidObservationError, compare_inventory
from app.domain.quality import evaluate_reading_quality
from app.domain.risk import RiskContext, RiskRule, calculate_risk
from app.domain.analytics import CoverageStatus
from app.services.inventory_analytics import fefo_for_outbound_lot, product_coverage_from_history, product_rotation_from_history
from app.domain.settings import BusinessRuleSettings
from app.models.enums import (
    ComparisonResult,
    InspectionStatus,
    ObservedState,
    ReadingStatus,
    SourceType,
    ExceptionStatus, ExceptionType,
)
from app.models.identity import User
from app.models.enums import UserRole
from app.models.inspection import EvidenceFile, Inspection, InspectionReading
from app.models.operations import ExceptionEvent
from app.models.enums import EvidenceType
from app.services.evidence_storage import EvidenceStorage, StagedEvidence
from app.models.warehouse import ExpectedInventory, Location, Pallet


@dataclass(frozen=True)
class ReadingCommand:
    client_reading_id: UUID
    location_id: int
    reading_group_id: UUID
    attempt_number: int
    observed_pallet_code: str | None
    observed_state: ObservedState
    quality_score: int
    source_type: SourceType
    empty_confirmed_by_operator: bool


@dataclass(frozen=True)
class ProcessedReading:
    reading: InspectionReading
    location_code: str
    expected_pallet_code: str | None
    observed_pallet_code: str | None
    risk_score: int
    severity: str
    risk_breakdown: dict[str, int]
    evidence: EvidenceFile
    idempotent: bool


class ReadingService:
    def __init__(self, *, settings: BusinessRuleSettings) -> None:
        self.settings = settings

    def process(
        self,
        *,
        session: Session,
        inspection_id: int,
        user: User,
        command: ReadingCommand,
        staged_evidence: StagedEvidence,
        evidence_storage: EvidenceStorage,
    ) -> ProcessedReading:
        inspection = session.get(Inspection, inspection_id)
        if inspection is None:
            raise ApiError(
                status_code=404,
                code="INSPECTION_NOT_FOUND",
                message="La inspección indicada no existe.",
                details={"inspection_id": inspection_id},
            )
        if inspection.started_by != user.id:
            raise ApiError(
                status_code=403,
                code="INSPECTION_FORBIDDEN",
                message="Solo el operador que inició la inspección puede registrar lecturas.",
            )

        existing = session.scalar(
            select(InspectionReading).where(
                InspectionReading.client_reading_id == command.client_reading_id
            )
        )
        if existing is not None:
            evidence_storage.discard(staged_evidence)
            if existing.inspection_id != inspection_id:
                raise ApiError(
                    status_code=409,
                    code="CLIENT_READING_ID_CONFLICT",
                    message="El identificador de lectura ya pertenece a otra inspección.",
                )
            return self._build_result(session=session, reading=existing, idempotent=True)

        if inspection.status is not InspectionStatus.IN_PROGRESS:
            raise ApiError(
                status_code=409,
                code="INSPECTION_NOT_IN_PROGRESS",
                message="La inspección ya no acepta nuevas lecturas.",
                details={"status": inspection.status.value},
            )
        if command.source_type not in (SourceType.MANUAL_DEMO, SourceType.ANDROID_CAMERA):
            raise ApiError(
                status_code=422,
                code="SOURCE_NOT_AVAILABLE",
                message="En esta fase solo se aceptan lecturas MANUAL_DEMO o ANDROID_CAMERA.",
                details={"source_type": command.source_type.value},
            )

        location = session.get(Location, command.location_id)
        if location is None or not location.is_active:
            raise ApiError(
                status_code=404,
                code="LOCATION_NOT_FOUND",
                message="La ubicación indicada no existe o no está activa.",
                details={"location_id": command.location_id},
            )
        if location.zone_id != inspection.zone_id:
            raise ApiError(
                status_code=409,
                code="LOCATION_OUTSIDE_INSPECTION_ZONE",
                message="La ubicación no pertenece a la zona de la inspección.",
                details={"location_id": location.id, "inspection_zone_id": inspection.zone_id},
            )

        self._validate_attempt_sequence(
            session=session,
            inspection_id=inspection_id,
            command=command,
        )
        observed_pallet = self._resolve_observation(session=session, command=command, user=user)
        expected_inventory = session.scalar(
            select(ExpectedInventory).where(ExpectedInventory.location_id == location.id)
        )
        expected_pallet_id = (
            expected_inventory.expected_pallet_id if expected_inventory is not None else None
        )

        try:
            # Absence of a decoded pallet is an observation failure, never EMPTY.
            # Preserve every capture and escalate the final attempt to human review.
            reading_status = (
                ReadingStatus.HUMAN_REVIEW_REQUIRED
                if command.observed_state is ObservedState.UNRESOLVED
                and command.attempt_number >= self.settings.max_reading_attempts
                else ReadingStatus.RESCAN_REQUIRED
                if command.observed_state is ObservedState.UNRESOLVED
                else evaluate_reading_quality(
                    quality_score=command.quality_score,
                    attempt_number=command.attempt_number,
                    quality_threshold=self.settings.rescan_quality_threshold,
                    max_reading_attempts=self.settings.max_reading_attempts,
                )
            )
        except ValueError as exc:
            raise ApiError(
                status_code=422,
                code="INVALID_READING_ATTEMPT",
                message=str(exc),
            ) from exc

        comparison_result = ComparisonResult.UNRESOLVED
        if reading_status is ReadingStatus.ACCEPTED:
            try:
                comparison_result = compare_inventory(
                    expected_pallet_id=expected_pallet_id,
                    observed_state=command.observed_state,
                    observed_pallet_id=(observed_pallet.id if observed_pallet else None),
                    empty_confirmed_by_operator=command.empty_confirmed_by_operator,
                )
            except InvalidObservationError as exc:
                raise ApiError(
                    status_code=422,
                    code="INVALID_OBSERVATION",
                    message=str(exc),
                ) from exc

        reading = InspectionReading(
            inspection_id=inspection.id,
            location_id=location.id,
            client_reading_id=command.client_reading_id,
            reading_group_id=command.reading_group_id,
            attempt_number=command.attempt_number,
            expected_pallet_id_at_inspection=expected_pallet_id,
            observed_pallet_id=observed_pallet.id if observed_pallet else None,
            observed_state=command.observed_state,
            quality_score=command.quality_score,
            reading_status=reading_status,
            comparison_result=comparison_result,
            is_final=reading_status is not ReadingStatus.RESCAN_REQUIRED,
            created_by=user.id,
            source_type=command.source_type,
            empty_confirmed_by_operator=command.empty_confirmed_by_operator,
        )
        evidence_type = self._evidence_type(command)
        evidence = EvidenceFile(
            reading=reading,
            file_path=evidence_storage.final_relative_path(inspection.id),
            mime_type=staged_evidence.mime_type,
            source_type=command.source_type,
            evidence_type=evidence_type,
            captured_at=staged_evidence.captured_at,
            checksum=staged_evidence.checksum,
            width=staged_evidence.width,
            height=staged_evidence.height,
        )
        session.add(reading)
        session.add(evidence)
        final_path = None
        try:
            session.flush()
            final_path = evidence_storage.finalize(staged_evidence, evidence.file_path)
            if reading.is_final:
                self._upsert_exception(session=session, reading=reading)
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            if final_path is not None:
                final_path.unlink(missing_ok=True)
            evidence_storage.discard(staged_evidence)
            duplicate = session.scalar(
                select(InspectionReading).where(
                    InspectionReading.client_reading_id == command.client_reading_id
                )
            )
            if duplicate is not None and duplicate.inspection_id == inspection_id:
                return self._build_result(
                    session=session, reading=duplicate, idempotent=True
                )
            raise ApiError(
                status_code=409,
                code="READING_CONFLICT",
                message="La lectura entra en conflicto con un intento ya registrado.",
            ) from exc
        except Exception:
            session.rollback()
            if final_path is not None:
                final_path.unlink(missing_ok=True)
            evidence_storage.discard(staged_evidence)
            raise
        session.refresh(reading)
        return self._build_result(session=session, reading=reading, idempotent=False)

    @staticmethod
    def _evidence_type(command: ReadingCommand) -> EvidenceType:
        if command.observed_state is ObservedState.EMPTY:
            return EvidenceType.EMPTY_CONFIRMATION
        if command.attempt_number > 1:
            return EvidenceType.RESCAN
        return EvidenceType.ORIGINAL

    def _validate_attempt_sequence(
        self,
        *,
        session: Session,
        inspection_id: int,
        command: ReadingCommand,
    ) -> None:
        if command.attempt_number > self.settings.max_reading_attempts:
            raise ApiError(
                status_code=422,
                code="ATTEMPT_LIMIT_EXCEEDED",
                message="El número de intento supera el máximo configurado.",
                details={"max_attempts": self.settings.max_reading_attempts},
            )
        prior = session.scalars(
            select(InspectionReading)
            .where(
                InspectionReading.inspection_id == inspection_id,
                InspectionReading.reading_group_id == command.reading_group_id,
            )
            .order_by(InspectionReading.attempt_number)
        ).all()
        expected_attempt = 1 if not prior else prior[-1].attempt_number + 1
        if command.attempt_number != expected_attempt:
            raise ApiError(
                status_code=409,
                code="INVALID_ATTEMPT_SEQUENCE",
                message="El intento no sigue la secuencia del grupo de lectura.",
                details={"expected_attempt": expected_attempt},
            )
        if prior and any(item.location_id != command.location_id for item in prior):
            raise ApiError(
                status_code=409,
                code="READING_GROUP_LOCATION_CONFLICT",
                message="El grupo de lectura ya pertenece a otra ubicación.",
            )
        if prior and prior[-1].is_final:
            raise ApiError(
                status_code=409,
                code="READING_GROUP_ALREADY_FINAL",
                message="El grupo de lectura ya tiene un resultado final.",
            )

    def _resolve_observation(
        self, *, session: Session, command: ReadingCommand, user: User
    ) -> Pallet | None:
        if command.observed_state is ObservedState.PALLET:
            if command.observed_pallet_code is None:
                raise ApiError(
                    status_code=422,
                    code="PALLET_CODE_REQUIRED",
                    message="Una observación PALLET requiere el código del pallet.",
                )
            pallet = session.scalar(
                select(Pallet).where(Pallet.pallet_code == command.observed_pallet_code)
            )
            if pallet is None:
                raise ApiError(
                    status_code=404,
                    code="PALLET_NOT_FOUND",
                    message="El pallet observado no existe.",
                    details={"pallet_code": command.observed_pallet_code},
                )
            return pallet
        if command.observed_pallet_code is not None:
            raise ApiError(
                status_code=422,
                code="PALLET_CODE_NOT_ALLOWED",
                message="EMPTY y UNRESOLVED no pueden incluir un código de pallet.",
            )
        if (
            command.observed_state is ObservedState.EMPTY
            and not command.empty_confirmed_by_operator
        ):
            raise ApiError(
                status_code=422,
                code="EMPTY_CONFIRMATION_REQUIRED",
                message="El operador debe confirmar una ubicación vacía.",
            )
        if command.observed_state is ObservedState.EMPTY and user.role is not UserRole.SUPERVISOR:
            raise ApiError(
                status_code=403,
                code="EMPTY_REQUIRES_SUPERVISOR",
                message="Solo un supervisor puede confirmar una ubicación vacía.",
            )
        return None

    def _build_result(
        self, *, session: Session, reading: InspectionReading, idempotent: bool
    ) -> ProcessedReading:
        location = session.get(Location, reading.location_id)
        expected = (
            session.get(Pallet, reading.expected_pallet_id_at_inspection)
            if reading.expected_pallet_id_at_inspection is not None
            else None
        )
        observed = (
            session.get(Pallet, reading.observed_pallet_id)
            if reading.observed_pallet_id is not None
            else None
        )
        risk = self._risk_for_reading(session=session, reading=reading)
        evidence = next(iter(reading.evidence_files), None)
        if evidence is None:
            raise ApiError(
                status_code=409,
                code="READING_EVIDENCE_MISSING",
                message="La lectura existente no tiene evidencia asociada.",
            )
        return ProcessedReading(
            reading=reading,
            location_code=location.code if location is not None else "",
            expected_pallet_code=expected.pallet_code if expected else None,
            observed_pallet_code=observed.pallet_code if observed else None,
            risk_score=risk.score,
            severity=risk.severity.value,
            risk_breakdown={reason.rule.value: reason.points for reason in risk.reasons},
            evidence=evidence,
            idempotent=idempotent,
        )

    def _risk_for_reading(self, *, session: Session, reading: InspectionReading):
        if not reading.is_final:
            return calculate_risk(context=RiskContext(comparison_result=ComparisonResult.UNRESOLVED), settings=self.settings)
        pallet_id = reading.observed_pallet_id or reading.expected_pallet_id_at_inspection
        pallet = session.get(Pallet, pallet_id) if pallet_id else None
        if pallet is None:
            return calculate_risk(context=RiskContext(comparison_result=reading.comparison_result, final_quality_status=reading.reading_status if reading.is_final else None), settings=self.settings)
        lot = pallet.lot
        reference = reading.created_at or datetime.now(timezone.utc)
        expiry_days = (lot.expires_at - reference.date()).days
        rotation = product_rotation_from_history(session=session, product_id=lot.product_id, reference_at=reference, settings=self.settings)
        coverage = product_coverage_from_history(session=session, product_id=lot.product_id, reference_at=reference, settings=self.settings)
        fefo = fefo_for_outbound_lot(session=session, outbound_lot_id=lot.id).risk
        historical = session.scalar(select(__import__('sqlalchemy').func.count()).select_from(ExceptionEvent).where(ExceptionEvent.location_id == reading.location_id, ExceptionEvent.created_at < reading.created_at)) or 0
        return calculate_risk(context=RiskContext(comparison_result=reading.comparison_result, days_to_expiry=expiry_days, rotation_level=rotation.level, low_coverage=coverage.status is CoverageStatus.LOW_COVERAGE, final_quality_status=reading.reading_status if reading.is_final else None, fefo_risk=fefo, historical_anomaly_count=historical), settings=self.settings)

    def _upsert_exception(self, *, session: Session, reading: InspectionReading) -> None:
        risk = self._risk_for_reading(session=session, reading=reading)
        if not risk.reasons:
            return
        if session.scalar(select(ExceptionEvent).where(ExceptionEvent.reading_id == reading.id)):
            return
        primary = next((reason for reason in risk.reasons if reason.rule in {RiskRule.PALLET_MISMATCH, RiskRule.EXPECTED_PALLET_MISSING, RiskRule.UNEXPECTED_PALLET}), risk.reasons[0])
        kind = {RiskRule.PALLET_MISMATCH: ExceptionType.PALLET_MISMATCH, RiskRule.EXPECTED_PALLET_MISSING: ExceptionType.PALLET_MISSING, RiskRule.UNEXPECTED_PALLET: ExceptionType.UNEXPECTED_PALLET, RiskRule.LOW_QUALITY: ExceptionType.LOW_QUALITY, RiskRule.EXPIRING_SOON: ExceptionType.EXPIRING_SOON, RiskRule.HIGH_ROTATION: ExceptionType.HIGH_ROTATION, RiskRule.LOW_COVERAGE: ExceptionType.LOW_COVERAGE, RiskRule.FEFO_RISK: ExceptionType.FEFO_RISK, RiskRule.HISTORICAL_ANOMALY: ExceptionType.HISTORICAL_ANOMALY}[primary.rule]
        pallet_id = reading.observed_pallet_id or reading.expected_pallet_id_at_inspection
        pallet = session.get(Pallet, pallet_id) if pallet_id else None
        session.add(ExceptionEvent(inspection_id=reading.inspection_id, reading_id=reading.id, location_id=reading.location_id, product_id=pallet.lot.product_id if pallet else None, pallet_id=pallet_id, exception_type=kind, severity=risk.severity, status=ExceptionStatus.OPEN, title=primary.label, description="; ".join(reason.label for reason in risk.reasons), risk_score=risk.score, risk_breakdown={reason.rule.value: reason.points for reason in risk.reasons}))
