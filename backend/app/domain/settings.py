import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class RotationThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    high_min: int = Field(ge=1)
    medium_min: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "RotationThresholds":
        if self.high_min <= self.medium_min:
            raise ValueError("rotation_thresholds.high_min debe ser mayor que medium_min")
        return self


class SeverityThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical_min: int = Field(ge=1, le=100)
    high_min: int = Field(ge=1, le=100)
    medium_min: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def validate_order(self) -> "SeverityThresholds":
        if not self.medium_min < self.high_min < self.critical_min:
            raise ValueError(
                "severity_thresholds debe cumplir medium_min < high_min < critical_min"
            )
        return self


class RiskWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pallet_mismatch: int = Field(alias="PALLET_MISMATCH", ge=0)
    expected_pallet_missing: int = Field(alias="EXPECTED_PALLET_MISSING", ge=0)
    unexpected_pallet: int = Field(alias="UNEXPECTED_PALLET", ge=0)
    expiring_soon: int = Field(alias="EXPIRING_SOON", ge=0)
    high_rotation: int = Field(alias="HIGH_ROTATION", ge=0)
    low_coverage: int = Field(default=25, alias="LOW_COVERAGE", ge=0)
    low_quality: int = Field(alias="LOW_QUALITY", ge=0)
    fefo_risk: int = Field(alias="FEFO_RISK", ge=0)
    historical_anomaly: int = Field(alias="HISTORICAL_ANOMALY", ge=0)

    def as_rule_map(self) -> dict[str, int]:
        return self.model_dump(by_alias=True)


class BusinessRuleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rescan_quality_threshold: int = Field(ge=0, le=100)
    max_reading_attempts: int = Field(ge=1)
    expiry_warning_days: int = Field(ge=1)
    expiry_risk_days: int = Field(ge=0)
    low_coverage_days: float = Field(gt=0)
    rotation_window_days: int = Field(ge=1)
    rotation_thresholds: RotationThresholds
    historical_anomaly_min_count: int = Field(ge=1)
    severity_thresholds: SeverityThresholds
    risk_weights: RiskWeights

    @model_validator(mode="after")
    def validate_expiry_thresholds(self) -> "BusinessRuleSettings":
        if self.expiry_warning_days < self.expiry_risk_days:
            raise ValueError(
                "expiry_warning_days debe ser mayor o igual que expiry_risk_days"
            )
        return self


def default_settings_path() -> Path:
    return Path(__file__).resolve().parents[2] / "settings.json"


@lru_cache(maxsize=4)
def load_business_rule_settings(path: str | Path | None = None) -> BusinessRuleSettings:
    settings_path = Path(path) if path is not None else default_settings_path()
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        return BusinessRuleSettings.model_validate(payload)
    except FileNotFoundError as exc:
        raise RuntimeError(f"No existe la configuración de reglas: {settings_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"La configuración de reglas no contiene JSON válido: {settings_path}"
        ) from exc
    except ValidationError as exc:
        raise RuntimeError(
            f"La configuración de reglas es inválida: {settings_path}\n{exc}"
        ) from exc
