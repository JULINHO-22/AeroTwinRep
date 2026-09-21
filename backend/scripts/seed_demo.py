from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
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
    FlowTwinChangeType,
    InspectionStatus,
    MovementType,
    ObservedState,
    PalletStatus,
    ReadingStatus,
    ResolutionType,
    Severity,
    SourceType,
    UserRole,
)


DEMO_TABLES = (
    "sensor_devices",
    "agent_query_logs",
    "audit_logs",
    "flowtwin_changes",
    "exception_events",
    "evidence_files",
    "inspection_readings",
    "inspections",
    "movement_history",
    "expected_inventory",
    "pallets",
    "lots",
    "products",
    "locations",
    "warehouse_zones",
    "users",
)


def stable_uuid(value: str):
    return uuid5(NAMESPACE_URL, f"https://aerotwin.demo/{value}")


def reset_demo_data(session: Session) -> None:
    table_list = ", ".join(DEMO_TABLES)
    session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))


def seed_demo(database_url: str | None = None) -> dict[str, int]:
    settings = get_settings()
    if not settings.demo_mode:
        raise RuntimeError("El seed demo solo puede ejecutarse con DEMO_MODE=true.")

    target_url = database_url or settings.database_url
    seed_engine = create_engine(target_url, pool_pre_ping=True)
    seed_session_factory = sessionmaker(bind=seed_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    today = date.today()

    with seed_session_factory.begin() as session:
        reset_demo_data(session)

        operator = User(
            username="operator01",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$9Z+ii2ksHIG1DAKhGpeM1g$J4wUYtWLnyMFCJNhSmrXt4KraZSjBLphcw/s1gAzN3U",
            full_name="Operador Demo",
            role=UserRole.OPERATOR,
        )
        supervisor = User(
            username="supervisor01",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$9Z+ii2ksHIG1DAKhGpeM1g$J4wUYtWLnyMFCJNhSmrXt4KraZSjBLphcw/s1gAzN3U",
            full_name="Supervisor Demo",
            role=UserRole.SUPERVISOR,
        )
        session.add_all([operator, supervisor])

        zones = {
            "A": WarehouseZone(code="A", name="Pasillo A", description="Zona demo A"),
            "B": WarehouseZone(code="B", name="Pasillo B", description="Zona demo B"),
        }
        session.add_all(zones.values())
        session.flush()

        locations: dict[str, Location] = {}
        for zone_code in ("A", "B"):
            for row in (1, 2):
                for column in (1, 2, 3):
                    code = f"{zone_code}-{row:02d}-{column:02d}"
                    locations[code] = Location(
                        zone_id=zones[zone_code].id,
                        code=code,
                        row_index=row,
                        column_index=column,
                        level=1,
                        description=f"Posición {code} del rack demo",
                    )
        session.add_all(locations.values())

        # Commercial names are public product references only.  DEMO SKU,
        # lots, pallets, quantities, dates and movements remain synthetic WMS
        # data and must never be presented as Nestlé internal identifiers.
        product_specs = (
            ("DEMO-001", "NESCAFÉ Tradición", "Café", "unidad"),
            ("DEMO-002", "MAGGI Caldo de Gallina 15 unidades", "Condimentos", "caja"),
            ("DEMO-003", "Galletas AMOR Wafer Chocolate 100 g", "Galletas", "unidad"),
            ("DEMO-004", "CHOCAPIC 300 g", "Cereales", "caja"),
            ("DEMO-005", "KITKAT 4 Finger Milk 41.5 g", "Chocolates", "unidad"),
            ("DEMO-006", "NIDO FortiGrow Lata 400 g", "Lácteos", "lata"),
            ("DEMO-007", "TANGO Original 25 g", "Galletas", "unidad"),
            ("DEMO-008", "GALAK Barra MilkFirst Blanco 90 g", "Chocolates", "unidad"),
            ("DEMO-009", "MAGGI Sopa Pollo Fideos 60 g", "Sopas", "unidad"),
            ("DEMO-010", "Galletas AMOR Wafer Fresa 100 g", "Galletas", "unidad"),
        )
        products = {
            sku: Product(sku=sku, name=name, category=category, unit=unit)
            for sku, name, category, unit in product_specs
        }
        session.add_all(products.values())
        session.flush()

        # LOT-011 is an older available lot of TANGO. It is intentionally not
        # assigned to an expected slot: FEFO must use WMS available inventory,
        # not just the visible rack assignments.
        lot_specs = (
            ("LOT-001", "DEMO-001", 120),
            ("LOT-002", "DEMO-003", 75),
            ("LOT-003", "DEMO-002", 90),
            ("LOT-004", "DEMO-004", 75),
            ("LOT-005", "DEMO-005", 180),
            ("LOT-006", "DEMO-006", 45),
            ("LOT-007", "DEMO-007", 90),
            ("LOT-008", "DEMO-008", 10),
            ("LOT-009", "DEMO-009", 120),
            ("LOT-010", "DEMO-010", 120),
            ("LOT-011", "DEMO-007", 24),
        )
        lots = {
            lot_code: Lot(
                product_id=products[sku].id,
                lot_code=lot_code,
                manufactured_at=today - timedelta(days=180),
                expires_at=today + timedelta(days=expiry_days),
            )
            for lot_code, sku, expiry_days in lot_specs
        }
        session.add_all(lots.values())
        session.flush()

        pallet_lots = (
            "LOT-001",  # PAL-001 / A-01-01 / NESCAFÉ Tradición
            "LOT-002",  # PAL-002 / A-01-02 / AMOR Chocolate
            "LOT-003",  # PAL-003 / A-01-03 / MAGGI Caldo
            "LOT-004",  # PAL-004 / A-02-01 / CHOCAPIC
            "LOT-005",  # PAL-005 / A-02-03 / KITKAT
            "LOT-006",  # PAL-006 / B-01-01 / NIDO
            "LOT-007",  # PAL-007 / B-01-02 / TANGO
            "LOT-008",  # PAL-008 / B-01-03 / GALAK
            "LOT-009",  # PAL-009 / B-02-01 / MAGGI Sopa
            "LOT-010",  # PAL-010 / B-02-03 / AMOR Fresa
            "LOT-011",  # PAL-011 / synthetic unexpected TANGO pallet
            "LOT-008",
            "LOT-004",
            "LOT-005",
            "LOT-007",
        )
        pallets: dict[str, Pallet] = {}
        for index, lot_code in enumerate(pallet_lots, start=1):
            pallet_code = f"PAL-{index:03d}"
            quantity = 40 + ((index * 7) % 41)
            # Deliberately chosen to exercise real analytics without changing
            # their rules: low coverage for DEMO-010 and excess/expiry for
            # DEMO-008 after outbound history is applied below.
            if pallet_code == "PAL-008":
                quantity = 150
            elif pallet_code == "PAL-010":
                quantity = 102
            elif pallet_code == "PAL-007":
                quantity = 80
            pallets[pallet_code] = Pallet(
                pallet_code=pallet_code,
                lot_id=lots[lot_code].id,
                quantity=quantity,
                status=PalletStatus.AVAILABLE,
            )
        session.add_all(pallets.values())
        session.flush()

        expected_mapping = {
            "A-01-01": "PAL-001",
            "A-01-02": "PAL-002",
            "A-01-03": "PAL-003",
            "A-02-01": "PAL-004",
            "A-02-02": None,
            "A-02-03": "PAL-005",
            "B-01-01": "PAL-006",
            "B-01-02": "PAL-007",
            "B-01-03": "PAL-008",
            "B-02-01": "PAL-009",
            "B-02-02": None,
            "B-02-03": "PAL-010",
        }
        session.add_all(
            ExpectedInventory(
                location_id=locations[location_code].id,
                expected_pallet_id=(
                    pallets[pallet_code].id if pallet_code is not None else None
                ),
                updated_at=now,
            )
            for location_code, pallet_code in expected_mapping.items()
        )

        pallets_by_lot: dict[str, Pallet] = {}
        for pallet in pallets.values():
            lot_code = next(code for code, lot in lots.items() if lot.id == pallet.lot_id)
            pallets_by_lot.setdefault(lot_code, pallet)

        movement_profiles = (
            # B-02-03 / AMOR Fresa: coverage below the configured threshold.
            ("DEMO-010", "LOT-010", 12, 35),
            # A-02-01 / CHOCAPIC: high rotation.
            ("DEMO-004", "LOT-004", 11, 25),
            # B-01-03 / GALAK: enough coverage to outlast LOT-008's 10 days.
            ("DEMO-008", "LOT-008", 10, 18),
            # B-01-02 / TANGO: a real outbound lot so FEFO compares its
            # outgoing stock against the older available LOT-011.
            ("DEMO-007", "LOT-007", 3, 6),
            ("DEMO-005", "LOT-005", 3, 3),
            ("DEMO-001", "LOT-001", 5, 4),
            ("DEMO-002", "LOT-003", 4, 5),
            ("DEMO-006", "LOT-006", 3, 4),
            ("DEMO-009", "LOT-009", 2, 3),
        )
        movement_index = 0
        for sku, lot_code, count, base_quantity in movement_profiles:
            for sequence in range(count):
                occurred_at = now - timedelta(
                    days=(movement_index % 28) + 1,
                    hours=movement_index % 7,
                )
                session.add(
                    MovementHistory(
                        product_id=products[sku].id,
                        lot_id=lots[lot_code].id,
                        pallet_id=pallets_by_lot[lot_code].id,
                        movement_type=MovementType.OUTBOUND,
                        quantity=base_quantity + (sequence % 4) * 2,
                        occurred_at=occurred_at,
                        source_zone_id=zones["A" if movement_index % 2 == 0 else "B"].id,
                        notes=f"Salida demo determinista {movement_index + 1:02d}",
                    )
                )
                movement_index += 1

        inspection_specs = (
            ("inspection-a-previous", "A", 3),
            ("inspection-a-current", "A", 2),
            ("inspection-b-current", "B", 1),
        )
        inspections: dict[str, Inspection] = {}
        for key, zone_code, days_ago in inspection_specs:
            started_at = now - timedelta(days=days_ago, hours=1)
            inspections[key] = Inspection(
                zone_id=zones[zone_code].id,
                started_by=operator.id,
                started_at=started_at,
                completed_at=started_at + timedelta(minutes=42),
                status=InspectionStatus.COMPLETED,
                notes="Inspección histórica sintética para demo",
            )
        session.add_all(inspections.values())
        session.flush()

        final_readings: dict[tuple[str, str], InspectionReading] = {}
        for inspection_key, zone_code, days_ago in inspection_specs:
            for location_code, expected_pallet_code in expected_mapping.items():
                if not location_code.startswith(f"{zone_code}-"):
                    continue

                observed_pallet_code = expected_pallet_code
                observed_state = (
                    ObservedState.PALLET
                    if expected_pallet_code is not None
                    else ObservedState.EMPTY
                )
                comparison = (
                    ComparisonResult.CORRECT
                    if expected_pallet_code is not None
                    else ComparisonResult.CORRECT_EMPTY
                )
                quality_score = 94
                empty_confirmed = expected_pallet_code is None

                # The same physical discrepancy in consecutive completed
                # inspections is what makes the recurrent/FlowTwin scenario
                # meaningful. PAL-008 is GALAK, while A-01-02 expects AMOR.
                if inspection_key in {"inspection-a-previous", "inspection-a-current"} and location_code == "A-01-02":
                    observed_pallet_code = "PAL-008"
                    comparison = ComparisonResult.PALLET_MISMATCH
                    quality_score = 91

                # No-read remains unresolved; it is deliberately not seeded as
                # EMPTY. This feeds the human-review case at A-01-03.
                if inspection_key == "inspection-a-current" and location_code == "A-01-03":
                    observed_pallet_code = None
                    observed_state = ObservedState.UNRESOLVED
                    comparison = ComparisonResult.UNRESOLVED
                    quality_score = 44
                    empty_confirmed = False

                # Expected empty position with a real, known pallet. This is a
                # physical UNEXPECTED_PALLET, not a synthetic empty reading.
                if inspection_key == "inspection-a-current" and location_code == "A-02-02":
                    observed_pallet_code = "PAL-011"
                    observed_state = ObservedState.PALLET
                    comparison = ComparisonResult.UNEXPECTED_PALLET
                    quality_score = 93

                reading_group_id = stable_uuid(f"{inspection_key}:{location_code}:group")

                if inspection_key == "inspection-b-current" and location_code == "B-01-01":
                    low_quality_reading = InspectionReading(
                        inspection_id=inspections[inspection_key].id,
                        location_id=locations[location_code].id,
                        client_reading_id=stable_uuid(
                            f"{inspection_key}:{location_code}:attempt:1"
                        ),
                        reading_group_id=reading_group_id,
                        attempt_number=1,
                        expected_pallet_id_at_inspection=pallets[expected_pallet_code].id,
                        observed_pallet_id=pallets[expected_pallet_code].id,
                        observed_state=ObservedState.PALLET,
                        quality_score=58,
                        reading_status=ReadingStatus.RESCAN_REQUIRED,
                        comparison_result=ComparisonResult.UNRESOLVED,
                        is_final=False,
                        created_by=operator.id,
                        source_type=SourceType.SEED_SYSTEM,
                        empty_confirmed_by_operator=False,
                        created_at=now - timedelta(days=days_ago, minutes=2),
                    )
                    session.add(low_quality_reading)

                attempt_number = 2 if (
                    inspection_key == "inspection-b-current"
                    and location_code == "B-01-01"
                ) else 1
                reading_status = (
                    ReadingStatus.HUMAN_REVIEW_REQUIRED
                    if inspection_key == "inspection-a-current" and location_code == "A-01-03"
                    else ReadingStatus.ACCEPTED
                )
                reading = InspectionReading(
                    inspection_id=inspections[inspection_key].id,
                    location_id=locations[location_code].id,
                    client_reading_id=stable_uuid(
                        f"{inspection_key}:{location_code}:attempt:{attempt_number}"
                    ),
                    reading_group_id=reading_group_id,
                    attempt_number=attempt_number,
                    expected_pallet_id_at_inspection=(
                        pallets[expected_pallet_code].id
                        if expected_pallet_code is not None
                        else None
                    ),
                    observed_pallet_id=(
                        pallets[observed_pallet_code].id
                        if observed_pallet_code is not None
                        else None
                    ),
                    observed_state=observed_state,
                    quality_score=quality_score,
                    reading_status=reading_status,
                    comparison_result=comparison,
                    is_final=True,
                    created_by=operator.id,
                    source_type=SourceType.SEED_SYSTEM,
                    empty_confirmed_by_operator=empty_confirmed,
                    created_at=now - timedelta(days=days_ago),
                )
                session.add(reading)
                final_readings[(inspection_key, location_code)] = reading

        session.flush()
        # Demo data exercises the real temporal engine; no manual FlowTwin rows.
        from app.services.flowtwin_service import persist
        persist(session, inspections["inspection-a-current"])

        exceptions = (
            ExceptionEvent(
                inspection_id=inspections["inspection-a-previous"].id,
                reading_id=final_readings[("inspection-a-previous", "A-01-02")].id,
                location_id=locations["A-01-02"].id,
                product_id=products["DEMO-008"].id,
                pallet_id=pallets["PAL-008"].id,
                exception_type=ExceptionType.PALLET_MISMATCH,
                severity=Severity.MEDIUM,
                status=ExceptionStatus.RESOLVED,
                title="Pallet distinto al esperado",
                description="A-01-02 registró PAL-008 cuando se esperaba PAL-002.",
                risk_score=35,
                risk_breakdown={"PALLET_MISMATCH": 35},
                resolution_type=ResolutionType.CONFIRMED,
                created_at=now - timedelta(days=3),
                resolved_at=now - timedelta(days=2, hours=20),
                resolved_by=supervisor.id,
                resolution_comment="La discrepancia se revisó en la inspección anterior.",
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-a-current"].id,
                reading_id=final_readings[("inspection-a-current", "A-01-02")].id,
                location_id=locations["A-01-02"].id,
                product_id=products["DEMO-008"].id,
                pallet_id=pallets["PAL-008"].id,
                exception_type=ExceptionType.PALLET_MISMATCH,
                severity=Severity.MEDIUM,
                status=ExceptionStatus.OPEN,
                title="Pallet distinto al esperado",
                description="A-01-02 observa PAL-008; el WMS espera PAL-002.",
                risk_score=55,
                risk_breakdown={"PALLET_MISMATCH": 35, "EXPIRING_SOON": 20},
                created_at=now - timedelta(days=2),
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-a-current"].id,
                reading_id=final_readings[("inspection-a-current", "A-01-03")].id,
                location_id=locations["A-01-03"].id,
                product_id=products["DEMO-002"].id,
                pallet_id=pallets["PAL-003"].id,
                exception_type=ExceptionType.LOW_QUALITY,
                severity=Severity.LOW,
                status=ExceptionStatus.IN_REVIEW,
                title="Lectura requiere revisión humana",
                description="A-01-03 no tiene una observación física confiable después de los intentos disponibles.",
                risk_score=10,
                risk_breakdown={"LOW_QUALITY": 10},
                created_at=now - timedelta(days=2),
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-a-current"].id,
                reading_id=final_readings[("inspection-a-current", "A-02-02")].id,
                location_id=locations["A-02-02"].id,
                product_id=products["DEMO-007"].id,
                pallet_id=pallets["PAL-011"].id,
                exception_type=ExceptionType.UNEXPECTED_PALLET,
                severity=Severity.MEDIUM,
                status=ExceptionStatus.OPEN,
                title="Pallet no esperado en posición vacía",
                description="A-02-02 está configurada vacía y observa PAL-011.",
                risk_score=35,
                risk_breakdown={"UNEXPECTED_PALLET": 35},
                created_at=now - timedelta(days=2),
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-b-current"].id,
                reading_id=final_readings[("inspection-b-current", "B-01-01")].id,
                location_id=locations["B-01-01"].id,
                product_id=products["DEMO-006"].id,
                pallet_id=pallets["PAL-006"].id,
                exception_type=ExceptionType.LOW_QUALITY,
                severity=Severity.MEDIUM,
                status=ExceptionStatus.RESOLVED,
                title="Lectura inicial de baja calidad",
                description="El primer intento obtuvo 58/100 y requirió ReScan.",
                risk_score=10,
                risk_breakdown={"LOW_QUALITY": 10},
                resolution_type=ResolutionType.FALSE_POSITIVE,
                created_at=now - timedelta(days=1),
                resolved_at=now - timedelta(hours=22),
                resolved_by=supervisor.id,
                resolution_comment="El segundo intento confirmó el pallet esperado.",
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-b-current"].id,
                reading_id=final_readings[("inspection-b-current", "B-02-03")].id,
                location_id=locations["B-02-03"].id,
                product_id=products["DEMO-010"].id,
                pallet_id=pallets["PAL-010"].id,
                exception_type=ExceptionType.LOW_COVERAGE,
                severity=Severity.LOW,
                status=ExceptionStatus.OPEN,
                title="Riesgo de faltante de AMOR Wafer Fresa",
                description="La salida reciente reduce la cobertura estimada bajo el umbral demo.",
                risk_score=25,
                risk_breakdown={"LOW_COVERAGE": 25},
                created_at=now - timedelta(hours=18),
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-b-current"].id,
                reading_id=final_readings[("inspection-b-current", "B-01-02")].id,
                location_id=locations["B-01-02"].id,
                product_id=products["DEMO-007"].id,
                pallet_id=pallets["PAL-007"].id,
                exception_type=ExceptionType.FEFO_RISK,
                severity=Severity.LOW,
                status=ExceptionStatus.OPEN,
                title="Riesgo FEFO en TANGO Original",
                description="LOT-007 puede salir mientras LOT-011 del mismo producto vence antes.",
                risk_score=10,
                risk_breakdown={"FEFO_RISK": 10},
                created_at=now - timedelta(hours=16),
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-a-current"].id,
                reading_id=final_readings[("inspection-a-current", "A-02-01")].id,
                location_id=locations["A-02-01"].id,
                product_id=products["DEMO-004"].id,
                pallet_id=pallets["PAL-004"].id,
                exception_type=ExceptionType.HIGH_ROTATION,
                severity=Severity.LOW,
                status=ExceptionStatus.OPEN,
                title="Alta rotación de CHOCAPIC",
                description="DEMO-004 concentra salidas durante la ventana de rotación.",
                risk_score=15,
                risk_breakdown={"HIGH_ROTATION": 15},
                created_at=now - timedelta(hours=14),
            ),
            ExceptionEvent(
                inspection_id=inspections["inspection-b-current"].id,
                reading_id=final_readings[("inspection-b-current", "B-01-03")].id,
                location_id=locations["B-01-03"].id,
                product_id=products["DEMO-008"].id,
                pallet_id=pallets["PAL-008"].id,
                exception_type=ExceptionType.EXPIRING_SOON,
                severity=Severity.LOW,
                status=ExceptionStatus.OPEN,
                title="Lote próximo a vencer",
                description="LOT-008 corresponde a GALAK y vence dentro de 10 días desde la generación del seed.",
                risk_score=20,
                risk_breakdown={"EXPIRING_SOON": 20},
                created_at=now - timedelta(hours=12),
            ),
            ExceptionEvent(
                location_id=locations["A-01-02"].id,
                product_id=products["DEMO-008"].id,
                exception_type=ExceptionType.HISTORICAL_ANOMALY,
                severity=Severity.LOW,
                status=ExceptionStatus.OPEN,
                title="Anomalía recurrente en A-01-02",
                description="La ubicación presenta antecedentes de discrepancia.",
                risk_score=10,
                risk_breakdown={"HISTORICAL_ANOMALY": 10},
                created_at=now - timedelta(hours=10),
            ),
        )
        session.add_all(exceptions)

        session.add_all(
            [
                AuditLog(
                    user_id=operator.id,
                    event_type="DEMO_INSPECTION_COMPLETED",
                    entity_type="inspection",
                    entity_id=inspection.id,
                    metadata_json={"source": "seed_demo"},
                    created_at=inspection.completed_at,
                )
                for inspection in inspections.values()
            ]
        )

    count_models = (
        User,
        WarehouseZone,
        Location,
        Product,
        Lot,
        Pallet,
        ExpectedInventory,
        MovementHistory,
        Inspection,
        InspectionReading,
        EvidenceFile,
        ExceptionEvent,
        FlowTwinChange,
        AuditLog,
        AgentQueryLog,
    )
    with seed_session_factory() as session:
        counts = {
            model.__tablename__: session.scalar(select(func.count()).select_from(model)) or 0
            for model in count_models
        }

    seed_engine.dispose()
    return counts


def main() -> None:
    counts = seed_demo()
    print("Seed demo recreado correctamente:")
    for table_name, row_count in counts.items():
        print(f"- {table_name}: {row_count}")


if __name__ == "__main__":
    main()
