from datetime import datetime

from pydantic import BaseModel, Field


class SensorRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class SensorRegisterResponse(BaseModel):
    id: int
    device_code: str
    name: str
    device_token: str


class SensorMissionResponse(BaseModel):
    inspection_id: int
    zone: str
    status: str


class SensorNextObjectiveResponse(BaseModel):
    action: str
    reason: str
    location_id: int | None = None
    location_code: str | None = None
    priority: int | None = None


class SensorTelemetryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=120)
    detected_code: str | None = Field(default=None, max_length=50)


class SensorLastReadingResponse(BaseModel):
    evidence_id: int
    location_code: str
    observed_pallet_code: str | None
    comparison_result: str
    created_at: datetime


class SensorStatusResponse(BaseModel):
    id: int
    device_code: str
    name: str
    status: str
    last_seen_at: datetime | None
    mission: SensorMissionResponse | None
    last_reading: SensorLastReadingResponse | None
    live_message: str | None = None
    last_detected_code: str | None = None
