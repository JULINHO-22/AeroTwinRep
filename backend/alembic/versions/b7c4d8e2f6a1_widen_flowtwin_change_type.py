"""widen FlowTwin change type storage for expanded classifications

Revision ID: b7c4d8e2f6a1
Revises: f5a1c2d3e4b5
"""

from alembic import op
import sqlalchemy as sa


revision = "b7c4d8e2f6a1"
down_revision = "f5a1c2d3e4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Accommodate values such as PERSISTENT_DISCREPANCY (22 chars)."""

    op.alter_column(
        "flowtwin_changes",
        "change_type",
        existing_type=sa.String(length=14),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Do not shrink here: Alembic downgrades b7 before f5 has removed the
    # expanded classifications, so PostgreSQL would reject persisted values
    # such as PERSISTENT_DISCREPANCY.  A wider VARCHAR is compatible with the
    # f5 schema; its own downgrade removes values that its predecessor cannot
    # represent before restoring the older check constraint.
    pass
