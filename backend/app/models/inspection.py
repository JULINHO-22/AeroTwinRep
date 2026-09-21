from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntIdMixin
from app.models.enums import (
    ComparisonResult,
    EvidenceType,
    InspectionStatus,
    ObservedState,
    ReadingStatus,
    SourceType,
)


class Inspection(IntIdMixin, Base):
    __tablename__ = "inspections"

    zone_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_zones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    started_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(
            InspectionStatus,
            name="inspection_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    readings: Mapped[list[InspectionReading]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
    )


class InspectionReading(IntIdMixin, Base):
    __tablename__ = "inspection_readings"
    __table_args__ = (
        CheckConstraint("quality_score >= 0 AND quality_score <= 100", name="quality_score_range"),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        Index(
            "uq_inspection_readings_final_group",
            "inspection_id",
            "location_id",
            "reading_group_id",
            unique=True,
            postgresql_where=text("is_final = true"),
        ),
    )

    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_reading_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    reading_group_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_pallet_id_at_inspection: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
    )
    observed_pallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
    )
    observed_state: Mapped[ObservedState] = mapped_column(
        Enum(
            ObservedState,
            name="observed_state",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reading_status: Mapped[ReadingStatus] = mapped_column(
        Enum(
            ReadingStatus,
            name="reading_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    comparison_result: Mapped[ComparisonResult] = mapped_column(
        Enum(
            ComparisonResult,
            name="comparison_result",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="source_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    empty_confirmed_by_operator: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    inspection: Mapped[Inspection] = relationship(back_populates="readings")
    evidence_files: Mapped[list[EvidenceFile]] = relationship(
        back_populates="reading",
        cascade="all, delete-orphan",
    )


class EvidenceFile(IntIdMixin, Base):
    __tablename__ = "evidence_files"
    __table_args__ = (
        CheckConstraint("width IS NULL OR width > 0", name="width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="height_positive"),
    )

    reading_id: Mapped[int] = mapped_column(
        ForeignKey("inspection_readings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="evidence_source_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(
            EvidenceType,
            name="evidence_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    reading: Mapped[InspectionReading] = relationship(back_populates="evidence_files")

