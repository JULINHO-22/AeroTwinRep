import json

import pytest

from app.domain.settings import load_business_rule_settings


def test_default_business_settings_are_valid() -> None:
    settings = load_business_rule_settings()
    assert settings.max_reading_attempts == 2
    assert settings.rotation_thresholds.high_min == 300
    assert settings.risk_weights.expected_pallet_missing == 40


def test_missing_critical_setting_fails_clearly(tmp_path) -> None:
    invalid_path = tmp_path / "settings.json"
    invalid_path.write_text(json.dumps({"rescan_quality_threshold": 85}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="configuración de reglas es inválida"):
        load_business_rule_settings(invalid_path)

