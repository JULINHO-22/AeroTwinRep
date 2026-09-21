from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Iterable

from app.models.enums import MovementType


class ExpiryLevel(str, Enum):
    EXPIRED = "EXPIRED"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    NORMAL = "NORMAL"


class RotationLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CoverageStatus(str, Enum):
    LOW_COVERAGE = "LOW_COVERAGE"
    NORMAL = "NORMAL"
    NO_CONSUMPTION_DATA = "NO_CONSUMPTION_DATA"


@dataclass(frozen=True)
class ExpiryAnalysis:
    days_to_expiry: int
    level: ExpiryLevel


@dataclass(frozen=True)
class MovementRecord:
    movement_type: MovementType
    quantity: int
    occurred_at: datetime


@dataclass(frozen=True)
class RotationAnalysis:
    outbound_quantity: int
    window_days: int
    level: RotationLevel


@dataclass(frozen=True)
class CoverageAnalysis:
    stock_actual: int
    outbound_quantity: int
    window_days: int
    average_daily_outbound: float
    coverage_days: float | None
    status: CoverageStatus


@dataclass(frozen=True)
class LossPreventionAnalysis:
    """Explainable, non-scoring signal for inventory that may expire first.

    This intentionally remains separate from the central Risk Score.  It is a
    planning signal: when the estimated product coverage is longer than the
    remaining life of the selected lot, normal outbound consumption may not be
    enough to clear that lot before it expires.
    """

    excess_expiry_risk: bool
    coverage_days: float | None
    days_to_expiry: int | None
    reason: str | None


@dataclass(frozen=True)
class LotInventory:
    product_id: int
    lot_code: str
    expires_at: date
    stock_quantity: int


@dataclass(frozen=True)
class FefoAnalysis:
    risk: bool
    outbound_lot: str
    preferred_lot: str | None
    reason: str | None


def analyze_expiry(
    *,
    expires_at: date,
    reference_date: date,
    risk_days: int,
    warning_days: int,
) -> ExpiryAnalysis:
    if risk_days < 0 or warning_days < risk_days:
        raise ValueError("Los umbrales de caducidad son inválidos")

    days_to_expiry = (expires_at - reference_date).days
    if days_to_expiry < 0:
        level = ExpiryLevel.EXPIRED
    elif days_to_expiry <= risk_days:
        level = ExpiryLevel.HIGH
    elif days_to_expiry <= warning_days:
        level = ExpiryLevel.MEDIUM
    else:
        level = ExpiryLevel.NORMAL
    return ExpiryAnalysis(days_to_expiry=days_to_expiry, level=level)


def analyze_rotation(
    *,
    movements: Iterable[MovementRecord],
    reference_at: datetime,
    window_days: int,
    high_min: int,
    medium_min: int,
) -> RotationAnalysis:
    if window_days < 1:
        raise ValueError("window_days debe ser al menos 1")
    if medium_min < 0 or high_min <= medium_min:
        raise ValueError("Los umbrales de rotación son inválidos")

    window_start = reference_at - timedelta(days=window_days)
    outbound_quantity = 0
    for movement in movements:
        if movement.quantity < 0:
            raise ValueError("La cantidad de un movimiento no puede ser negativa")
        if (
            movement.movement_type is MovementType.OUTBOUND
            and window_start <= movement.occurred_at <= reference_at
        ):
            outbound_quantity += movement.quantity

    if outbound_quantity >= high_min:
        level = RotationLevel.HIGH
    elif outbound_quantity >= medium_min:
        level = RotationLevel.MEDIUM
    else:
        level = RotationLevel.LOW

    return RotationAnalysis(
        outbound_quantity=outbound_quantity,
        window_days=window_days,
        level=level,
    )


def analyze_coverage(
    *,
    stock_actual: int,
    outbound_quantity: int,
    window_days: int,
    low_coverage_days: float,
) -> CoverageAnalysis:
    if stock_actual < 0 or outbound_quantity < 0:
        raise ValueError("Stock y salida acumulada no pueden ser negativos")
    if window_days < 1 or low_coverage_days <= 0:
        raise ValueError("Los parámetros de cobertura son inválidos")

    average_daily_outbound = outbound_quantity / window_days
    if average_daily_outbound == 0:
        return CoverageAnalysis(
            stock_actual=stock_actual,
            outbound_quantity=outbound_quantity,
            window_days=window_days,
            average_daily_outbound=0.0,
            coverage_days=None,
            status=CoverageStatus.NO_CONSUMPTION_DATA,
        )

    coverage_days = stock_actual / average_daily_outbound
    status = (
        CoverageStatus.LOW_COVERAGE
        if coverage_days <= low_coverage_days
        else CoverageStatus.NORMAL
    )
    return CoverageAnalysis(
        stock_actual=stock_actual,
        outbound_quantity=outbound_quantity,
        window_days=window_days,
        average_daily_outbound=average_daily_outbound,
        coverage_days=coverage_days,
        status=status,
    )


def analyze_excess_expiry_risk(
    *, coverage_days: float | None, days_to_expiry: int | None
) -> LossPreventionAnalysis:
    """Return a conservative loss-prevention signal from existing analytics.

    ``None`` means there is insufficient consumption/expiry data, rather than
    an assertion that excess inventory does not exist.  The strict comparison
    follows the operational rule agreed for the MVP: ``coverage_days`` must be
    greater than ``days_to_expiry``.
    """

    if coverage_days is None or days_to_expiry is None:
        return LossPreventionAnalysis(
            excess_expiry_risk=False,
            coverage_days=coverage_days,
            days_to_expiry=days_to_expiry,
            reason=None,
        )

    active = coverage_days > days_to_expiry
    return LossPreventionAnalysis(
        excess_expiry_risk=active,
        coverage_days=coverage_days,
        days_to_expiry=days_to_expiry,
        reason=(
            "El inventario podría durar más que la vida restante del lote al ritmo de salida actual."
            if active
            else None
        ),
    )


def analyze_fefo(
    *,
    outbound_lot: LotInventory,
    expected_lots: Iterable[LotInventory],
) -> FefoAnalysis:
    candidates = [
        lot
        for lot in expected_lots
        if lot.product_id == outbound_lot.product_id
        and lot.lot_code != outbound_lot.lot_code
        and lot.stock_quantity > 0
        and lot.expires_at < outbound_lot.expires_at
    ]
    if not candidates:
        return FefoAnalysis(
            risk=False,
            outbound_lot=outbound_lot.lot_code,
            preferred_lot=None,
            reason=None,
        )

    preferred = min(candidates, key=lambda lot: (lot.expires_at, lot.lot_code))
    return FefoAnalysis(
        risk=True,
        outbound_lot=outbound_lot.lot_code,
        preferred_lot=preferred.lot_code,
        reason="Existe stock de un lote del mismo producto con vencimiento anterior.",
    )
