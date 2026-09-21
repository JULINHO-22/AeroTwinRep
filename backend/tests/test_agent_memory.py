"""Regression coverage for derived Warehouse Memory and the local Agent.

The Agent is a read-only adapter over the derived services.  These tests use
the public API where possible so Android never becomes a second analytics
engine and ReScan attempts cannot contaminate physical history.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    ComparisonResult,
    EvidenceType,
    ExceptionStatus,
    ExceptionType,
    InspectionStatus,
    ObservedState,
    ReadingStatus,
    Severity,
    SourceType,
)
from app.models.inspection import EvidenceFile, Inspection, InspectionReading
from app.models.operations import AgentQueryLog, ExceptionEvent, FlowTwinChange
from app.models.warehouse import Location, Pallet, WarehouseZone
from app.services.agent_service import _params
from app.services.warehouse_memory_service import latest_evidence, location_memory, zone_memory
from tests.test_phase3_api import auth_headers


def ask(client: TestClient, question: str) -> dict:
    response = client.post(
        "/api/v1/agent/query",
        json={"question": question},
        headers=auth_headers(client),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _location(session: Session, code: str) -> Location:
    location = session.scalar(select(Location).where(Location.code == code))
    assert location is not None
    return location


def _pallet_id(session: Session, code: str) -> int:
    pallet = session.scalar(select(Pallet).where(Pallet.pallet_code == code))
    assert pallet is not None
    return pallet.id


def _test_location(session: Session, zone: WarehouseZone, code: str) -> Location:
    location = Location(
        zone_id=zone.id,
        code=code,
        row_index=90,
        column_index=int(code[-2:]),
        level=1,
        description="Ubicación creada por una prueba de memoria.",
    )
    session.add(location)
    session.flush()
    return location


def _final_reading(
    session: Session,
    *,
    location: Location,
    at: datetime,
    comparison: ComparisonResult = ComparisonResult.CORRECT,
    observed_state: ObservedState = ObservedState.PALLET,
    observed_pallet_id: int | None = None,
    expected_pallet_id: int | None = None,
    status: ReadingStatus = ReadingStatus.ACCEPTED,
    empty_confirmed: bool = False,
    is_final: bool = True,
) -> InspectionReading:
    """Create one independently completed inspection reading for history tests."""
    inspection = Inspection(
        zone_id=location.zone_id,
        started_by=1,
        started_at=at - timedelta(minutes=10),
        completed_at=at,
        status=InspectionStatus.COMPLETED,
    )
    session.add(inspection)
    session.flush()
    reading = InspectionReading(
        inspection_id=inspection.id,
        location_id=location.id,
        client_reading_id=uuid4(),
        reading_group_id=uuid4(),
        attempt_number=1,
        expected_pallet_id_at_inspection=expected_pallet_id,
        observed_pallet_id=observed_pallet_id,
        observed_state=observed_state,
        quality_score=91 if status is ReadingStatus.ACCEPTED else 48,
        reading_status=status,
        comparison_result=comparison,
        is_final=is_final,
        created_by=1,
        source_type=SourceType.SEED_SYSTEM,
        empty_confirmed_by_operator=empty_confirmed,
        created_at=at,
    )
    session.add(reading)
    session.flush()
    return reading


@pytest.mark.parametrize(
    ("question", "intent"),
    [
        ("¿Qué debo revisar primero?", "PRIORITY"),
        ("¿Por qué A-01-02 está en rojo?", "LOCATION_STATUS"),
        ("Muéstrame el historial de A-01-02", "LOCATION_HISTORY"),
        ("¿Qué cambió desde ayer?", "RECENT_CHANGES"),
        ("¿Qué vence en 30 días?", "EXPIRY"),
        ("¿Hay riesgo FEFO?", "FEFO"),
        ("¿Qué productos tienen cobertura baja?", "LOW_COVERAGE"),
        ("¿Qué no se pudo resolver?", "UNRESOLVED"),
        ("¿Qué ubicación repite más errores?", "RECURRENT"),
        ("Compara Zona A y Zona B", "COMPARE_ZONES"),
        ("¿Cuál es la última evidencia de A-01-02?", "LATEST_EVIDENCE"),
    ],
)
def test_agent_routes_every_supported_read_only_tool(
    api_client: TestClient, question: str, intent: str
) -> None:
    body = ask(api_client, question)
    assert body["mode"] == "LOCAL"
    assert body["intent"] == intent
    assert "tool" in body
    assert "answer" in body and body["answer"]
    assert isinstance(body["data"], (dict, list))
    assert isinstance(body["sources"], list)
    assert isinstance(body["actions"], list)


def test_agent_parameter_extraction_supports_location_zones_days_and_limit() -> None:
    params = _params("Compara Zona A y Zona B, revisa A-01-02 en 15 días Top 3")
    assert params == {
        "location": "A-01-02",
        "zones": ["A", "B"],
        "days": 15,
        "limit": 3,
    }
    assert _params("Top 99 prioridades")["limit"] == 10


def test_unknown_and_read_only_denied_are_logged_without_operational_writes(
    api_client: TestClient, test_engine
) -> None:
    with Session(test_engine) as session:
        before_logs = session.scalar(select(func.count()).select_from(AgentQueryLog))
        before_readings = session.scalar(select(func.count()).select_from(InspectionReading))
        before_exceptions = session.scalar(select(func.count()).select_from(ExceptionEvent))
        before_changes = session.scalar(select(func.count()).select_from(FlowTwinChange))

    denied = ask(api_client, "Confirma A-01-02 como vacío")
    unknown = ask(api_client, "Escribe un poema sobre el almacén")

    assert denied["intent"] == "READ_ONLY_DENIED"
    assert denied["tool"] is None
    assert "no realiza acciones" in denied["answer"].lower()
    assert unknown["intent"] == "UNKNOWN"
    assert unknown["tool"] is None

    with Session(test_engine) as session:
        assert session.scalar(select(func.count()).select_from(InspectionReading)) == before_readings
        assert session.scalar(select(func.count()).select_from(ExceptionEvent)) == before_exceptions
        assert session.scalar(select(func.count()).select_from(FlowTwinChange)) == before_changes
        logs = session.scalars(
            select(AgentQueryLog).order_by(AgentQueryLog.id.desc()).limit(2)
        ).all()
        assert session.scalar(select(func.count()).select_from(AgentQueryLog)) == before_logs + 2
        assert {row.question for row in logs} == {
            "Confirma A-01-02 como vacío",
            "Escribe un poema sobre el almacén",
        }
        assert all(row.fallback_used for row in logs)
        assert all(row.latency_ms is not None and row.latency_ms >= 0 for row in logs)


def test_inspection_coverage_is_scoped_to_requested_zone(
    api_client: TestClient, test_engine
) -> None:
    with Session(test_engine) as session:
        zone_a = session.scalar(select(WarehouseZone).where(WarehouseZone.code == "A"))
        zone_b = session.scalar(select(WarehouseZone).where(WarehouseZone.code == "B"))
        assert zone_a and zone_b
        now = datetime.now(timezone.utc)
        inspection_a = Inspection(
            zone_id=zone_a.id,
            started_by=1,
            started_at=now - timedelta(minutes=5),
            status=InspectionStatus.IN_PROGRESS,
        )
        # A newer inspection in B must not replace A for a Zone A question.
        inspection_b = Inspection(
            zone_id=zone_b.id,
            started_by=2,
            started_at=now,
            status=InspectionStatus.IN_PROGRESS,
        )
        session.add_all((inspection_a, inspection_b))
        session.commit()
        a_id = inspection_a.id

    body = ask(api_client, "¿Cómo está la cobertura de Zona A?")
    assert body["intent"] == "INSPECTION_COVERAGE"
    assert body["tool"] == "get_inspection_coverage"
    assert body["data"]["inspection_id"] == a_id
    assert body["sources"] == [{"type": "Inspection", "id": a_id}]


def test_inspection_coverage_without_active_requested_zone_is_explicit(
    api_client: TestClient
) -> None:
    body = ask(api_client, "¿Cómo está la cobertura de Zona A?")
    assert body["intent"] == "INSPECTION_COVERAGE"
    assert body["tool"] == "get_inspection_coverage"
    assert body["data"] == {}
    assert "zona a" in body["answer"].lower()
    assert "activa" in body["answer"].lower()


def test_location_history_timeline_is_final_only_and_human_enriched(
    api_client: TestClient, test_engine
) -> None:
    with Session(test_engine) as session:
        location = _location(session, "B-01-01")
        location_id = location.id
        expected_count = session.scalar(
            select(func.count())
            .select_from(InspectionReading)
            .where(
                InspectionReading.location_id == location_id,
                InspectionReading.is_final.is_(True),
            )
        )

    response = api_client.get(
        f"/api/v1/memory/locations/{location_id}", headers=auth_headers(api_client)
    )
    assert response.status_code == 200, response.text
    timeline = response.json()["timeline"]
    assert len(timeline) == expected_count
    required = {
        "inspection_id",
        "inspection_date",
        "completed_at",
        "observed_pallet",
        "expected_pallet",
        "comparison_result",
        "reading_status",
        "risk_score",
        "severity",
        "exception_type",
        "evidence_id",
        "flowtwin_change",
    }
    assert all(required <= set(item) for item in timeline)
    assert all(item["reading_status"] != "RESCAN_REQUIRED" for item in timeline)
    assert all(item["observed_pallet"] in (None, "PAL-006") for item in timeline)

    history = ask(api_client, "Muéstrame el historial de B-01-01")
    assert history["intent"] == "LOCATION_HISTORY"
    assert history["data"]["timeline"] == timeline


def test_location_memory_streaks_last_valid_and_stale_semantics(test_engine) -> None:
    """Streaks are final-reading, same-family temporal facts, never attempt counts."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with Session(test_engine) as session:
        zone = session.scalar(select(WarehouseZone).where(WarehouseZone.code == "A"))
        assert zone is not None
        expected = _pallet_id(session, "PAL-001")
        observed = _pallet_id(session, "PAL-002")

        same = _test_location(session, zone, "A-90-01")
        for days_ago in (3, 2, 1):
            _final_reading(
                session,
                location=same,
                at=now - timedelta(days=days_ago),
                comparison=ComparisonResult.PALLET_MISMATCH,
                observed_pallet_id=observed,
                expected_pallet_id=expected,
            )

        changed_family = _test_location(session, zone, "A-90-02")
        _final_reading(
            session,
            location=changed_family,
            at=now - timedelta(days=2),
            comparison=ComparisonResult.PALLET_MISMATCH,
            observed_pallet_id=observed,
            expected_pallet_id=expected,
        )
        _final_reading(
            session,
            location=changed_family,
            at=now - timedelta(days=1),
            comparison=ComparisonResult.EXPECTED_PALLET_MISSING,
            observed_state=ObservedState.EMPTY,
            observed_pallet_id=None,
            expected_pallet_id=expected,
            empty_confirmed=True,
        )

        corrected = _test_location(session, zone, "A-90-03")
        _final_reading(
            session,
            location=corrected,
            at=now - timedelta(days=2),
            comparison=ComparisonResult.PALLET_MISMATCH,
            observed_pallet_id=observed,
            expected_pallet_id=expected,
        )
        _final_reading(
            session,
            location=corrected,
            at=now - timedelta(days=1),
            comparison=ComparisonResult.CORRECT,
            observed_pallet_id=expected,
            expected_pallet_id=expected,
        )

        unresolved = _test_location(session, zone, "A-90-04")
        accepted = _final_reading(
            session,
            location=unresolved,
            at=now - timedelta(days=2),
            comparison=ComparisonResult.CORRECT,
            observed_pallet_id=expected,
            expected_pallet_id=expected,
        )
        _final_reading(
            session,
            location=unresolved,
            at=now - timedelta(days=1),
            comparison=ComparisonResult.UNRESOLVED,
            observed_state=ObservedState.UNRESOLVED,
            observed_pallet_id=None,
            expected_pallet_id=expected,
            status=ReadingStatus.HUMAN_REVIEW_REQUIRED,
        )
        never = _test_location(session, zone, "A-90-05")
        session.commit()

        same_memory = location_memory(session, same)
        changed_memory = location_memory(session, changed_family)
        corrected_memory = location_memory(session, corrected)
        unresolved_memory = location_memory(session, unresolved)
        zone_data = zone_memory(session, zone)

        assert same_memory["consecutive_anomalous_inspections"] == 3
        assert same_memory["recurrent_anomaly_type"] == "PALLET_MISMATCH"
        assert changed_memory["consecutive_anomalous_inspections"] == 1
        assert changed_memory["recurrent_anomaly_type"] is None
        assert corrected_memory["consecutive_anomalous_inspections"] == 0
        assert unresolved_memory["last_valid_reading"] == accepted.created_at
        assert unresolved_memory["last_comparison_result"] == "UNRESOLVED"
        assert never.id
        # Never-inspected and currently unresolved are neither stale by default.
        assert zone_data["never_inspected_locations"] >= 1
        assert zone_data["unresolved_locations"] >= 1
        assert zone_data["stale_locations"] == 0


