from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.api.errors import ApiError
from app.config import get_settings


MAX_EVIDENCE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/jpg"}


@dataclass(frozen=True)
class StagedEvidence:
    temporary_path: Path
    mime_type: str
    checksum: str
    width: int
    height: int
    captured_at: datetime


class EvidenceStorage:
    """Stages an upload before the reading transaction, then finalizes it safely."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.temp_root = self.root / ".tmp"

    async def stage(self, upload: UploadFile) -> StagedEvidence:
        mime_type = (upload.content_type or "").lower()
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ApiError(
                status_code=422,
                code="UNSUPPORTED_EVIDENCE_MIME",
                message="La evidencia debe ser una imagen JPEG.",
            )

        content = await upload.read(MAX_EVIDENCE_BYTES + 1)
        if not content:
            raise ApiError(
                status_code=422,
                code="EMPTY_EVIDENCE_FILE",
                message="El archivo de evidencia está vacío.",
            )
        if len(content) > MAX_EVIDENCE_BYTES:
            raise ApiError(
                status_code=422,
                code="EVIDENCE_FILE_TOO_LARGE",
                message="La evidencia supera el límite de 5 MB.",
                details={"max_bytes": MAX_EVIDENCE_BYTES},
            )

        try:
            from io import BytesIO

            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                if image.format != "JPEG":
                    raise ValueError("not jpeg")
                width, height = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ApiError(
                status_code=422,
                code="INVALID_JPEG_EVIDENCE",
                message="La evidencia no contiene un JPEG válido.",
            ) from exc

        self.temp_root.mkdir(parents=True, exist_ok=True)
        temporary_path = self.temp_root / f"{uuid4()}.upload"
        temporary_path.write_bytes(content)
        return StagedEvidence(
            temporary_path=temporary_path,
            mime_type="image/jpeg",
            checksum=hashlib.sha256(content).hexdigest(),
            width=width,
            height=height,
            captured_at=datetime.now(timezone.utc),
        )

    def final_relative_path(self, inspection_id: int) -> str:
        return f"inspection_{inspection_id}/{uuid4()}.jpg"

    def finalize(self, staged: StagedEvidence, relative_path: str) -> Path:
        destination = self.resolve(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged.temporary_path, destination)
        return destination

    def discard(self, staged: StagedEvidence | None) -> None:
        if staged is not None:
            staged.temporary_path.unlink(missing_ok=True)

    def resolve(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate == self.root or self.root not in candidate.parents:
            raise ApiError(
                status_code=500,
                code="INVALID_EVIDENCE_STORAGE_PATH",
                message="La ruta interna de evidencia es inválida.",
            )
        return candidate


def get_evidence_storage() -> EvidenceStorage:
    configured = Path(get_settings().evidence_storage_path)
    if not configured.is_absolute():
        configured = Path(__file__).resolve().parents[2] / configured
    return EvidenceStorage(configured)
