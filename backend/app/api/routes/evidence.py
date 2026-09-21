from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.errors import ApiError
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.models.inspection import EvidenceFile, Inspection, InspectionReading
from app.services.evidence_storage import EvidenceStorage, get_evidence_storage


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/{evidence_id}")
def get_evidence(
    evidence_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    evidence_storage: Annotated[EvidenceStorage, Depends(get_evidence_storage)],
) -> FileResponse:
    evidence = session.get(EvidenceFile, evidence_id)
    if evidence is None:
        raise ApiError(status_code=404, code="EVIDENCE_NOT_FOUND", message="La evidencia no existe.")
    reading = session.get(InspectionReading, evidence.reading_id)
    inspection = session.get(Inspection, reading.inspection_id) if reading else None
    if inspection is None or (
        user.role is not UserRole.SUPERVISOR and inspection.started_by != user.id
    ):
        raise ApiError(status_code=403, code="EVIDENCE_FORBIDDEN", message="No tienes acceso a esta evidencia.")
    file_path = evidence_storage.resolve(evidence.file_path)
    if not file_path.is_file():
        raise ApiError(status_code=404, code="EVIDENCE_FILE_MISSING", message="El archivo de evidencia no está disponible.")
    return FileResponse(file_path, media_type=evidence.mime_type, filename=f"evidence-{evidence.id}.jpg")
