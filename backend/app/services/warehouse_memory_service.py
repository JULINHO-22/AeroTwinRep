"""Derived, read-only Warehouse Memory built from existing operational records.

The physical history is intentionally based on final readings only. Re-scan
attempts and individual evidence files never create extra history entries or
inflate recurrence counts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.settings import load_business_rule_settings
from app.models.enums import (
    ComparisonResult,
    ExceptionStatus,
    ObservedState,
    ReadingStatus,
    Severity,
)
from app.models.inspection import EvidenceFile, Inspection, InspectionReading
from app.models.operations import ExceptionEvent, FlowTwinChange
from app.models.warehouse import Location, Lot, Pallet, Product, WarehouseZone
from app.services.inventory_analytics import (
    fefo_for_outbound_lot,
    product_coverage_from_history,
    product_rotation_from_history,
)


# One central definition for derived memory. A location with no accepted
# reading is never marked stale merely because it has no timestamp.
STALE_AFTER_DAYS = 7
PHYSICAL_DISCREPANCIES = {
    ComparisonResult.PALLET_MISMATCH,
    ComparisonResult.EXPECTED_PALLET_MISSING,
    ComparisonResult.UNEXPECTED_PALLET,
}


def _final_readings(session: Session, location_id: int) -> list[InspectionReading]:
    return session.scalars(
        select(InspectionReading)
        .where(
            InspectionReading.location_id == location_id,
            InspectionReading.is_final.is_(True),
        )
        .order_by(InspectionReading.created_at.desc(), InspectionReading.id.desc())
    ).all()


def _latest_by_inspection(readings: Iterable[InspectionReading]) -> list[InspectionReading]:
    """Keep one final physical result per inspection/location.

    The database protects normal data from duplicates. This defensive step
    keeps legacy malformed groups from being counted twice in Warehouse Memory.
    """

    by_inspection: dict[int, InspectionReading] = {}
    for reading in readings:
        by_inspection.setdefault(reading.inspection_id, reading)
    return list(by_inspection.values())


def _physical_family(reading: InspectionReading) -> str | None:
    return (
        reading.comparison_result.value
        if reading.comparison_result in PHYSICAL_DISCREPANCIES
        else None
    )


def _recurrence(readings: list[InspectionReading]) -> tuple[str | None, int, list[InspectionReading]]:
    """Return the current same-family discrepancy streak.

    A different discrepancy family or a correct/unresolved reading ends the
    streak. This prevents PALLET_MISMATCH -> EXPECTED_PALLET_MISSING from
    being reported as one recurrent condition.
    """

    family = _physical_family(readings[0]) if readings else None
    if family is None:
        return None, 0, []

    members: list[InspectionReading] = []
    for reading in readings:
        if _physical_family(reading) != family:
            break
        members.append(reading)
    return family, len(members), members


def _public_evidence(row: EvidenceFile | None, location_code: str | None = None) -> dict | None:
    if row is None:
        return None
    value = {
        "evidence_id": row.id,
        "reading_id": row.reading_id,
        "captured_at": row.captured_at,
        "mime_type": row.mime_type,
        "evidence_type": row.evidence_type.value,
    }
    if location_code is not None:
        value["location"] = location_code
    return value


def _event_for_reading(
    events: Iterable[ExceptionEvent], reading: InspectionReading | None
) -> ExceptionEvent | None:
    if reading is None:
        return None
    # Reading linkage is authoritative. The inspection/location fallback
    # supports imported legacy events that pre-date reading linkage.
    direct = [event for event in events if event.reading_id == reading.id]
    candidates = direct or [
        event
        for event in events
        if event.inspection_id == reading.inspection_id
        and event.location_id == reading.location_id
    ]
    return max(candidates, key=lambda event: (event.risk_score, event.id)) if candidates else None


def latest_evidence(session: Session, location: Location) -> dict | None:
    row = session.scalar(
        select(EvidenceFile)
        .join(InspectionReading, EvidenceFile.reading_id == InspectionReading.id)
        .where(
            InspectionReading.location_id == location.id,
            InspectionReading.is_final.is_(True),
        )
        .order_by(EvidenceFile.captured_at.desc(), EvidenceFile.id.desc())
    )
    return _public_evidence(row, location.code)


def _pallet_context(
    session: Session, reading: InspectionReading | None
) -> tuple[Pallet | None, Pallet | None, Lot | None, Product | None]:
    if reading is None:
        return None, None, None, None
    observed = session.get(Pallet, reading.observed_pallet_id) if reading.observed_pallet_id else None
    expected = (
        session.get(Pallet, reading.expected_pallet_id_at_inspection)
        if reading.expected_pallet_id_at_inspection
        else None
    )
    # When a location is empty/unresolved, expected inventory still gives the
    # supervisor usable product context. It is labelled as expected below.
    selected = observed or expected
    lot = session.get(Lot, selected.lot_id) if selected else None
    product = session.get(Product, lot.product_id) if lot else None
    return observed, expected, lot, product


def location_memory(session: Session, location: Location) -> dict:
    readings = _latest_by_inspection(_final_readings(session, location.id))
    events = session.scalars(
        select(ExceptionEvent)
        .where(ExceptionEvent.location_id == location.id)
        .order_by(ExceptionEvent.created_at.desc(), ExceptionEvent.id.desc())
    ).all()
    latest = readings[0] if readings else None
    last_valid = next(
        (reading for reading in readings if reading.reading_status == ReadingStatus.ACCEPTED),
        None,
    )
    family, streak, streak_members = _recurrence(readings)
    current_event = _event_for_reading(events, latest)
    observed, expected, lot, product = _pallet_context(session, latest)
    now = datetime.now(timezone.utc)

    rotation = coverage = fefo = None
    if product is not None:
        settings = load_business_rule_settings()
        rotation = product_rotation_from_history(
            session=session, product_id=product.id, reference_at=now, settings=settings
        )
        coverage = product_coverage_from_history(
            session=session, product_id=product.id, reference_at=now, settings=settings
        )
    if lot is not None:
        fefo = fefo_for_outbound_lot(session=session, outbound_lot_id=lot.id)

    valid_at = last_valid.created_at if last_valid else None
    days_since_valid = (now - valid_at).days if valid_at else None
    is_unresolved = bool(
        latest
        and (
            latest.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED
            or latest.observed_state == ObservedState.UNRESOLVED
            or latest.comparison_result == ComparisonResult.UNRESOLVED
        )
    )
    zone = session.get(WarehouseZone, location.zone_id)
    history_risks = [event.risk_score for event in events]
    recent_changes = session.scalars(
        select(FlowTwinChange)
        .where(FlowTwinChange.location_id == location.id)
        .order_by(FlowTwinChange.created_at.desc(), FlowTwinChange.id.desc())
        .limit(5)
    ).all()

    return {
        "location_id": location.id,
        "code": location.code,
        "zone_id": location.zone_id,
        "zone": zone.code if zone else None,
        "total_inspections": len(readings),
        "total_final_readings": len(readings),
        "total_exceptions": len(events),
        "open_exceptions": sum(
            event.status in (ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW)
            for event in events
        ),
        "resolved_exceptions": sum(
            event.status == ExceptionStatus.RESOLVED for event in events
        ),
        "last_reading_id": latest.id if latest else None,
        "last_inspection_id": latest.inspection_id if latest else None,
        "last_valid_reading": valid_at,
        "last_observed_pallet": observed.pallet_code if observed else None,
        "last_observed_pallet_id": observed.id if observed else None,
        "expected_pallet": expected.pallet_code if expected else None,
        "expected_pallet_id": expected.id if expected else None,
        "last_comparison_result": latest.comparison_result.value if latest else None,
        "last_reading_status": latest.reading_status.value if latest else None,
        "last_observed_state": latest.observed_state.value if latest else None,
        "last_quality_score": latest.quality_score if latest else None,
        "last_risk_score": current_event.risk_score if current_event else 0,
        "last_severity": current_event.severity.value if current_event else None,
        "current_exception_id": current_event.id if current_event else None,
        "current_exception_type": current_event.exception_type.value if current_event else None,
        "current_exception_status": current_event.status.value if current_event else None,
        "max_historical_risk": max(history_risks, default=0),
        "avg_historical_risk": round(sum(history_risks) / len(history_risks), 1)
        if history_risks
        else 0,
        "risk_breakdown": current_event.risk_breakdown if current_event else {},
        "recurrent_anomaly_type": family if streak >= 2 else None,
        "consecutive_anomalous_inspections": streak,
        "first_anomaly_date": streak_members[-1].created_at if streak_members else None,
        "latest_anomaly_date": streak_members[0].created_at if streak_members else None,
        "is_never_inspected": latest is None,
        "is_unresolved": is_unresolved,
        "is_stale": bool(days_since_valid is not None and days_since_valid > STALE_AFTER_DAYS),
        "days_since_last_valid_inspection": days_since_valid,
        "product": product.name if product else None,
        "product_id": product.id if product else None,
        "product_context": "OBSERVED" if observed else ("EXPECTED" if expected else None),
        "sku": product.sku if product else None,
        "lot": lot.lot_code if lot else None,
        "lot_id": lot.id if lot else None,
        "quantity": (observed or expected).quantity if (observed or expected) else None,
        "expiration_date": lot.expires_at if lot else None,
        "days_to_expiry": (lot.expires_at - now.date()).days if lot else None,
        "rotation": rotation.level.value if rotation else None,
        "rotation_outbound_quantity": rotation.outbound_quantity if rotation else None,
        "coverage_days": coverage.coverage_days if coverage else None,
        "coverage_status": coverage.status.value if coverage else None,
        "fefo_risk": fefo.risk if fefo else False,
        "fefo_preferred_lot": fefo.preferred_lot if fefo else None,
        "fefo_reason": fefo.reason if fefo else None,
        "recent_changes": [
            {"id": row.id, "type": row.change_type.value, "created_at": row.created_at}
            for row in recent_changes
        ],
        "latest_evidence": latest_evidence(session, location),
    }


def get_location_history(session: Session, location: Location) -> list[dict]:
    """Return a human-operational timeline of final readings for a location."""

    readings = _latest_by_inspection(_final_readings(session, location.id))
    if not readings:
        return []

    reading_ids = [reading.id for reading in readings]
    inspection_ids = [reading.inspection_id for reading in readings]
    pallet_ids = {
        pallet_id
        for reading in readings
        for pallet_id in (
            reading.observed_pallet_id,
            reading.expected_pallet_id_at_inspection,
        )
        if pallet_id is not None
    }
    inspections = {
        row.id: row
        for row in session.scalars(select(Inspection).where(Inspection.id.in_(inspection_ids))).all()
    }
    pallets = (
        {
            row.id: row
            for row in session.scalars(select(Pallet).where(Pallet.id.in_(pallet_ids))).all()
        }
        if pallet_ids
        else {}
    )
    events = session.scalars(
        select(ExceptionEvent)
        .where(
            ExceptionEvent.location_id == location.id,
            (
                ExceptionEvent.reading_id.in_(reading_ids)
                | ExceptionEvent.inspection_id.in_(inspection_ids)
            ),
        )
        .order_by(ExceptionEvent.risk_score.desc(), ExceptionEvent.id.desc())
    ).all()
    evidence_rows = session.scalars(
        select(EvidenceFile)
        .where(EvidenceFile.reading_id.in_(reading_ids))
        .order_by(EvidenceFile.captured_at.desc(), EvidenceFile.id.desc())
    ).all()
    evidence_by_reading: dict[int, EvidenceFile] = {}
    for evidence in evidence_rows:
        evidence_by_reading.setdefault(evidence.reading_id, evidence)
    change_rows = session.scalars(
        select(FlowTwinChange)
        .where(
            FlowTwinChange.location_id == location.id,
            FlowTwinChange.current_inspection_id.in_(inspection_ids),
        )
        .order_by(FlowTwinChange.created_at.desc(), FlowTwinChange.id.desc())
    ).all()
    changes_by_inspection: dict[int, FlowTwinChange] = {}
    for change in change_rows:
        changes_by_inspection.setdefault(change.current_inspection_id, change)

    timeline: list[dict] = []
    for reading in readings:
        inspection = inspections.get(reading.inspection_id)
        event = _event_for_reading(events, reading)
        evidence = evidence_by_reading.get(reading.id)
        change = changes_by_inspection.get(reading.inspection_id)
        completed_at = inspection.completed_at if inspection else None
        inspection_date = completed_at or reading.created_at
        timeline.append(
            {
                "reading_id": reading.id,
                "inspection_id": reading.inspection_id,
                "inspection_date": inspection_date,
                "inspection_completed_at": completed_at,
                "completed_at": completed_at,
                "observed_pallet": pallets.get(reading.observed_pallet_id).pallet_code
                if reading.observed_pallet_id in pallets
                else None,
                "observed_pallet_id": reading.observed_pallet_id,
                "expected_pallet": pallets.get(reading.expected_pallet_id_at_inspection).pallet_code
                if reading.expected_pallet_id_at_inspection in pallets
                else None,
                "expected_pallet_id": reading.expected_pallet_id_at_inspection,
                "comparison_result": reading.comparison_result.value,
                "reading_status": reading.reading_status.value,
                "risk_score": event.risk_score if event else 0,
                "severity": event.severity.value if event else None,
                "exception_type": event.exception_type.value if event else None,
                "exception_id": event.id if event else None,
                "evidence_id": evidence.id if evidence else None,
                "evidence": _public_evidence(evidence, location.code),
                "flowtwin_change": {
                    "id": change.id,
                    "type": change.change_type.value,
                    "created_at": change.created_at,
                }
                if change
                else None,
            }
        )
    return timeline


def location_list(session: Session) -> list[dict]:
    # The per-location analytics are intentionally server-side. The inventory
    # is small in the MVP; this keeps the public contract accurate while the
    # endpoint returns only one lightweight summary per location.
    rows = [
        location_memory(session, location)
        for location in session.scalars(select(Location).order_by(Location.code)).all()
    ]
    return sorted(
        rows,
        key=lambda row: (
            row["open_exceptions"] == 0,
            -row["consecutive_anomalous_inspections"],
            -row["last_risk_score"],
            row["code"],
        ),
    )


def zone_memory(session: Session, zone: WarehouseZone) -> dict:
    locations = [
        location_memory(session, location)
        for location in session.scalars(
            select(Location).where(Location.zone_id == zone.id).order_by(Location.code)
        ).all()
    ]
    location_ids = [row["location_id"] for row in locations]
    open_events = (
        session.scalars(
            select(ExceptionEvent)
            .where(
                ExceptionEvent.location_id.in_(location_ids),
                ExceptionEvent.status.in_((ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW)),
            )
            .order_by(ExceptionEvent.risk_score.desc(), ExceptionEvent.id.desc())
        ).all()
        if location_ids
        else []
    )
    recent_changes = session.scalars(
        select(FlowTwinChange)
        .join(Location, FlowTwinChange.location_id == Location.id)
        .where(Location.zone_id == zone.id)
        .order_by(FlowTwinChange.created_at.desc(), FlowTwinChange.id.desc())
        .limit(5)
    ).all()

    # `*_exceptions` deliberately counts open/in-review ExceptionEvent rows,
    # not locations. `average_risk` is the average risk_score of that same open
    # operational exception set.
    open_risks = [event.risk_score for event in open_events]
    return {
        "zone_id": zone.id,
        "zone": zone.code,
        "inspections_count": session.scalar(
            select(func.count()).select_from(Inspection).where(Inspection.zone_id == zone.id)
        )
        or 0,
        "locations_count": len(locations),
        "inspected_locations": sum(not row["is_never_inspected"] for row in locations),
        "never_inspected_locations": sum(row["is_never_inspected"] for row in locations),
        "stale_locations": sum(row["is_stale"] for row in locations),
        "unresolved_locations": sum(row["is_unresolved"] for row in locations),
        "locations_with_anomalies": sum(
            row["last_comparison_result"]
            in {result.value for result in PHYSICAL_DISCREPANCIES}
            for row in locations
        ),
        "recurring_locations": sum(
            row["consecutive_anomalous_inspections"] >= 2 for row in locations
        ),
        "open_exceptions": len(open_events),
        "high_exceptions": sum(event.severity == Severity.HIGH for event in open_events),
        "critical_exceptions": sum(
            event.severity == Severity.CRITICAL for event in open_events
        ),
        "average_risk": round(sum(open_risks) / len(open_risks), 1) if open_risks else 0,
        "max_risk": max(open_risks, default=0),
        "risk_aggregation": "OPEN_OR_IN_REVIEW_EXCEPTION_EVENTS",
        "recent_flowtwin_changes": [
            {
                "id": change.id,
                "location_id": change.location_id,
                "type": change.change_type.value,
                "at": change.created_at,
            }
            for change in recent_changes
        ],
    }
