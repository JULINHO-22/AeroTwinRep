from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.analytics import (
    CoverageAnalysis,
    FefoAnalysis,
    LotInventory,
    MovementRecord,
    RotationAnalysis,
    analyze_coverage,
    analyze_fefo,
    analyze_rotation,
)
from app.domain.settings import BusinessRuleSettings
from app.models import ExpectedInventory, Lot, MovementHistory, Pallet
from app.models.enums import PalletStatus


def product_rotation_from_history(
    *,
    session: Session,
    product_id: int,
    reference_at: datetime,
    settings: BusinessRuleSettings,
) -> RotationAnalysis:
    window_start = reference_at - timedelta(days=settings.rotation_window_days)
    rows = session.execute(
        select(
            MovementHistory.movement_type,
            MovementHistory.quantity,
            MovementHistory.occurred_at,
        ).where(
            MovementHistory.product_id == product_id,
            MovementHistory.occurred_at >= window_start,
            MovementHistory.occurred_at <= reference_at,
        )
    ).all()
    movements = (
        MovementRecord(
            movement_type=row.movement_type,
            quantity=row.quantity,
            occurred_at=row.occurred_at,
        )
        for row in rows
    )
    return analyze_rotation(
        movements=movements,
        reference_at=reference_at,
        window_days=settings.rotation_window_days,
        high_min=settings.rotation_thresholds.high_min,
        medium_min=settings.rotation_thresholds.medium_min,
    )


def expected_stock_for_product(*, session: Session, product_id: int) -> int:
    stock = session.scalar(
        select(func.coalesce(func.sum(Pallet.quantity), 0))
        .select_from(ExpectedInventory)
        .join(Pallet, ExpectedInventory.expected_pallet_id == Pallet.id)
        .join(Lot, Pallet.lot_id == Lot.id)
        .where(Lot.product_id == product_id)
    )
    return int(stock or 0)


def product_coverage_from_history(
    *,
    session: Session,
    product_id: int,
    reference_at: datetime,
    settings: BusinessRuleSettings,
) -> CoverageAnalysis:
    rotation = product_rotation_from_history(
        session=session,
        product_id=product_id,
        reference_at=reference_at,
        settings=settings,
    )
    stock = expected_stock_for_product(session=session, product_id=product_id)
    return analyze_coverage(
        stock_actual=stock,
        outbound_quantity=rotation.outbound_quantity,
        window_days=settings.rotation_window_days,
        low_coverage_days=settings.low_coverage_days,
    )


def fefo_for_outbound_lot(*, session: Session, outbound_lot_id: int) -> FefoAnalysis:
    outbound_lot = session.get(Lot, outbound_lot_id)
    if outbound_lot is None:
        raise ValueError(f"No existe el lote outbound con id={outbound_lot_id}")

    # FEFO is a WMS availability question, not a rack-assignment question.
    # ExpectedInventory remains the source for physical-position coverage, but
    # an older available pallet can legitimately be staged or unassigned while
    # still needing to be consumed before a later lot leaves the warehouse.
    # The outbound lot itself is deliberately retained in this query; the pure
    # analyzer excludes the same lot from candidate selection.
    stock_rows = session.execute(
        select(
            Lot.product_id,
            Lot.lot_code,
            Lot.expires_at,
            func.sum(Pallet.quantity).label("stock_quantity"),
        )
        .select_from(Pallet)
        .join(Lot, Pallet.lot_id == Lot.id)
        .where(
            Lot.product_id == outbound_lot.product_id,
            Pallet.status == PalletStatus.AVAILABLE,
        )
        .group_by(Lot.id)
    ).all()
    expected_lots = [
        LotInventory(
            product_id=row.product_id,
            lot_code=row.lot_code,
            expires_at=row.expires_at,
            stock_quantity=int(row.stock_quantity),
        )
        for row in stock_rows
    ]
    return analyze_fefo(
        outbound_lot=LotInventory(
            product_id=outbound_lot.product_id,
            lot_code=outbound_lot.lot_code,
            expires_at=outbound_lot.expires_at,
            stock_quantity=0,
        ),
        expected_lots=expected_lots,
    )
