from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntIdMixin
from app.models.enums import (
    ComparisonResult,
    ExceptionStatus,
    ExceptionType,
    FlowTwinChangeType,
    ResolutionType,
    Severity,
)


class ExceptionEvent(IntIdMixin, Base):
    __tablename__ = "exception_events"
    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="risk_score_range"),
    )

    inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="SET NULL"),
        index=True,
    )
    reading_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspection_readings.id", ondelete="SET NULL"),
        index=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        index=True,
    )
    pallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
        index=True,
    )
    exception_type: Mapped[ExceptionType] = mapped_column(
        Enum(
            ExceptionType,
            name="exception_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(
            Severity,
            name="severity",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        Enum(
            ExceptionStatus,
            name="exception_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resolution_type: Mapped[ResolutionType | None] = mapped_column(
        Enum(
            ResolutionType,
            name="resolution_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolution_comment: Mapped[str | None] = mapped_column(Text)


class FlowTwinChange(IntIdMixin, Base):
    __tablename__ = "flowtwin_changes"

    current_inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_inspection_id: Mapped[int | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="SET NULL"),
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[FlowTwinChangeType] = mapped_column(
        Enum(
            FlowTwinChangeType,
            name="flowtwin_change_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            # Keep schema capacity stable when FlowTwin classifications grow.
            # The initial migration inferred VARCHAR(14) from the four first
            # values, while PERSISTENT_DISCREPANCY requires more space.
            length=32,
        ),
        nullable=False,
    )
    previous_pallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
    )
    current_pallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
    )
    previous_result: Mapped[ComparisonResult | None] = mapped_column(
        Enum(
            ComparisonResult,
            name="flowtwin_previous_result",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        )
    )
    current_result: Mapped[ComparisonResult | None] = mapped_column(
        Enum(
            ComparisonResult,
            name="flowtwin_current_result",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        )
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AuditLog(IntIdMixin, Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class AgentQueryLog(IntIdMixin, Base):
    __tablename__ = "agent_query_logs"
    __table_args__ = (
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="latency_non_negative"),
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    tool_called: Mapped[str | None] = mapped_column(String(100))
    response: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
