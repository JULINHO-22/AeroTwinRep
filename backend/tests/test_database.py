from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AgentQueryLog,
    AuditLog,
    EvidenceFile,
    ExceptionEvent,
    ExpectedInventory,
    FlowTwinChange,
    Inspection,
    InspectionReading,
    Location,
    Lot,
    MovementHistory,
    Pallet,
    Product,
    User,
    WarehouseZone,
)
from app.models.enums import (
    ComparisonResult,
    ExceptionStatus,
    ExceptionType,
    ObservedState,
    ReadingStatus,
    Severity,
    SourceType,
    UserRole,
)
from scripts.seed_demo import seed_demo


EXPECTED_TABLES = {
    "agent_query_logs",
    "audit_logs",
    "evidence_files",
    "exception_events",
    "expected_inventory",
    "flowtwin_changes",
    "inspection_readings",
    "inspections",
    "locations",
    "lots",
    "movement_history",
    "pallets",
    "products",
    "users",
    "warehouse_zones",
}

EXPECTED_SEED_COUNTS = {
    "users": 2,
    "warehouse_zones": 2,
    "locations": 12,
    "products": 10,
    "lots": 11,
    "pallets": 15,
    "expected_inventory": 12,
    "movement_history": 53,
    "inspections": 3,
    "inspection_readings": 19,
    "evidence_files": 0,
    "exception_events": 10,
    "flowtwin_changes": 3,
    "audit_logs": 3,
    "agent_query_logs": 0,
}


def test_database_connection(test_engine) -> None:
    with test_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1


def test_initial_migration_creates_all_domain_tables(test_engine) -> None:
    table_names = set(inspect(test_engine).get_table_names())
    assert EXPECTED_TABLES.issubset(table_names)
    assert "alembic_version" in table_names


def test_seed_is_reproducible_without_duplicates(test_database_url) -> None:
    first_counts = seed_demo(test_database_url)
    second_counts = seed_demo(test_database_url)

    assert first_counts == EXPECTED_SEED_COUNTS
    assert second_counts == EXPECTED_SEED_COUNTS


def test_basic_relationships(test_engine) -> None:
    with Session(test_engine) as session:
        pallet = session.scalar(select(Pallet).where(Pallet.pallet_code == "PAL-001"))
        location = session.scalar(select(Location).where(Location.code == "A-01-01"))

        assert pallet is not None
        assert pallet.lot.product.sku == "DEMO-001"
        assert pallet.lot.product.name == "NESCAFÉ Tradición"
        assert location is not None
        assert location.zone.code == "A"
        assert location.expected_inventory.expected_pallet.pallet_code == "PAL-001"


def test_username_must_be_unique(test_engine) -> None:
    with Session(test_engine) as session:
        session.add(
            User(
                username="operator01",
                password_hash="duplicate",
                full_name="Duplicado",
                role=UserRole.OPERATOR,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_expected_pallet_cannot_be_assigned_twice(test_engine) -> None:
    with Session(test_engine) as session:
        empty_position = session.scalar(
            select(ExpectedInventory).where(
                ExpectedInventory.expected_pallet_id.is_(None)
            )
        )
        occupied_position = session.scalar(
            select(ExpectedInventory).where(
                ExpectedInventory.expected_pallet_id.is_not(None)
            )
        )
        assert empty_position is not None
        assert occupied_position is not None

        empty_position.expected_pallet_id = occupied_position.expected_pallet_id
        with pytest.raises(IntegrityError):
            session.commit()


def test_quality_score_constraint(test_engine) -> None:
    with Session(test_engine) as session:
        inspection = session.scalar(select(Inspection))
        location = session.scalar(select(Location))
        user = session.scalar(select(User))
        assert inspection and location and user

        session.add(
            InspectionReading(
                inspection_id=inspection.id,
                location_id=location.id,
                client_reading_id=uuid4(),
                reading_group_id=uuid4(),
                attempt_number=1,
                observed_state=ObservedState.UNRESOLVED,
                quality_score=101,
                reading_status=ReadingStatus.HUMAN_REVIEW_REQUIRED,
                comparison_result=ComparisonResult.UNRESOLVED,
                is_final=False,
                created_by=user.id,
                source_type=SourceType.SEED_SYSTEM,
                empty_confirmed_by_operator=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_risk_score_constraint(test_engine) -> None:
    with Session(test_engine) as session:
        session.add(
            ExceptionEvent(
                exception_type=ExceptionType.HISTORICAL_ANOMALY,
                severity=Severity.HIGH,
                status=ExceptionStatus.OPEN,
                title="Score inválido",
                description="Registro usado únicamente para comprobar el constraint.",
                risk_score=101,
                risk_breakdown={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_client_reading_id_must_be_unique(test_engine) -> None:
    with Session(test_engine) as session:
        existing = session.scalar(select(InspectionReading))
        assert existing is not None
        session.add(
            InspectionReading(
                inspection_id=existing.inspection_id,
                location_id=existing.location_id,
                client_reading_id=existing.client_reading_id,
                reading_group_id=uuid4(),
                attempt_number=1,
                observed_state=ObservedState.UNRESOLVED,
                quality_score=50,
                reading_status=ReadingStatus.HUMAN_REVIEW_REQUIRED,
                comparison_result=ComparisonResult.UNRESOLVED,
                is_final=False,
                created_by=existing.created_by,
                source_type=SourceType.SEED_SYSTEM,
                empty_confirmed_by_operator=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_only_one_final_reading_per_group(test_engine) -> None:
    with Session(test_engine) as session:
        existing = session.scalar(
            select(InspectionReading).where(InspectionReading.is_final.is_(True))
        )
        assert existing is not None
        session.add(
            InspectionReading(
                inspection_id=existing.inspection_id,
                location_id=existing.location_id,
                client_reading_id=uuid4(),
                reading_group_id=existing.reading_group_id,
                attempt_number=existing.attempt_number + 1,
                expected_pallet_id_at_inspection=existing.expected_pallet_id_at_inspection,
                observed_pallet_id=existing.observed_pallet_id,
                observed_state=existing.observed_state,
                quality_score=existing.quality_score,
                reading_status=ReadingStatus.ACCEPTED,
                comparison_result=existing.comparison_result,
                is_final=True,
                created_by=existing.created_by,
                source_type=SourceType.SEED_SYSTEM,
                empty_confirmed_by_operator=existing.empty_confirmed_by_operator,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
