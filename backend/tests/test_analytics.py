from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.analytics import (
    CoverageStatus,
    ExpiryLevel,
    LotInventory,
    MovementRecord,
    RotationLevel,
    analyze_coverage,
    analyze_excess_expiry_risk,
    analyze_expiry,
    analyze_fefo,
    analyze_rotation,
)
from app.models.enums import MovementType


@pytest.mark.parametrize(
    ("days", "expected_level"),
    [
        (-1, ExpiryLevel.EXPIRED),
        (0, ExpiryLevel.HIGH),
        (30, ExpiryLevel.HIGH),
        (31, ExpiryLevel.MEDIUM),
        (90, ExpiryLevel.MEDIUM),
        (91, ExpiryLevel.NORMAL),
    ],
)
def test_expiry_boundaries(days, expected_level) -> None:
    reference = date(2026, 9, 20)
    result = analyze_expiry(
        expires_at=reference + timedelta(days=days),
        reference_date=reference,
        risk_days=30,
        warning_days=90,
    )
    assert result.days_to_expiry == days
    assert result.level is expected_level


@pytest.mark.parametrize(
    ("quantity", "expected_level"),
    [
        (99, RotationLevel.LOW),
        (100, RotationLevel.MEDIUM),
        (299, RotationLevel.MEDIUM),
        (300, RotationLevel.HIGH),
    ],
)
def test_rotation_thresholds(quantity, expected_level) -> None:
    reference = datetime(2026, 9, 20, tzinfo=timezone.utc)
    result = analyze_rotation(
        movements=[
            MovementRecord(MovementType.OUTBOUND, quantity, reference - timedelta(days=1))
        ],
        reference_at=reference,
        window_days=30,
        high_min=300,
        medium_min=100,
    )
    assert result.outbound_quantity == quantity
    assert result.level is expected_level


def test_rotation_counts_only_outbound_inside_window() -> None:
    reference = datetime(2026, 9, 20, tzinfo=timezone.utc)
    result = analyze_rotation(
        movements=[
            MovementRecord(MovementType.OUTBOUND, 100, reference - timedelta(days=2)),
            MovementRecord(MovementType.INBOUND, 500, reference - timedelta(days=2)),
            MovementRecord(MovementType.OUTBOUND, 700, reference - timedelta(days=31)),
            MovementRecord(MovementType.OUTBOUND, 25, reference - timedelta(days=30)),
        ],
        reference_at=reference,
        window_days=30,
        high_min=300,
        medium_min=100,
    )
    assert result.outbound_quantity == 125
    assert result.level is RotationLevel.MEDIUM


@pytest.mark.parametrize(
    ("stock", "outbound", "expected_days", "expected_status"),
    [
        (600, 3000, 6.0, CoverageStatus.LOW_COVERAGE),
        (800, 3000, 8.0, CoverageStatus.NORMAL),
        (700, 3000, 7.0, CoverageStatus.LOW_COVERAGE),
    ],
)
def test_coverage(stock, outbound, expected_days, expected_status) -> None:
    result = analyze_coverage(
        stock_actual=stock,
        outbound_quantity=outbound,
        window_days=30,
        low_coverage_days=7,
    )
    assert result.coverage_days == pytest.approx(expected_days)
    assert result.status is expected_status


def test_coverage_without_outbound_has_no_infinite_value() -> None:
    result = analyze_coverage(
        stock_actual=600,
        outbound_quantity=0,
        window_days=30,
        low_coverage_days=7,
    )
    assert result.coverage_days is None
    assert result.average_daily_outbound == 0
    assert result.status is CoverageStatus.NO_CONSUMPTION_DATA


def test_loss_prevention_flags_only_when_coverage_outlasts_lot_life() -> None:
    flagged = analyze_excess_expiry_risk(coverage_days=21.8, days_to_expiry=10)
    safe = analyze_excess_expiry_risk(coverage_days=7.0, days_to_expiry=10)
    incomplete = analyze_excess_expiry_risk(coverage_days=None, days_to_expiry=10)

    assert flagged.excess_expiry_risk is True
    assert flagged.reason is not None
    assert safe.excess_expiry_risk is False
    assert incomplete.excess_expiry_risk is False
    assert incomplete.reason is None


def lot(product_id: int, code: str, expiry_days: int, stock: int) -> LotInventory:
    return LotInventory(
        product_id=product_id,
        lot_code=code,
        expires_at=date(2026, 9, 20) + timedelta(days=expiry_days),
        stock_quantity=stock,
    )


def test_fefo_detects_later_lot_leaving_before_earlier_stock() -> None:
    result = analyze_fefo(
        outbound_lot=lot(2, "LOT-007", 90, 0),
        expected_lots=[lot(2, "LOT-002", 24, 54)],
    )
    assert result.risk is True
    assert result.preferred_lot == "LOT-002"
    assert result.outbound_lot == "LOT-007"
    assert result.reason is not None


@pytest.mark.parametrize(
    "expected_lots",
    [
        [lot(2, "LOT-007", 90, 50)],
        [lot(2, "LOT-010", 120, 50)],
        [lot(2, "LOT-002", 24, 0)],
        [lot(3, "LOT-002", 24, 50)],
    ],
)
def test_fefo_edge_cases_do_not_raise_risk(expected_lots) -> None:
    result = analyze_fefo(
        outbound_lot=lot(2, "LOT-007", 90, 0),
        expected_lots=expected_lots,
    )
    assert result.risk is False
    assert result.preferred_lot is None


def test_fefo_earlier_lot_leaving_first_has_no_risk() -> None:
    result = analyze_fefo(
        outbound_lot=lot(2, "LOT-002", 24, 0),
        expected_lots=[lot(2, "LOT-007", 90, 50)],
    )
    assert result.risk is False