def test_zone_exception_counts_use_open_exception_severity_not_location_risk(test_engine) -> None:
    with Session(test_engine) as session:
        zone = WarehouseZone(code="T", name="Zona de pruebas", description="Semántica")
        session.add(zone)
        session.flush()
        one = _test_location(session, zone, "T-90-01")
        two = _test_location(session, zone, "T-90-02")
        common = dict(
            exception_type=ExceptionType.LOW_QUALITY,
            title="Excepción de prueba",
            description="No depende del riesgo de la última ubicación.",
            risk_breakdown={"LOW_QUALITY": 10},
        )
        session.add_all(
            (
                ExceptionEvent(
                    location_id=one.id,
                    severity=Severity.HIGH,
                    status=ExceptionStatus.OPEN,
                    risk_score=60,
                    **common,
                ),
                ExceptionEvent(
                    location_id=two.id,
                    severity=Severity.CRITICAL,
                    status=ExceptionStatus.IN_REVIEW,
                    risk_score=82,
                    **common,
                ),
                ExceptionEvent(
                    location_id=two.id,
                    severity=Severity.CRITICAL,
                    status=ExceptionStatus.RESOLVED,
                    risk_score=90,
                    **common,
                ),
            )
        )
        session.commit()
        data = zone_memory(session, zone)

    assert data["open_exceptions"] == 2
    assert data["high_exceptions"] == 1
    assert data["critical_exceptions"] == 1


