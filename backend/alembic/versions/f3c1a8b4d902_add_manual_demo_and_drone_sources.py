"""add MANUAL_DEMO and DRONE source values

Revision ID: f3c1a8b4d902
Revises: a2ae44d701c5
Create Date: 2026-09-20
"""

from collections.abc import Sequence

from alembic import op


revision: str = "f3c1a8b4d902"
down_revision: str | None = "a2ae44d701c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


READING_CONSTRAINT = "ck_inspection_readings_source_type"
EVIDENCE_CONSTRAINT = "ck_evidence_files_evidence_source_type"


def _replace_constraint(table: str, constraint: str, values: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{value}'" for value in values)
    op.drop_constraint(op.f(constraint), table, type_="check")
    op.create_check_constraint(op.f(constraint), table, f"source_type IN ({allowed})")


def upgrade() -> None:
    values = (
        "ANDROID_CAMERA",
        "MANUAL_DEMO",
        "DRONE",
        "MANUAL",
        "SEED_SYSTEM",
        "WMS_IMPORT",
    )
    _replace_constraint("inspection_readings", READING_CONSTRAINT, values)
    _replace_constraint("evidence_files", EVIDENCE_CONSTRAINT, values)


def downgrade() -> None:
    op.execute(
        "UPDATE inspection_readings SET source_type = 'MANUAL' "
        "WHERE source_type IN ('MANUAL_DEMO', 'DRONE')"
    )
    op.execute(
        "UPDATE evidence_files SET source_type = 'MANUAL' "
        "WHERE source_type IN ('MANUAL_DEMO', 'DRONE')"
    )
    values = ("ANDROID_CAMERA", "MANUAL", "SEED_SYSTEM", "WMS_IMPORT")
    _replace_constraint("inspection_readings", READING_CONSTRAINT, values)
    _replace_constraint("evidence_files", EVIDENCE_CONSTRAINT, values)
