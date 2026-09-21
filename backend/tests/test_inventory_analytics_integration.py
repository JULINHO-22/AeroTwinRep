from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.analytics import CoverageStatus, RotationLevel, analyze_excess_expiry_risk
from app.domain.settings import load_business_rule_settings
from app.models import Lot, MovementHistory, Product
from app.services.inventory_analytics import (
    expected_stock_for_product,
    fefo_for_outbound_lot,
    product_coverage_from_history,
    product_rotation_from_history,
)


@pytest.fixture(scope="module")
def rules():
    return load_business_rule_settings()


def seed_reference_at(session: Session):
    latest_movement = session.scalar(select(func.max(MovementHistory.occurred_at)))
    assert latest_movement is not None
    return latest_movement + timedelta(days=1)


def test_seed_uses_requested_public_nestle_demo_products(test_engine) -> None:
    expected = {
        "DEMO-001": "NESCAFÉ Tradición",
        "DEMO-002": "MAGGI Caldo de Gallina 15 unidades",
        "DEMO-003": "Galletas AMOR Wafer Chocolate 100 g",
        "DEMO-004": "CHOCAPIC 300 g",
        "DEMO-005": "KITKAT 4 Finger Milk 41.5 g",
        "DEMO-006": "NIDO FortiGrow Lata 400 g",
        "DEMO-007": "TANGO Original 25 g",
        "DEMO-008": "GALAK Barra MilkFirst Blanco 90 g",
        "DEMO-009": "MAGGI Sopa Pollo Fideos 60 g",
        "DEMO-010": "Galletas AMOR Wafer Fresa 100 g",
    }
    with Session(test_engine) as session:
        products = {
            product.sku: product.name
            for product in session.scalars(select(Product).where(Product.sku.like("DEMO-%")))
        }
    assert products == expected


def test_seed_rotation_for_chocapic_is_high(test_engine, rules) -> None:
    with Session(test_engine) as session:
        product = session.scalar(select(Product).where(Product.sku == "DEMO-004"))
        assert product is not None
        result = product_rotation_from_history(
            session=session,
            product_id=product.id,
            reference_at=seed_reference_at(session),
            settings=rules,
        )
        assert result.outbound_quantity == 305
        assert result.level is RotationLevel.HIGH


def test_expected_stock_comes_from_current_expected_pallets(test_engine) -> None:
    with Session(test_engine) as session:
        product = session.scalar(select(Product).where(Product.sku == "DEMO-010"))
        assert product is not None
        assert expected_stock_for_product(session=session, product_id=product.id) == 102


def test_seed_coverage_for_amor_fresa_is_low(test_engine, rules) -> None:
    with Session(test_engine) as session:
        product = session.scalar(select(Product).where(Product.sku == "DEMO-010"))
        assert product is not None
        result = product_coverage_from_history(
            session=session,
            product_id=product.id,
            reference_at=seed_reference_at(session),
            settings=rules,
        )
        assert result.coverage_days == pytest.approx(6.710526, rel=1e-5)
        assert result.status is CoverageStatus.LOW_COVERAGE


def test_seed_fefo_risk_finds_available_older_tango_lot(test_engine) -> None:
    with Session(test_engine) as session:
        outbound_lot = session.scalar(select(Lot).where(Lot.lot_code == "LOT-007"))
        assert outbound_lot is not None
        outbound_exists = session.scalar(
            select(func.count())
            .select_from(MovementHistory)
            .where(MovementHistory.lot_id == outbound_lot.id)
        )
        assert outbound_exists and outbound_exists > 0

        result = fefo_for_outbound_lot(
            session=session,
            outbound_lot_id=outbound_lot.id,
        )
        assert result.risk is True
        assert result.outbound_lot == "LOT-007"
        assert result.preferred_lot == "LOT-011"


def test_seed_galak_emits_explainable_excess_expiry_signal(test_engine, rules) -> None:
    with Session(test_engine) as session:
        product = session.scalar(select(Product).where(Product.sku == "DEMO-008"))
        lot = session.scalar(select(Lot).where(Lot.lot_code == "LOT-008"))
        assert product is not None and lot is not None
        coverage = product_coverage_from_history(
            session=session,
            product_id=product.id,
            reference_at=seed_reference_at(session),
            settings=rules,
        )
        days_to_expiry = (lot.expires_at - seed_reference_at(session).date()).days
    signal = analyze_excess_expiry_risk(
        coverage_days=coverage.coverage_days,
        days_to_expiry=days_to_expiry,
    )
    assert coverage.coverage_days is not None and coverage.coverage_days > days_to_expiry
    assert signal.excess_expiry_risk is True
    assert signal.reason is not None
