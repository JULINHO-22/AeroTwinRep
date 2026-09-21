from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.api.errors import ApiError
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.models.warehouse import Location, WarehouseZone
from app.services.warehouse_memory_service import (
    get_location_history,
    location_list,
    location_memory,
    zone_memory,
)
router=APIRouter(tags=["memory"]); viewer=require_roles(UserRole.OPERATOR,UserRole.SUPERVISOR)
@router.get('/memory/locations')
def locations(_user: Annotated[User,Depends(viewer)],session: Annotated[Session,Depends(get_db)]): return {"items":location_list(session)}
@router.get('/memory/locations/{location_id}')
def location(location_id:int,_user:Annotated[User,Depends(viewer)],session:Annotated[Session,Depends(get_db)]):
    loc=session.get(Location,location_id)
    if not loc: raise ApiError(status_code=404,code='LOCATION_NOT_FOUND',message='La ubicación no existe.')
    # Keep /memory/locations lightweight. The detail endpoint adds the final
    # reading timeline required by Location History.
    payload = location_memory(session,loc)
    payload['timeline'] = get_location_history(session, loc)
    return payload
@router.get('/memory/zones/{zone_id}')
def zone(zone_id:int,_user:Annotated[User,Depends(viewer)],session:Annotated[Session,Depends(get_db)]):
    zone=session.get(WarehouseZone,zone_id)
    if not zone: raise ApiError(status_code=404,code='ZONE_NOT_FOUND',message='La zona no existe.')
    return zone_memory(session,zone)
