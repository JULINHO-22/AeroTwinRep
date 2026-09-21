"""Read-only, client-agnostic projections for the AeroTwin Command Center."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.api.errors import ApiError
from app.db.session import get_db
from app.models.enums import ExceptionStatus, ExceptionType, InspectionStatus, ReadingStatus, Severity, UserRole
from app.models.identity import SensorDevice, User
from app.models.inspection import Inspection, InspectionReading
from app.models.operations import ExceptionEvent
from app.models.warehouse import Location, Lot, Pallet, Product, WarehouseZone
from app.services.inspection_service import inspection_progress
from app.services.inventory_analytics import fefo_for_outbound_lot, product_coverage_from_history, product_rotation_from_history
from app.domain.settings import load_business_rule_settings

router = APIRouter(tags=["command center"])
viewer = require_roles(UserRole.OPERATOR, UserRole.SUPERVISOR)
OPEN_STATUSES = (ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW)


def _visible_event_query(user: User):
    query = select(ExceptionEvent).where(ExceptionEvent.status.in_(OPEN_STATUSES))
    if user.role is UserRole.OPERATOR:
        query = query.join(Inspection, ExceptionEvent.inspection_id == Inspection.id).where(Inspection.started_by == user.id)
    return query


def _event_rows(session: Session, query) -> list[dict]:
    """A joined list projection: no location query per exception."""
    rows = session.execute(query.outerjoin(Location, ExceptionEvent.location_id == Location.id).add_columns(Location.code).order_by(ExceptionEvent.risk_score.desc(), ExceptionEvent.created_at.desc())).all()
    return [{"id": event.id, "location": code or "Sin ubicación", "type": event.exception_type.value,
             "severity": event.severity.value, "status": event.status.value, "risk_score": event.risk_score,
             "short_reason": event.title, "created_at": event.created_at} for event, code in rows]


def _active_inspection(session: Session, user: User) -> Inspection | None:
    query = select(Inspection).where(Inspection.status == InspectionStatus.IN_PROGRESS)
    if user.role is UserRole.OPERATOR:
        query = query.where(Inspection.started_by == user.id)
    return session.scalar(query.order_by(Inspection.started_at.desc()))


@router.get("/dashboard")
def dashboard(user: Annotated[User, Depends(viewer)], session: Annotated[Session, Depends(get_db)]) -> dict:
    inspection = _active_inspection(session, user)
    progress = inspection_progress(session=session, inspection=inspection) if inspection else None
    events = _event_rows(session, _visible_event_query(user))
    counts = {kind.value: 0 for kind in ExceptionType}
    for item in events:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    review_query = select(func.count(InspectionReading.id)).where(InspectionReading.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED, InspectionReading.is_final.is_(True))
    if user.role is UserRole.OPERATOR:
        review_query = review_query.join(Inspection).where(Inspection.started_by == user.id)
    sensors = session.execute(select(SensorDevice.id, SensorDevice.name, SensorDevice.device_code, SensorDevice.status).where(SensorDevice.status == "ONLINE")).all()
    verified, total = (progress["completed_locations"], progress["total_locations"]) if progress else (0, 0)
    return {
        "inspection": {"active": inspection is not None, "inspection_id": inspection.id if inspection else None, "zone_code": progress["zone_code"] if progress else None, "verified": verified, "total": total, "coverage_percent": round(verified * 100 / total, 1) if total else 0.0},
        "exceptions": {"open": len(events), "critical": sum(x["severity"] == "CRITICAL" for x in events), "high": sum(x["severity"] == "HIGH" for x in events), "human_review": int(session.scalar(review_query) or 0)},
        "inventory_risks": {"expiring_soon": counts[ExceptionType.EXPIRING_SOON.value], "low_coverage": counts[ExceptionType.LOW_COVERAGE.value], "fefo": counts[ExceptionType.FEFO_RISK.value]},
        "priorities": events[:5],
        "sensors": [{"id": row.id, "name": row.name, "code": row.device_code, "status": row.status} for row in sensors],
    }


def _reading_ids_for_pallet_ids(pallet_ids):
    """Correlated reading subquery for filters that use observed *or* expected WMS context."""

    return select(InspectionReading.id).where(
        or_(
            InspectionReading.observed_pallet_id.in_(pallet_ids),
            InspectionReading.expected_pallet_id_at_inspection.in_(pallet_ids),
        )
    )


def _filter_by_pallet_ids(query, pallet_ids):
    return query.where(
        or_(
            ExceptionEvent.pallet_id.in_(pallet_ids),
            ExceptionEvent.reading_id.in_(_reading_ids_for_pallet_ids(pallet_ids)),
        )
    )


@router.get("/exceptions")
def exceptions(
    user: Annotated[User, Depends(viewer)],
    session: Annotated[Session, Depends(get_db)],
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    zone: str | None = Query(default=None, max_length=20),
    expiry: bool | None = Query(default=None),
    expiry_days: int | None = Query(default=None, ge=0, le=3650),
    lot: str | None = Query(default=None, max_length=50),
    quality: int | None = Query(default=None, ge=0, le=100),
    quality_max: int | None = Query(default=None, ge=0, le=100),
    quality_lte: int | None = Query(default=None, ge=0, le=100),
) -> dict:
    """List open operational exceptions with lightweight operational filters.

    ``expiry=true`` uses the central risk horizon unless a caller supplies an
    explicit ``expiry_days``.  Lot filtering includes either the observed or
    expected pallet associated with the final reading, so an expected-missing
    event remains discoverable by its expected lot.
    """

    query = _visible_event_query(user)
    if type:
        try: query = query.where(ExceptionEvent.exception_type == ExceptionType(type.upper()))
        except ValueError as error: raise ApiError(status_code=422, code="INVALID_EXCEPTION_TYPE", message="Tipo de excepción inválido.") from error
    if severity:
        try: query = query.where(ExceptionEvent.severity == Severity(severity.upper()))
        except ValueError as error: raise ApiError(status_code=422, code="INVALID_SEVERITY", message="Severidad inválida.") from error
    if zone:
        location_ids = select(Location.id).join(WarehouseZone).where(
            WarehouseZone.code == zone.strip().upper()
        )
        query = query.where(ExceptionEvent.location_id.in_(location_ids))
    if lot:
        pallet_ids = select(Pallet.id).join(Lot).where(Lot.lot_code == lot.strip().upper())
        query = _filter_by_pallet_ids(query, pallet_ids)
    quality_limit = min(
        value for value in (quality, quality_max, quality_lte) if value is not None
    ) if quality is not None or quality_max is not None or quality_lte is not None else None
    if quality_limit is not None:
        query = query.where(
            ExceptionEvent.reading_id.in_(
                select(InspectionReading.id).where(
                    InspectionReading.quality_score <= quality_limit
                )
            )
        )
    if expiry is True or expiry_days is not None:
        horizon = expiry_days
        if horizon is None:
            horizon = load_business_rule_settings().expiry_risk_days
        pallet_ids = select(Pallet.id).join(Lot).where(
            Lot.expires_at <= date.today() + timedelta(days=horizon)
        )
        query = _filter_by_pallet_ids(query, pallet_ids)
    items = _event_rows(session, query)
    return {"items": items, "total": len(items)}


@router.get("/exceptions/{exception_id}")
def exception_detail(exception_id: int, user: Annotated[User, Depends(viewer)], session: Annotated[Session, Depends(get_db)]) -> dict:
    event = session.scalar(_visible_event_query(user).where(ExceptionEvent.id == exception_id))
    if event is None: raise ApiError(status_code=404, code="EXCEPTION_NOT_FOUND", message="La excepción no existe.")
    reading = session.get(InspectionReading, event.reading_id) if event.reading_id else None
    location = session.get(Location, event.location_id) if event.location_id else None
    expected = session.get(Pallet, reading.expected_pallet_id_at_inspection) if reading and reading.expected_pallet_id_at_inspection else None
    observed = session.get(Pallet, reading.observed_pallet_id) if reading and reading.observed_pallet_id else None
    pallet = observed or (session.get(Pallet, event.pallet_id) if event.pallet_id else None)
    lot = session.get(Lot, pallet.lot_id) if pallet else None
    product = session.get(Product, lot.product_id) if lot else None
    days = (lot.expires_at - date.today()).days if lot else None
    settings = load_business_rule_settings()
    rotation = product_rotation_from_history(session=session, product_id=product.id, reference_at=datetime.now(timezone.utc), settings=settings) if product else None
    coverage = product_coverage_from_history(session=session, product_id=product.id, reference_at=datetime.now(timezone.utc), settings=settings) if product else None
    fefo = fefo_for_outbound_lot(session=session, outbound_lot_id=lot.id) if lot else None
    attempts = session.scalars(select(InspectionReading).where(InspectionReading.reading_group_id == reading.reading_group_id).order_by(InspectionReading.attempt_number)) if reading else []
    return {"id": event.id, "location": location.code if location else None, "type": event.exception_type.value, "severity": event.severity.value, "status": event.status.value, "risk_score": event.risk_score, "risk_breakdown": event.risk_breakdown, "short_reason": event.title, "description": event.description, "expected_pallet": expected.pallet_code if expected else None, "observed_pallet": observed.pallet_code if observed else None, "product": product.name if product else None, "sku": product.sku if product else None, "pallet": pallet.pallet_code if pallet else None, "lot": lot.lot_code if lot else None, "quantity": pallet.quantity if pallet else None, "expiration_date": lot.expires_at if lot else None, "days_to_expiry": days, "quality_score": reading.quality_score if reading else None, "comparison_result": reading.comparison_result.value if reading else None, "reading_status": reading.reading_status.value if reading else None, "attempt_number": reading.attempt_number if reading else None, "rotation": rotation.level.value if rotation else None, "rotation_30d": rotation.outbound_quantity if rotation else None, "coverage_days": coverage.coverage_days if coverage else None, "coverage_status": coverage.status.value if coverage else None, "fefo_risk": fefo.risk if fefo else False, "fefo_reason": fefo.reason if fefo else None, "rescan_attempts": [{"attempt_number": x.attempt_number, "quality_score": x.quality_score, "status": x.reading_status.value, "evidence_count": len(x.evidence_files)} for x in attempts], "evidence": [{"id": x.id, "type": x.evidence_type.value, "captured_at": x.captured_at} for x in (reading.evidence_files if reading else [])]}
