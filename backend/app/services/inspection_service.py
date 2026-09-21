from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.models.enums import InspectionStatus, UserRole
from app.models.identity import User
from app.models.inspection import Inspection, InspectionReading
from app.models.warehouse import Location, WarehouseZone


def create_inspection(*, session: Session, zone_id: int, user: User) -> Inspection:
    zone = session.get(WarehouseZone, zone_id)
    if zone is None or not zone.is_active:
        raise ApiError(
            status_code=404,
            code="ZONE_NOT_FOUND",
            message="La zona indicada no existe o no está activa.",
            details={"zone_id": zone_id},
        )
    active = session.scalar(
        select(Inspection).where(
            Inspection.started_by == user.id,
            Inspection.status == InspectionStatus.IN_PROGRESS,
        )
    )
    if active is not None:
        raise ApiError(
            status_code=409,
            code="ACTIVE_INSPECTION_EXISTS",
            message="Ya tienes una inspección en curso.",
            details={"inspection_id": active.id},
        )
    inspection = Inspection(
        zone_id=zone.id,
        started_by=user.id,
        status=InspectionStatus.IN_PROGRESS,
    )
    session.add(inspection)
    session.commit()
    session.refresh(inspection)
    return inspection


def get_active_inspection(*, session: Session, user: User) -> Inspection | None:
    return session.scalar(
        select(Inspection)
        .where(
            Inspection.started_by == user.id,
            Inspection.status == InspectionStatus.IN_PROGRESS,
        )
        .order_by(Inspection.started_at.desc())
        .limit(1)
    )


def get_visible_inspection(
    *, session: Session, inspection_id: int, user: User
) -> Inspection:
    inspection = session.get(Inspection, inspection_id)
    if inspection is None:
        raise ApiError(
            status_code=404,
            code="INSPECTION_NOT_FOUND",
            message="La inspección indicada no existe.",
            details={"inspection_id": inspection_id},
        )
    if user.role is UserRole.OPERATOR and inspection.started_by != user.id:
        raise ApiError(
            status_code=403,
            code="INSPECTION_FORBIDDEN",
            message="La inspección pertenece a otro operador.",
        )
    return inspection


def inspection_progress(*, session: Session, inspection: Inspection) -> dict:
    zone = session.get(WarehouseZone, inspection.zone_id)
    total = session.scalar(
        select(func.count()).select_from(Location).where(
            Location.zone_id == inspection.zone_id,
            Location.is_active.is_(True),
        )
    ) or 0
    completed = session.scalar(
        select(func.count(func.distinct(InspectionReading.location_id))).where(
            InspectionReading.inspection_id == inspection.id,
            InspectionReading.is_final.is_(True),
        )
    ) or 0
    return {
        "id": inspection.id,
        "zone_id": inspection.zone_id,
        "zone_code": zone.code if zone is not None else "",
        "status": inspection.status,
        "started_at": inspection.started_at,
        "total_locations": total,
        "completed_locations": completed,
    }
