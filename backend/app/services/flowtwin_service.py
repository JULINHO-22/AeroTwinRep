"""Temporal comparison engine built from final inspection readings, not snapshots."""
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ComparisonResult, FlowTwinChangeType, InspectionStatus, ObservedState, ReadingStatus
from app.models.inspection import Inspection, InspectionReading
from app.models.operations import ExceptionEvent, FlowTwinChange

PHYSICAL = {ComparisonResult.PALLET_MISMATCH, ComparisonResult.EXPECTED_PALLET_MISSING, ComparisonResult.UNEXPECTED_PALLET}

@dataclass
class FlowChange:
    location_id: int; type: FlowTwinChangeType; previous: InspectionReading; current: InspectionReading

def previous_comparable(session: Session, current: Inspection) -> Inspection | None:
    return session.scalar(select(Inspection).where(Inspection.zone_id == current.zone_id, Inspection.status == InspectionStatus.COMPLETED, Inspection.completed_at < current.completed_at).order_by(Inspection.completed_at.desc()))

def _finals(session: Session, inspection_id: int) -> dict[int, InspectionReading]:
    # Final unique group reads; if historical malformed data has several groups, latest wins.
    rows = session.scalars(select(InspectionReading).where(InspectionReading.inspection_id == inspection_id, InspectionReading.is_final.is_(True)).order_by(InspectionReading.created_at.desc())).all()
    return {row.location_id: row for row in rows}

def classify(previous: InspectionReading, current: InspectionReading) -> FlowTwinChangeType | None:
    previous_unresolved = previous.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED or previous.observed_state == ObservedState.UNRESOLVED
    current_unresolved = current.reading_status == ReadingStatus.HUMAN_REVIEW_REQUIRED or current.observed_state == ObservedState.UNRESOLVED
    if current_unresolved and not previous_unresolved:
        return FlowTwinChangeType.BECAME_UNRESOLVED
    if previous_unresolved and not current_unresolved:
        return FlowTwinChangeType.RESOLVED_SINCE_PREVIOUS
    if previous.observed_state == ObservedState.PALLET and current.observed_state == ObservedState.EMPTY and current.empty_confirmed_by_operator:
        return FlowTwinChangeType.PALLET_REMOVED
    if previous.observed_state == ObservedState.EMPTY and previous.empty_confirmed_by_operator and current.observed_state == ObservedState.PALLET:
        return FlowTwinChangeType.PALLET_ADDED
    if previous.observed_pallet_id != current.observed_pallet_id and current.observed_state == ObservedState.PALLET:
        return FlowTwinChangeType.PALLET_CHANGED
    if previous.expected_pallet_id_at_inspection != current.expected_pallet_id_at_inspection:
        return FlowTwinChangeType.EXPECTED_CHANGED
    if previous.comparison_result in PHYSICAL and current.comparison_result in PHYSICAL and previous.comparison_result == current.comparison_result:
        return FlowTwinChangeType.PERSISTENT_DISCREPANCY
    return None

def calculate(session: Session, current: Inspection) -> tuple[Inspection | None, list[FlowChange], int]:
    previous = previous_comparable(session, current)
    if not previous: return None, [], 0
    old, new = _finals(session, previous.id), _finals(session, current.id)
    changes = [FlowChange(location, kind, old[location], row) for location, row in new.items() if location in old and (kind := classify(old[location], row))]
    unchanged = sum(1 for loc, row in new.items() if loc in old and classify(old[loc], row) is None)
    return previous, changes, unchanged

def persist(session: Session, current: Inspection) -> tuple[Inspection | None, list[FlowChange], int]:
    previous, changes, unchanged = calculate(session, current)
    if not previous: return previous, changes, unchanged
    existing = {(x.location_id, x.change_type) for x in session.scalars(select(FlowTwinChange).where(FlowTwinChange.current_inspection_id == current.id, FlowTwinChange.previous_inspection_id == previous.id))}
    for change in changes:
        if (change.location_id, change.type) not in existing:
            session.add(FlowTwinChange(current_inspection_id=current.id, previous_inspection_id=previous.id, location_id=change.location_id, change_type=change.type, previous_pallet_id=change.previous.observed_pallet_id, current_pallet_id=change.current.observed_pallet_id, previous_result=change.previous.comparison_result, current_result=change.current.comparison_result, description=f"{change.type.value} detectado entre inspecciones."))
    session.flush()
    return previous, changes, unchanged

def exception_for(session: Session, reading_id: int, inspection_id: int, location_id: int):
    event = session.scalar(select(ExceptionEvent).where(ExceptionEvent.reading_id == reading_id).order_by(ExceptionEvent.risk_score.desc()))
    return event or session.scalar(select(ExceptionEvent).where(ExceptionEvent.inspection_id == inspection_id, ExceptionEvent.location_id == location_id).order_by(ExceptionEvent.risk_score.desc()))
