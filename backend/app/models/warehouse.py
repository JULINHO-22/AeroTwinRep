from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntIdMixin, TimestampMixin
from app.models.enums import MovementType, PalletStatus


class WarehouseZone(IntIdMixin, TimestampMixin, Base):
    __tablename__ = "warehouse_zones"

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    locations: Mapped[list[Location]] = relationship(back_populates="zone")


class Location(IntIdMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("row_index >= 1", name="row_index_positive"),
        CheckConstraint("column_index >= 1", name="column_index_positive"),
        CheckConstraint("level >= 1 AND level <= 20", name="level_reasonable"),
    )

    zone_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_zones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    zone: Mapped[WarehouseZone] = relationship(back_populates="locations")
    expected_inventory: Mapped[ExpectedInventory | None] = relationship(
        back_populates="location",
        uselist=False,
    )


class Product(IntIdMixin, TimestampMixin, Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    lots: Mapped[list[Lot]] = relationship(back_populates="product")


class Lot(IntIdMixin, TimestampMixin, Base):
    __tablename__ = "lots"
    __table_args__ = (
        CheckConstraint("expires_at > manufactured_at", name="expiry_after_manufacture"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lot_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    manufactured_at: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    product: Mapped[Product] = relationship(back_populates="lots")
    pallets: Mapped[list[Pallet]] = relationship(back_populates="lot")


class Pallet(IntIdMixin, TimestampMixin, Base):
    __tablename__ = "pallets"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
    )

    pallet_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PalletStatus] = mapped_column(
        Enum(
            PalletStatus,
            name="pallet_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    lot: Mapped[Lot] = relationship(back_populates="pallets")
    expected_inventory: Mapped[ExpectedInventory | None] = relationship(
        back_populates="expected_pallet",
        uselist=False,
    )


class ExpectedInventory(IntIdMixin, Base):
    __tablename__ = "expected_inventory"

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    expected_pallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
        unique=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    location: Mapped[Location] = relationship(back_populates="expected_inventory")
    expected_pallet: Mapped[Pallet | None] = relationship(back_populates="expected_inventory")


class MovementHistory(IntIdMixin, Base):
    __tablename__ = "movement_history"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lot_id: Mapped[int | None] = mapped_column(
        ForeignKey("lots.id", ondelete="SET NULL"),
        index=True,
    )
    pallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pallets.id", ondelete="SET NULL"),
        index=True,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            name="movement_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    source_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse_zones.id", ondelete="SET NULL"),
    )
    destination_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouse_zones.id", ondelete="SET NULL"),
    )
    notes: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship()
    lot: Mapped[Lot | None] = relationship()
    pallet: Mapped[Pallet | None] = relationship()
    source_zone: Mapped[WarehouseZone | None] = relationship(
        foreign_keys=[source_zone_id],
    )
    destination_zone: Mapped[WarehouseZone | None] = relationship(
        foreign_keys=[destination_zone_id],
    )

