from dataclasses import dataclass
from enum import Enum

from app.domain.analytics import RotationLevel
from app.domain.settings import BusinessRuleSettings
from app.models.enums import ComparisonResult, ReadingStatus, Severity


class RiskRule(str, Enum):
    PALLET_MISMATCH = "PALLET_MISMATCH"
    EXPECTED_PALLET_MISSING = "EXPECTED_PALLET_MISSING"
    UNEXPECTED_PALLET = "UNEXPECTED_PALLET"
    EXPIRING_SOON = "EXPIRING_SOON"
    HIGH_ROTATION = "HIGH_ROTATION"
    LOW_COVERAGE = "LOW_COVERAGE"
    LOW_QUALITY = "LOW_QUALITY"
    FEFO_RISK = "FEFO_RISK"
    HISTORICAL_ANOMALY = "HISTORICAL_ANOMALY"


@dataclass(frozen=True)
class RiskContext:
    comparison_result: ComparisonResult = ComparisonResult.UNRESOLVED
    days_to_expiry: int | None = None
    rotation_level: RotationLevel | None = None
    low_coverage: bool = False
    final_quality_status: ReadingStatus | None = None
    fefo_risk: bool = False
    historical_anomaly_count: int = 0


@dataclass(frozen=True)
class RiskReason:
    rule: RiskRule
    points: int
    label: str


@dataclass(frozen=True)
class RiskResult:
    score: int
    severity: Severity
    reasons: tuple[RiskReason, ...]


RULE_LABELS = {
    RiskRule.PALLET_MISMATCH: "Pallet diferente al esperado",
    RiskRule.EXPECTED_PALLET_MISSING: "Pallet esperado no encontrado",
    RiskRule.UNEXPECTED_PALLET: "Pallet encontrado en una posición esperada vacía",
    RiskRule.EXPIRING_SOON: "Producto vencido o próximo a vencer",
    RiskRule.HIGH_ROTATION: "Producto con alta rotación",
    RiskRule.LOW_COVERAGE: "Producto con cobertura baja",
    RiskRule.LOW_QUALITY: "Lectura final requiere revisión humana",
    RiskRule.FEFO_RISK: "Salida posterior a un lote con vencimiento anterior",
    RiskRule.HISTORICAL_ANOMALY: "Ubicación con anomalías recurrentes",
}

COMPARISON_RULES = {
    ComparisonResult.PALLET_MISMATCH: RiskRule.PALLET_MISMATCH,
    ComparisonResult.EXPECTED_PALLET_MISSING: RiskRule.EXPECTED_PALLET_MISSING,
    ComparisonResult.UNEXPECTED_PALLET: RiskRule.UNEXPECTED_PALLET,
}

PHYSICAL_DISCREPANCY_RULES = {
    RiskRule.PALLET_MISMATCH,
    RiskRule.EXPECTED_PALLET_MISSING,
    RiskRule.UNEXPECTED_PALLET,
}


def calculate_risk(
    *,
    context: RiskContext,
    settings: BusinessRuleSettings,
) -> RiskResult:
    if context.historical_anomaly_count < 0:
        raise ValueError("historical_anomaly_count no puede ser negativo")

    active_rules: list[RiskRule] = []
    comparison_rule = COMPARISON_RULES.get(context.comparison_result)
    if comparison_rule is not None:
        active_rules.append(comparison_rule)
    if (
        context.days_to_expiry is not None
        and context.days_to_expiry <= settings.expiry_risk_days
    ):
        active_rules.append(RiskRule.EXPIRING_SOON)
    if context.rotation_level is RotationLevel.HIGH:
        active_rules.append(RiskRule.HIGH_ROTATION)
    if context.low_coverage:
        active_rules.append(RiskRule.LOW_COVERAGE)
    if context.final_quality_status is ReadingStatus.HUMAN_REVIEW_REQUIRED:
        active_rules.append(RiskRule.LOW_QUALITY)
    if context.fefo_risk:
        active_rules.append(RiskRule.FEFO_RISK)
    if context.historical_anomaly_count >= settings.historical_anomaly_min_count:
        active_rules.append(RiskRule.HISTORICAL_ANOMALY)

    weight_map = settings.risk_weights.as_rule_map()
    reasons = tuple(
        RiskReason(
            rule=rule,
            points=weight_map[rule.value],
            label=RULE_LABELS[rule],
        )
        for rule in active_rules
    )
    score = min(sum(reason.points for reason in reasons), 100)
    severity = severity_for_score(score=score, settings=settings)

    if (
        severity is Severity.LOW
        and any(reason.rule in PHYSICAL_DISCREPANCY_RULES for reason in reasons)
    ):
        severity = Severity.MEDIUM

    return RiskResult(score=score, severity=severity, reasons=reasons)


def severity_for_score(*, score: int, settings: BusinessRuleSettings) -> Severity:
    if not 0 <= score <= 100:
        raise ValueError("score debe estar entre 0 y 100")
    thresholds = settings.severity_thresholds
    if score >= thresholds.critical_min:
        return Severity.CRITICAL
    if score >= thresholds.high_min:
        return Severity.HIGH
    if score >= thresholds.medium_min:
        return Severity.MEDIUM
    return Severity.LOW
