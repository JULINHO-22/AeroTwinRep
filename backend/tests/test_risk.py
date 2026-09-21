import pytest

from app.domain.analytics import RotationLevel
from app.domain.risk import RiskContext, RiskRule, calculate_risk, severity_for_score
from app.domain.settings import load_business_rule_settings
from app.models.enums import ComparisonResult, ReadingStatus, Severity


@pytest.fixture(scope="module")
def rules():
    return load_business_rule_settings()


@pytest.mark.parametrize(
    ("score", "severity"),
    [
        (0, Severity.LOW),
        (39, Severity.LOW),
        (40, Severity.MEDIUM),
        (59, Severity.MEDIUM),
        (60, Severity.HIGH),
        (79, Severity.HIGH),
        (80, Severity.CRITICAL),
        (100, Severity.CRITICAL),
    ],
)
def test_severity_boundaries(rules, score, severity) -> None:
    assert severity_for_score(score=score, settings=rules) is severity


def test_physical_discrepancy_has_minimum_medium_severity(rules) -> None:
    result = calculate_risk(
        context=RiskContext(comparison_result=ComparisonResult.PALLET_MISMATCH),
        settings=rules,
    )
    assert result.score == 35
    assert result.severity is Severity.MEDIUM


def test_risk_examples_respect_expected_scale(rules) -> None:
    result_90 = calculate_risk(
        context=RiskContext(
            comparison_result=ComparisonResult.PALLET_MISMATCH,
            days_to_expiry=10,
            rotation_level=RotationLevel.HIGH,
            final_quality_status=ReadingStatus.HUMAN_REVIEW_REQUIRED,
            fefo_risk=True,
        ),
        settings=rules,
    )
    result_75 = calculate_risk(
        context=RiskContext(
            comparison_result=ComparisonResult.EXPECTED_PALLET_MISSING,
            days_to_expiry=10,
            rotation_level=RotationLevel.HIGH,
        ),
        settings=rules,
    )
    result_55 = calculate_risk(
        context=RiskContext(
            comparison_result=ComparisonResult.EXPECTED_PALLET_MISSING,
            rotation_level=RotationLevel.HIGH,
        ),
        settings=rules,
    )

    assert (result_90.score, result_90.severity) == (90, Severity.CRITICAL)
    assert (result_75.score, result_75.severity) == (75, Severity.HIGH)
    assert (result_55.score, result_55.severity) == (55, Severity.MEDIUM)


def test_risk_is_capped_and_has_structured_breakdown(rules) -> None:
    result = calculate_risk(
        context=RiskContext(
            comparison_result=ComparisonResult.EXPECTED_PALLET_MISSING,
            days_to_expiry=-2,
            rotation_level=RotationLevel.HIGH,
            final_quality_status=ReadingStatus.HUMAN_REVIEW_REQUIRED,
            fefo_risk=True,
            historical_anomaly_count=2,
        ),
        settings=rules,
    )
    assert result.score == 100
    assert result.severity is Severity.CRITICAL
    assert {reason.rule for reason in result.reasons} == {
        RiskRule.EXPECTED_PALLET_MISSING,
        RiskRule.EXPIRING_SOON,
        RiskRule.HIGH_ROTATION,
        RiskRule.LOW_QUALITY,
        RiskRule.FEFO_RISK,
        RiskRule.HISTORICAL_ANOMALY,
    }
    assert all(reason.points >= 0 and reason.label for reason in result.reasons)


def test_successful_final_rescan_does_not_keep_low_quality_penalty(rules) -> None:
    result = calculate_risk(
        context=RiskContext(
            comparison_result=ComparisonResult.CORRECT,
            final_quality_status=ReadingStatus.ACCEPTED,
        ),
        settings=rules,
    )
    assert result.score == 0
    assert not result.reasons

