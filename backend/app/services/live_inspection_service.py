"""Small, Core-owned projection for the live warehouse twin.

The projection deliberately has no persistence and does not make a client a
source of truth.  A candidate QR is telemetry only; the physical state and
coverage change exclusively after :class:`InspectionReading` is final.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.analytics import (
    CoverageStatus,
    RotationLevel,
    analyze_excess_expiry_risk,
)
from app.domain.settings import load_business_rule_settings
from app.models.enums import ComparisonResult, ObservedState, ReadingStatus
from app.models.identity import SensorDevice
from app.models.inspection import EvidenceFile, Inspection, InspectionReading
from app.models.operations import ExceptionEvent
from app.models.warehouse import ExpectedInventory, Location, Lot, Pallet, Product, WarehouseZone
from app.services.inventory_analytics import (
    fefo_for_outbound_lot,
    product_coverage_from_history,
    product_rotation_from_history,
)
from app.services.sensor_live import live_telemetry
from app.services.warehouse_memory_service import STALE_AFTER_DAYS


PHYSICAL_DISCREPANCIES = {
    ComparisonResult.PALLET_MISMATCH,
    ComparisonResult.EXPECTED_PALLET_MISSING,
    ComparisonResult.UNEXPECTED_PALLET,
}

_RESULT_LABELS = {
    ComparisonResult.CORRECT: "Pallet correcto",
    ComparisonResult.CORRECT_EMPTY: "Vacío confirmado",
    ComparisonResult.PALLET_MISMATCH: "Pallet diferente",
    ComparisonResult.EXPECTED_PALLET_MISSING: "Pallet esperado no encontrado",
    ComparisonResult.UNEXPECTED_PALLET: "Pallet no esperado",
    ComparisonResult.UNRESOLVED: "No resuelto",
}


@dataclass(frozen=True)
class LocationSignals:
    """Analytics already computed by Core for one live twin cell."""

    badges: list[str]
    loss_prevention_signal: str | None
    loss_prevention_reason: str | None
    slotting_suggestion: str | None
    lot: str | None
    days_to_expiry: int | None
    rotation: str | None
    coverage_days: float | None
    fefo_risk: bool


def _latest_by_location(rows: Iterable[InspectionReading]) -> dict[int, InspectionReading]:
    """Keep the latest row for every location after a deterministic ordering."""

    result: dict[int, InspectionReading] = {}
    for row in rows:
        result.setdefault(row.location_id, row)
    return result


def _latest_by_inspection(rows: Iterable[InspectionReading]) -> list[InspectionReading]:
    """Defensively collapse legacy multiple final groups per inspection/location."""

    result: dict[int, InspectionReading] = {}
    for row in rows:
        result.setdefault(row.inspection_id, row)
    return list(result.values())


def _physical_family(row: InspectionReading | None) -> ComparisonResult | None:
    if row is None or row.comparison_result not in PHYSICAL_DISCREPANCIES:
        return None
    return row.comparison_result


def _recurrence(rows: list[InspectionReading]) -> int:
    """Count the current same-family physical discrepancy streak."""

    family = _physical_family(rows[0]) if rows else None
    if family is None:
        return 0
    count = 0
    for row in rows:
        if _physical_family(row) != family:
            break
        count += 1
    return count


def _scanning_location_ids(session: Session, inspection_id: int) -> set[int]:
    """Map a recent LOC telemetry value to an active location in the mission.

    Android has sent both ``LOC:A-01-01`` and the normalized ``A-01-01`` over
    the course of the MVP, so both forms are intentionally accepted here.
    Telemetry expires in ``LiveTelemetryStore`` and never becomes a reading.
    """

    location_by_code = {
        location.code.upper(): location.id
        for location in session.scalars(
            select(Location).join(Inspection, Location.zone_id == Inspection.zone_id).where(
                Inspection.id == inspection_id,
                Location.is_active.is_(True),
            )
        ).all()
    }
    if not location_by_code:
        return set()

    scanning: set[int] = set()
    sensor_ids = session.scalars(
        select(SensorDevice.id).where(SensorDevice.assigned_inspection_id == inspection_id)
    ).all()
    for sensor_id in sensor_ids:
        telemetry = live_telemetry.get(sensor_id, inspection_id)
        if telemetry is None or not telemetry.detected_code:
            continue
        code = telemetry.detected_code.strip().upper()
        if code.startswith("LOC:"):
            code = code[4:]
        location_id = location_by_code.get(code)
        if location_id is not None:
            scanning.add(location_id)
    return scanning


def _historical_rows_by_location(
    session: Session, location_ids: list[int]
) -> dict[int, list[InspectionReading]]:
    """Return newest final physical result per historical inspection/location."""

    rows = session.scalars(
        select(InspectionReading)
        .where(
            InspectionReading.location_id.in_(location_ids),
            InspectionReading.is_final.is_(True),
        )
        .order_by(
            InspectionReading.location_id,
            InspectionReading.created_at.desc(),
            InspectionReading.id.desc(),
        )
    ).all()
    grouped: dict[int, list[InspectionReading]] = defaultdict(list)
    by_location_and_inspection: set[tuple[int, int]] = set()
    for row in rows:
        key = (row.location_id, row.inspection_id)
        if key in by_location_and_inspection:
            continue
        by_location_and_inspection.add(key)
        grouped[row.location_id].append(row)
    return grouped


def _event_maps(
    session: Session, inspection_id: int, final_rows: Iterable[InspectionReading]
) -> tuple[dict[int, ExceptionEvent], dict[int, ExceptionEvent]]:
    """Index current events by reading and location without inventing risk data."""

    final_rows = list(final_rows)
    reading_ids = [row.id for row in final_rows]
    location_ids = [row.location_id for row in final_rows]
    if not reading_ids:
        return {}, {}
    rows = session.scalars(
        select(ExceptionEvent)
        .where(
            ExceptionEvent.inspection_id == inspection_id,
            ExceptionEvent.location_id.in_(location_ids),
        )
        .order_by(ExceptionEvent.risk_score.desc(), ExceptionEvent.id.desc())
    ).all()
    by_reading: dict[int, ExceptionEvent] = {}
    by_location: dict[int, ExceptionEvent] = {}
    for event in rows:
        if event.reading_id is not None:
            by_reading.setdefault(event.reading_id, event)
        if event.location_id is not None:
            by_location.setdefault(event.location_id, event)
    return by_reading, by_location


def _evidence_map(session: Session, reading_ids: list[int]) -> dict[int, EvidenceFile]:
    if not reading_ids:
        return {}
    rows = session.scalars(
        select(EvidenceFile)
        .where(EvidenceFile.reading_id.in_(reading_ids))
        .order_by(EvidenceFile.captured_at.desc(), EvidenceFile.id.desc())
    ).all()
    result: dict[int, EvidenceFile] = {}
    for row in rows:
        result.setdefault(row.reading_id, row)
    return result


def _pallet_contexts(
    session: Session, pallet_ids: set[int]
) -> dict[int, tuple[Pallet, Lot, Product]]:
    if not pallet_ids:
        return {}
    rows = session.execute(
        select(Pallet, Lot, Product)
        .join(Lot, Pallet.lot_id == Lot.id)
        .join(Product, Lot.product_id == Product.id)
        .where(Pallet.id.in_(pallet_ids))
    ).all()
    return {pallet.id: (pallet, lot, product) for pallet, lot, product in rows}


def _expected_by_location(
    session: Session, location_ids: list[int]
) -> dict[int, int | None]:
    rows = session.scalars(
        select(ExpectedInventory).where(ExpectedInventory.location_id.in_(location_ids))
    ).all()
    return {row.location_id: row.expected_pallet_id for row in rows}


def _analytics_for_product(
    *,
    session: Session,
    product: Product,
    lot: Lot,
    now: datetime,
    settings,
    cache: dict[int, tuple[object, object]],
    fefo_cache: dict[int, object],
):
    if product.id not in cache:
        cache[product.id] = (
            product_rotation_from_history(
                session=session, product_id=product.id, reference_at=now, settings=settings
            ),
            product_coverage_from_history(
                session=session, product_id=product.id, reference_at=now, settings=settings
            ),
        )
    if lot.id not in fefo_cache:
        fefo_cache[lot.id] = fefo_for_outbound_lot(session=session, outbound_lot_id=lot.id)
    return (*cache[product.id], fefo_cache[lot.id])


def _badges_and_signals(
    *,
    session: Session,
    product: Product | None,
    lot: Lot | None,
    location: Location,
    now: datetime,
    settings,
    analytics_cache: dict[int, tuple[object, object]],
    fefo_cache: dict[int, object],
    recurrent: bool,
) -> LocationSignals:
    """Return lightweight, explainable secondary signals for a cell."""

    badges: list[str] = ["RECURRENTE"] if recurrent else []
    if product is None or lot is None:
        return LocationSignals(
            badges=badges,
            loss_prevention_signal=None,
            loss_prevention_reason=None,
            slotting_suggestion=None,
            lot=None,
            days_to_expiry=None,
            rotation=None,
            coverage_days=None,
            fefo_risk=False,
        )

    rotation, coverage, fefo = _analytics_for_product(
        session=session,
        product=product,
        lot=lot,
        now=now,
        settings=settings,
        cache=analytics_cache,
        fefo_cache=fefo_cache,
    )
    days_to_expiry = (lot.expires_at - now.date()).days
    if days_to_expiry <= settings.expiry_risk_days:
        badges.append("CADUCIDAD")
    if fefo.risk:
        badges.append("FEFO")
    if coverage.status is CoverageStatus.LOW_COVERAGE:
        badges.append("COBERTURA_BAJA")

    prevention = analyze_excess_expiry_risk(
        coverage_days=coverage.coverage_days,
        days_to_expiry=days_to_expiry,
    )
    signal = reason = None
    if prevention.excess_expiry_risk:
        badges.append("EXCESO")
        signal = "EXCESS_EXPIRY_RISK"
        reason = prevention.reason

    slotting = None
    if rotation.level is RotationLevel.HIGH and location.level > 1:
        slotting = (
            "Producto de alta rotación. Revisar una posición de mayor accesibilidad."
        )
    return LocationSignals(
        badges=badges,
        loss_prevention_signal=signal,
        loss_prevention_reason=reason,
        slotting_suggestion=slotting,
        lot=lot.lot_code,
        days_to_expiry=days_to_expiry,
        rotation=rotation.level.value,
        coverage_days=coverage.coverage_days,
        fefo_risk=fefo.risk,
    )


def _next_target(
    *,
    session: Session,
    inspection: Inspection,
    locations: list[Location],
    finals: dict[int, InspectionReading],
    history: dict[int, list[InspectionReading]],
    expected_pallet_ids: dict[int, int | None],
    pallet_context: dict[int, tuple[Pallet, Lot, Product]],
    now: datetime,
    settings,
) -> dict:
    """Select the next *scan* objective; the Core owns the order.

    Final human-review readings count as inspected and deliberately do not send
    the sensor into an endless capture loop.  Re-scan readings are non-final,
    therefore their locations remain candidates and win the queue.
    """

    pending = [location for location in locations if location.id not in finals]
    if not pending:
        return {
            "action": "COMPLETE_MISSION",
            "location_id": None,
            "location_code": None,
            "reason": "Todas las posiciones tienen una lectura final.",
            "priority": 0,
        }

    nonfinal_rows = session.scalars(
        select(InspectionReading)
        .where(
            InspectionReading.inspection_id == inspection.id,
            InspectionReading.location_id.in_([item.id for item in pending]),
            InspectionReading.is_final.is_(False),
        )
        .order_by(InspectionReading.created_at.desc(), InspectionReading.id.desc())
    ).all()
    latest_nonfinal = _latest_by_location(nonfinal_rows)
    analytics_cache: dict[int, tuple[object, object]] = {}
    fefo_cache: dict[int, object] = {}
    candidates: list[tuple[tuple, Location, str]] = []

    for location in pending:
        nonfinal = latest_nonfinal.get(location.id)
        physical_order = (location.row_index, location.column_index, location.level, location.code)
        if nonfinal is not None and nonfinal.reading_status is ReadingStatus.RESCAN_REQUIRED:
            candidates.append(((1, *physical_order), location, "Reintento pendiente por calidad de lectura."))
            continue

        historical = history.get(location.id, [])
        streak = _recurrence(historical)
        if streak >= 2:
            candidates.append(((2, *physical_order), location, "Ubicación con anomalía recurrente."))
            continue

        expected_pallet_id = expected_pallet_ids.get(location.id)
        context = pallet_context.get(expected_pallet_id) if expected_pallet_id else None
        if context is not None:
            _pallet, lot, product = context
            rotation, coverage, fefo = _analytics_for_product(
                session=session,
                product=product,
                lot=lot,
                now=now,
                settings=settings,
                cache=analytics_cache,
                fefo_cache=fefo_cache,
            )
            if (lot.expires_at - now.date()).days <= settings.expiry_risk_days:
                candidates.append(((3, *physical_order), location, "Lote próximo a vencer."))
                continue
            if fefo.risk:
                candidates.append(((3, *physical_order), location, "Riesgo FEFO pendiente de verificación."))
                continue
            if coverage.status is CoverageStatus.LOW_COVERAGE:
                candidates.append(((3, *physical_order), location, "Producto con cobertura baja."))
                continue

        latest_accepted = next(
            (row for row in historical if row.reading_status is ReadingStatus.ACCEPTED),
            None,
        )
        if latest_accepted is not None and (now - latest_accepted.created_at).days > STALE_AFTER_DAYS:
            candidates.append(((4, *physical_order), location, "Ubicación sin validación reciente."))
            continue
        candidates.append(((5, *physical_order), location, "Siguiente posición según recorrido físico."))

    _rank, location, reason = min(candidates, key=lambda item: item[0])
    return {
        # Existing sensor clients already interpret CONTINUE_AUTONOMOUS as a
        # Core directive to move on.  Location and reason make that directive
        # useful to both the phone today and a drone later.
        "action": "CONTINUE_AUTONOMOUS",
        "location_id": location.id,
        "location_code": location.code,
        "reason": reason,
        "priority": 1,
    }


def live_state(session: Session, inspection: Inspection) -> dict:
    """Build the light live projection for an inspection without side effects."""

    zone = session.get(WarehouseZone, inspection.zone_id)
    locations = session.scalars(
        select(Location)
        .where(Location.zone_id == inspection.zone_id, Location.is_active.is_(True))
        .order_by(Location.row_index, Location.column_index, Location.level, Location.code)
    ).all()
    location_ids = [location.id for location in locations]
    final_rows = session.scalars(
        select(InspectionReading)
        .where(
            InspectionReading.inspection_id == inspection.id,
            InspectionReading.is_final.is_(True),
        )
        .order_by(InspectionReading.created_at.desc(), InspectionReading.id.desc())
    ).all()
    finals = _latest_by_location(final_rows)
    inspected = len(finals)
    validated = sum(
        row.reading_status is ReadingStatus.ACCEPTED for row in finals.values()
    )
    review_required = sum(
        row.reading_status is ReadingStatus.HUMAN_REVIEW_REQUIRED
        for row in finals.values()
    )
    pending = max(len(locations) - inspected, 0)
    now = datetime.now(timezone.utc)
    settings = load_business_rule_settings()
    history = _historical_rows_by_location(session, location_ids) if location_ids else {}
    expected_pallet_ids = _expected_by_location(session, location_ids) if location_ids else {}

    pallet_ids = {
        pallet_id
        for row in finals.values()
        for pallet_id in (row.observed_pallet_id, row.expected_pallet_id_at_inspection)
        if pallet_id is not None
    }
    pallet_ids.update(
        pallet_id for pallet_id in expected_pallet_ids.values() if pallet_id is not None
    )
    pallet_context = _pallet_contexts(session, pallet_ids)
    event_by_reading, event_by_location = _event_maps(
        session, inspection.id, finals.values()
    )
    evidence_by_reading = _evidence_map(session, [row.id for row in finals.values()])
    scanning = _scanning_location_ids(session, inspection.id)
    analytics_cache: dict[int, tuple[object, object]] = {}
    fefo_cache: dict[int, object] = {}

    items: list[dict] = []
    for location in locations:
        reading = finals.get(location.id)
        current_expected_id = expected_pallet_ids.get(location.id)
        expected_context = pallet_context.get(current_expected_id) if current_expected_id else None
        observed_context = (
            pallet_context.get(reading.observed_pallet_id)
            if reading is not None and reading.observed_pallet_id is not None
            else None
        )
        selected_context = observed_context or expected_context
        event = (
            event_by_reading.get(reading.id)
            if reading is not None
            else None
        ) or event_by_location.get(location.id)
        evidence = evidence_by_reading.get(reading.id) if reading is not None else None
        historical = history.get(location.id, [])
        recurrent = _recurrence(historical) >= 2
        product = selected_context[2] if selected_context else None
        lot = selected_context[1] if selected_context else None
        signals = _badges_and_signals(
            session=session,
            product=product,
            lot=lot,
            location=location,
            now=now,
            settings=settings,
            analytics_cache=analytics_cache,
            fefo_cache=fefo_cache,
            recurrent=recurrent,
        )
        if reading is None:
            physical_state = "SCANNING" if location.id in scanning else "UNINSPECTED"
        elif (
            reading.reading_status is ReadingStatus.HUMAN_REVIEW_REQUIRED
            or reading.observed_state is ObservedState.UNRESOLVED
            or reading.comparison_result is ComparisonResult.UNRESOLVED
        ):
            physical_state = "REVIEW_REQUIRED"
        elif reading.comparison_result in PHYSICAL_DISCREPANCIES:
            physical_state = "DISCREPANCY"
        else:
            physical_state = "CORRECT"

        expected_pallet = expected_context[0] if expected_context else None
        observed_pallet = observed_context[0] if observed_context else None
        items.append(
            {
                "id": location.id,
                "code": location.code,
                "row_index": location.row_index,
                "column_index": location.column_index,
                "level": location.level,
                "physical_state": physical_state,
                "expected_pallet_code": expected_pallet.pallet_code if expected_pallet else None,
                "observed_pallet_code": observed_pallet.pallet_code if observed_pallet else None,
                "product": product.name if product else None,
                "sku": product.sku if product else None,
                "lot": signals.lot,
                "days_to_expiry": signals.days_to_expiry,
                "rotation": signals.rotation,
                "coverage_days": signals.coverage_days,
                "fefo_risk": signals.fefo_risk,
                "expected_quantity": expected_pallet.quantity if expected_pallet else None,
                # This is intentionally pallet metadata from WMS, not visual count.
                "observed_quantity": observed_pallet.quantity if observed_pallet else None,
                "comparison_result": reading.comparison_result.value if reading else None,
                "result": _RESULT_LABELS[reading.comparison_result] if reading else None,
                "risk_score": event.risk_score if event else 0,
                "severity": event.severity.value if event else None,
                "badges": signals.badges,
                "exception_id": event.id if event else None,
                "evidence_id": evidence.id if evidence else None,
                "loss_prevention_signal": signals.loss_prevention_signal,
                "loss_prevention_reason": signals.loss_prevention_reason,
                "slotting_suggestion": signals.slotting_suggestion,
                "updated_at": reading.created_at if reading else None,
            }
        )

    return {
        "inspection_id": inspection.id,
        "zone": zone.code if zone else "",
        "total": len(locations),
        "inspected": inspected,
        "validated": validated,
        "review_required": review_required,
        "pending": pending,
        "coverage_percent": round((inspected * 100 / len(locations)), 1) if locations else 0.0,
        "last_final_reading": _last_final_response(
            final_rows=final_rows,
            event_by_reading=event_by_reading,
            event_by_location=event_by_location,
            evidence_by_reading=evidence_by_reading,
            locations={location.id: location for location in locations},
            pallets=pallet_context,
        ),
        "current_target": _next_target(
            session=session,
            inspection=inspection,
            locations=locations,
            finals=finals,
            history=history,
            expected_pallet_ids=expected_pallet_ids,
            pallet_context=pallet_context,
            now=now,
            settings=settings,
        ),
        "locations": items,
    }


def _last_final_response(
    *,
    final_rows: list[InspectionReading],
    event_by_reading: dict[int, ExceptionEvent],
    event_by_location: dict[int, ExceptionEvent],
    evidence_by_reading: dict[int, EvidenceFile],
    locations: dict[int, Location],
    pallets: dict[int, tuple[Pallet, Lot, Product]],
) -> dict | None:
    if not final_rows:
        return None
    row = final_rows[0]
    event = event_by_reading.get(row.id) or event_by_location.get(row.location_id)
    observed = pallets.get(row.observed_pallet_id) if row.observed_pallet_id else None
    expected = (
        pallets.get(row.expected_pallet_id_at_inspection)
        if row.expected_pallet_id_at_inspection
        else None
    )
    evidence = evidence_by_reading.get(row.id)
    return {
        "id": row.id,
        "location_id": row.location_id,
        "location_code": locations.get(row.location_id).code if row.location_id in locations else "",
        "reading_status": row.reading_status.value,
        "comparison_result": row.comparison_result.value,
        "expected_pallet_code": expected[0].pallet_code if expected else None,
        "observed_pallet_code": observed[0].pallet_code if observed else None,
        "risk_score": event.risk_score if event else 0,
        "severity": event.severity.value if event else None,
        "exception_id": event.id if event else None,
        "evidence_id": evidence.id if evidence else None,
        "created_at": row.created_at,
    }


def next_objective(session: Session, inspection: Inspection) -> dict:
    """Return only the Core-owned next objective for the Sensor endpoint."""

    # Keep the exact algorithm shared with GET live-state. The live projection
    # is deliberately read-only, so this has no side effect beyond calculation.
    return live_state(session, inspection)["current_target"]
