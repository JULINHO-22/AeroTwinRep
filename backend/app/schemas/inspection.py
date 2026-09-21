from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    ComparisonResult,
    InspectionStatus,
    ObservedState,
    ReadingStatus,
    Severity,
    SourceType,
    EvidenceType,
)


class InspectionCreateRequest(BaseModel):
    zone_id: int = Field(gt=0)


class InspectionResponse(BaseModel):
    id: int
    zone_id: int
    zone_code: str
    status: InspectionStatus
    started_at: datetime
    total_locations: int
    completed_locations: int


class LiveInspectionLastReadingResponse(BaseModel):
    id: int
    location_id: int
    location_code: str
    reading_status: str
    comparison_result: str
    expected_pallet_code: str | None = None
    observed_pallet_code: str | None = None
    risk_score: int = 0
    severity: str | None = None
    exception_id: int | None = None
    evidence_id: int | None = None
    created_at: datetime


class LiveInspectionTargetResponse(BaseModel):
    """A Core-owned objective; the client only displays or follows it."""

    action: str
    location_id: int | None = None
    location_code: str | None = None
    reason: str
    priority: int


class LiveInspectionLocationResponse(BaseModel):
    id: int
    code: str
    row_index: int
    column_index: int
    level: int
    physical_state: str
    expected_pallet_code: str | None = None
    observed_pallet_code: str | None = None
    product: str | None = None
    sku: str | None = None
    lot: str | None = None
    days_to_expiry: int | None = None
    rotation: str | None = None
    coverage_days: float | None = None
    fefo_risk: bool = False
    expected_quantity: int | None = None
    observed_quantity: int | None = None
    comparison_result: str | None = None
    result: str | None = None
    risk_score: int = 0
    severity: str | None = None
    badges: list[str] = Field(default_factory=list)
    exception_id: int | None = None
    evidence_id: int | None = None
    loss_prevention_signal: str | None = None
    loss_prevention_reason: str | None = None
    slotting_suggestion: str | None = None
    updated_at: datetime | None = None


class LiveInspectionStateResponse(BaseModel):
    inspection_id: int
    zone: str
    total: int
    inspected: int
    validated: int
    review_required: int
    pending: int
    coverage_percent: float
    last_final_reading: LiveInspectionLastReadingResponse | None = None
    current_target: LiveInspectionTargetResponse
    locations: list[LiveInspectionLocationResponse]


class ReadingCreateRequest(BaseModel):
    client_reading_id: UUID
    location_id: int = Field(gt=0)
    reading_group_id: UUID
    attempt_number: int = Field(ge=1)
    observed_pallet_code: str | None = Field(default=None, max_length=50)
    observed_state: ObservedState
    quality_score: int = Field(ge=0, le=100)
    source_type: SourceType = SourceType.MANUAL_DEMO
    empty_confirmed_by_operator: bool = False

    @field_validator("observed_pallet_code")
    @classmethod
    def normalize_pallet_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class EvidenceSummary(BaseModel):
    id: int
    mime_type: str
    evidence_type: EvidenceType


class ReadingResponse(BaseModel):
    id: int
    inspection_id: int
    client_reading_id: UUID
    location_id: int
    location_code: str
    reading_group_id: UUID
    attempt_number: int
    expected_pallet_code: str | None
    observed_pallet_code: str | None
    observed_state: ObservedState
    quality_score: int
    reading_status: ReadingStatus
    comparison_result: ComparisonResult
    is_final: bool
    risk_score: int
    severity: Severity
    risk_breakdown: dict[str, int]
    idempotent: bool
    evidence: EvidenceSummary
    created_at: datetime


class EvidenceAttemptResponse(BaseModel):
    id: int
    attempt_number: int
    evidence_id: int
    captured_at: datetime


class ReviewExceptionResponse(BaseModel):
    reading_group_id: UUID
    location_code: str
    expected_pallet_code: str | None
    status: ReadingStatus
    attempts: int
    evidence_attempts: list[EvidenceAttemptResponse]


class EmptyConfirmationRequest(BaseModel):
    reading_group_id: UUID
