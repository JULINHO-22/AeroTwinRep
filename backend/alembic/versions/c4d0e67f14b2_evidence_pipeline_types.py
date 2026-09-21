"""align evidence types with the evidence pipeline

Revision ID: c4d0e67f14b2
Revises: f3c1a8b4d902
"""

from collections.abc import Sequence

from alembic import op


revision: str = "c4d0e67f14b2"
down_revision: str | None = "f3c1a8b4d902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINT = "evidence_type_allowed"


def _replace(values: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{value}'" for value in values)
    op.create_check_constraint(op.f(CONSTRAINT), "evidence_files", f"evidence_type IN ({allowed})")


def upgrade() -> None:
    op.execute("UPDATE evidence_files SET evidence_type = 'ORIGINAL' WHERE evidence_type IN ('PALLET_READING', 'LOCATION_READING')")
    op.execute("ALTER TABLE evidence_files DROP CONSTRAINT ck_evidence_files_evidence_type")
    _replace(("ORIGINAL", "RESCAN", "EMPTY_CONFIRMATION", "MANUAL_REVIEW"))


def downgrade() -> None:
    op.drop_constraint(op.f(CONSTRAINT), "evidence_files", type_="check")
    op.execute("UPDATE evidence_files SET evidence_type = 'PALLET_READING' WHERE evidence_type IN ('ORIGINAL', 'RESCAN', 'MANUAL_REVIEW')")
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_evidence_files_evidence_type'
            ) THEN
                ALTER TABLE evidence_files
                ADD CONSTRAINT ck_evidence_files_evidence_type
                CHECK (evidence_type IN ('PALLET_READING', 'EMPTY_CONFIRMATION', 'LOCATION_READING'));
            END IF;
        END $$;
    """)
