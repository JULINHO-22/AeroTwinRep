from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import ApiError
from app.db.session import get_db
from app.models.identity import User
from app.models.warehouse import Location, WarehouseZone
from app.schemas.warehouse import LocationResponse, ZoneResponse


router = APIRouter(tags=["warehouse"])


@router.get("/zones", response_model=list[ZoneResponse])
def list_zones(
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ZoneResponse]:
    zones = session.scalars(
        select(WarehouseZone)
        .where(WarehouseZone.is_active.is_(True))
        .order_by(WarehouseZone.code)
    ).all()
    return [
        ZoneResponse(id=zone.id, code=zone.code, name=zone.name, is_active=zone.is_active)
        for zone in zones
    ]


@router.get("/locations/code/{code}", response_model=LocationResponse)
def get_location_by_code(
    code: str,
    _user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> LocationResponse:
    normalized = code.strip().upper()
    row = session.execute(
        select(Location, WarehouseZone)
        .join(WarehouseZone, WarehouseZone.id == Location.zone_id)
        .where(Location.code == normalized, Location.is_active.is_(True))
    ).one_or_none()
    if row is None:
        raise ApiError(
            status_code=404,
            code="LOCATION_NOT_FOUND",
            message="La ubicación indicada no existe o no está activa.",
            details={"code": normalized},
        )
    location, zone = row
    return LocationResponse(
        id=location.id,
        code=location.code,
        zone_id=location.zone_id,
        zone_code=zone.code,
        is_active=location.is_active,
    )
