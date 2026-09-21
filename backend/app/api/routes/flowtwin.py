from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import require_roles
from app.api.errors import ApiError
from app.db.session import get_db
from app.models.enums import InspectionStatus, UserRole
from app.models.identity import User
from app.models.inspection import Inspection
from app.models.warehouse import Location, Pallet
from app.services.flowtwin_service import calculate, exception_for

router = APIRouter(tags=["flowtwin"])
viewer = require_roles(UserRole.OPERATOR, UserRole.SUPERVISOR)

@router.get("/flowtwin/changes")
def changes(user: Annotated[User, Depends(viewer)], session: Annotated[Session, Depends(get_db)], inspection_id: int | None = Query(default=None)) -> dict:
    current = session.get(Inspection, inspection_id) if inspection_id else session.scalar(select(Inspection).where(Inspection.status == InspectionStatus.COMPLETED).order_by(Inspection.completed_at.desc()))
    if not current: raise ApiError(status_code=404, code="INSPECTION_NOT_FOUND", message="No existe una inspección completada para comparar.")
    previous, rows, unchanged = calculate(session, current)
    if not previous: return {"status": "NO_PREVIOUS_INSPECTION", "current_inspection_id": current.id, "previous_inspection_id": None, "summary": {"compared": 0, "unchanged": 0, "changed": 0, "persistent": 0, "unresolved": 0}, "changes": []}
    items = []
    for row in rows:
        loc, old, now = session.get(Location, row.location_id), session.get(Pallet, row.previous.observed_pallet_id) if row.previous.observed_pallet_id else None, session.get(Pallet, row.current.observed_pallet_id) if row.current.observed_pallet_id else None
        event = exception_for(session, row.current.id, current.id, row.location_id)
        def display(reading, pallet):
            if pallet: return pallet.pallet_code
            return "Vacío confirmado" if reading.observed_state.value == "EMPTY" and reading.empty_confirmed_by_operator else "No resuelto"
        items.append({"location": loc.code, "location_id": row.location_id, "type": row.type.value, "previous": display(row.previous, old), "current": display(row.current, now), "risk_score": event.risk_score if event else 0, "exception_id": event.id if event else None})
    return {"status": "OK", "current_inspection_id": current.id, "previous_inspection_id": previous.id, "summary": {"compared": unchanged + len(rows), "unchanged": unchanged, "changed": len(rows), "persistent": sum(x.type.value == "PERSISTENT_DISCREPANCY" for x in rows), "unresolved": sum(x.type.value == "BECAME_UNRESOLVED" for x in rows)}, "changes": items}