def test_latest_evidence_and_unresolved_tool_are_grounded(
    test_engine, api_client: TestClient
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with Session(test_engine) as session:
        zone = session.scalar(select(WarehouseZone).where(WarehouseZone.code == "A"))
        assert zone is not None
        location = _test_location(session, zone, "A-90-06")
        expected = _pallet_id(session, "PAL-001")
        reading = _final_reading(
            session,
            location=location,
            at=now,
            comparison=ComparisonResult.UNRESOLVED,
            observed_state=ObservedState.UNRESOLVED,
            expected_pallet_id=expected,
            status=ReadingStatus.HUMAN_REVIEW_REQUIRED,
        )
        evidence = EvidenceFile(
            reading_id=reading.id,
            file_path=f"tests/{uuid4()}.jpg",
            mime_type="image/jpeg",
            source_type=SourceType.SEED_SYSTEM,
            evidence_type=EvidenceType.MANUAL_REVIEW,
            captured_at=now,
            checksum="a" * 64,
            width=8,
            height=6,
        )
        session.add(evidence)
        session.commit()
        expected_evidence_id = evidence.id
        reading_id = reading.id

        latest = latest_evidence(session, location)
        assert latest is not None
        assert latest["evidence_id"] == expected_evidence_id
        assert latest["reading_id"] == reading_id

    body = ask(api_client, "¿Qué no se pudo resolver?")
    assert body["intent"] == "UNRESOLVED"
    item = next(row for row in body["data"] if row["reading_id"] == reading_id)
    assert item["location"] == "A-90-06"
    assert {"inspection_id", "attempts", "quality", "reason", "latest_evidence"} <= set(item)
    assert item["latest_evidence"]["evidence_id"] == expected_evidence_id
    assert {"type": "InspectionReading", "id": reading_id} in body["sources"]


def test_recent_calculated_changes_trace_readings_not_nonexistent_flow_rows(
    test_engine, api_client: TestClient
) -> None:
    """A calculated-only FlowTwin result must never cite an invented row."""
    with Session(test_engine) as session:
        location = _location(session, "A-01-01")
        expected = _pallet_id(session, "PAL-001")
        observed = _pallet_id(session, "PAL-002")
        current = _final_reading(
            session,
            location=location,
            at=datetime.now(timezone.utc) + timedelta(minutes=5),
            comparison=ComparisonResult.PALLET_MISMATCH,
            observed_pallet_id=observed,
            expected_pallet_id=expected,
        )
        previous = session.scalar(
            select(InspectionReading)
            .where(
                InspectionReading.location_id == location.id,
                InspectionReading.is_final.is_(True),
                InspectionReading.inspection_id != current.inspection_id,
            )
            .order_by(InspectionReading.created_at.desc())
        )
        assert previous is not None
        assert not session.scalar(
            select(FlowTwinChange).where(
                FlowTwinChange.current_inspection_id == current.inspection_id
            )
        )
        session.commit()

        current_id = current.id
        previous_id = previous.id

    body = ask(api_client, "¿Qué cambió desde ayer?")
    assert body["intent"] == "RECENT_CHANGES"
    source_types = {source["type"] for source in body["sources"]}
    assert "FlowTwinChange" not in source_types
    reading_sources = {
        source["id"] for source in body["sources"] if source["type"] == "InspectionReading"
    }
    assert {current_id, previous_id} <= reading_sources


def test_location_status_explains_real_physical_context(
    test_engine, api_client: TestClient
) -> None:
    with Session(test_engine) as session:
        location = _location(session, "A-01-03")
        expected = _pallet_id(session, "PAL-003")
        observed = _pallet_id(session, "PAL-004")
        reading = _final_reading(
            session,
            location=location,
            at=datetime.now(timezone.utc) + timedelta(minutes=5),
            comparison=ComparisonResult.PALLET_MISMATCH,
            observed_pallet_id=observed,
            expected_pallet_id=expected,
        )
        exception = ExceptionEvent(
            inspection_id=reading.inspection_id,
            reading_id=reading.id,
            location_id=location.id,
            pallet_id=observed,
            exception_type=ExceptionType.PALLET_MISMATCH,
            severity=Severity.HIGH,
            status=ExceptionStatus.OPEN,
            title="Pallet distinto al esperado",
            description="Prueba de explicación determinística.",
            risk_score=75,
            risk_breakdown={"PALLET_MISMATCH": 35, "EXPIRING_SOON": 20},
        )
        session.add(exception)
        session.commit()
        exception_id = exception.id

    body = ask(api_client, "¿Por qué A-01-03 está en rojo?")
    assert body["intent"] == "LOCATION_STATUS"
    answer = body["answer"]
    for value in ("A-01-03", "PAL-003", "PAL-004", "75", "ALTO"):
        assert value in answer
    assert body["data"]["current_exception_id"] == exception_id
    assert {"type": "ExceptionEvent", "id": exception_id} in body["sources"]


def test_low_coverage_rows_include_operational_context(api_client: TestClient) -> None:
    body = ask(api_client, "¿Qué productos tienen cobertura baja?")
    assert body["intent"] == "LOW_COVERAGE"
    assert body["tool"] == "get_low_coverage_items"
    assert body["data"]
    for item in body["data"]:
        assert {"product", "sku", "coverage_days", "rotation", "risk_score"} <= set(item)
