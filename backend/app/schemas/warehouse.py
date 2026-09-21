from pydantic import BaseModel


class ZoneResponse(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool


class LocationResponse(BaseModel):
    id: int
    code: str
    zone_id: int
    zone_code: str
    is_active: bool
