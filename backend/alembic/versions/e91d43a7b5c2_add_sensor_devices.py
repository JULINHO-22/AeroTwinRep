"""add device identities and mission assignment

Revision ID: e91d43a7b5c2
Revises: c4d0e67f14b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e91d43a7b5c2"
down_revision: str | None = "c4d0e67f14b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sensor_devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="OFFLINE", nullable=False),
        sa.Column("assigned_inspection_id", sa.Integer(), nullable=True),
        sa.Column("last_reading_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_inspection_id"], ["inspections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_reading_id"], ["inspection_readings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code"),
    )
    op.create_index(op.f("ix_sensor_devices_assigned_inspection_id"), "sensor_devices", ["assigned_inspection_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_sensor_devices_assigned_inspection_id"), table_name="sensor_devices")
    op.drop_table("sensor_devices")
