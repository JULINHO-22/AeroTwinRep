"""align_domain_status_values

Revision ID: a2ae44d701c5
Revises: 75895c0372ab
Create Date: 2026-09-20 00:09:19.013809
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a2ae44d701c5'
down_revision: str | None = '75895c0372ab'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _drop_domain_checks()
    op.alter_column(
        "inspection_readings",
        "reading_status",
        existing_type=sa.String(length=15),
        type_=sa.String(length=21),
        existing_nullable=False,
    )
    op.execute(
        "UPDATE inspection_readings SET observed_state = 'UNRESOLVED' "
        "WHERE observed_state = 'UNREADABLE'"
    )
    op.execute(
        "UPDATE inspection_readings SET reading_status = 'RESCAN_REQUIRED' "
        "WHERE reading_status = 'REQUIRES_RESCAN'"
    )
    op.execute(
        "UPDATE inspection_readings SET reading_status = 'HUMAN_REVIEW_REQUIRED' "
        "WHERE reading_status = 'REJECTED'"
    )
    op.execute(
        "UPDATE inspection_readings SET comparison_result = 'CORRECT' "
        "WHERE comparison_result = 'MATCH'"
    )
    op.execute(
        "UPDATE inspection_readings SET comparison_result = 'CORRECT_EMPTY' "
        "WHERE comparison_result = 'EXPECTED_EMPTY'"
    )
    op.execute(
        "UPDATE inspection_readings SET comparison_result = 'UNRESOLVED' "
        "WHERE comparison_result = 'UNVERIFIED'"
    )
    for column_name in ("previous_result", "current_result"):
        op.execute(
            f"UPDATE flowtwin_changes SET {column_name} = 'CORRECT' "
            f"WHERE {column_name} = 'MATCH'"
        )
        op.execute(
            f"UPDATE flowtwin_changes SET {column_name} = 'CORRECT_EMPTY' "
            f"WHERE {column_name} = 'EXPECTED_EMPTY'"
        )
        op.execute(
            f"UPDATE flowtwin_changes SET {column_name} = 'UNRESOLVED' "
            f"WHERE {column_name} = 'UNVERIFIED'"
        )
    _create_new_domain_checks()


def downgrade() -> None:
    _drop_domain_checks()
    op.execute(
        "UPDATE inspection_readings SET observed_state = 'UNREADABLE' "
        "WHERE observed_state = 'UNRESOLVED'"
    )
    op.execute(
        "UPDATE inspection_readings SET reading_status = 'REQUIRES_RESCAN' "
        "WHERE reading_status = 'RESCAN_REQUIRED'"
    )
    op.execute(
        "UPDATE inspection_readings SET reading_status = 'REJECTED' "
        "WHERE reading_status = 'HUMAN_REVIEW_REQUIRED'"
    )
    op.execute(
        "UPDATE inspection_readings SET comparison_result = 'MATCH' "
        "WHERE comparison_result = 'CORRECT'"
    )
    op.execute(
        "UPDATE inspection_readings SET comparison_result = 'EXPECTED_EMPTY' "
        "WHERE comparison_result = 'CORRECT_EMPTY'"
    )
    op.execute(
        "UPDATE inspection_readings SET comparison_result = 'UNVERIFIED' "
        "WHERE comparison_result = 'UNRESOLVED'"
    )
    for column_name in ("previous_result", "current_result"):
        op.execute(
            f"UPDATE flowtwin_changes SET {column_name} = 'MATCH' "
            f"WHERE {column_name} = 'CORRECT'"
        )
        op.execute(
            f"UPDATE flowtwin_changes SET {column_name} = 'EXPECTED_EMPTY' "
            f"WHERE {column_name} = 'CORRECT_EMPTY'"
        )
        op.execute(
            f"UPDATE flowtwin_changes SET {column_name} = 'UNVERIFIED' "
            f"WHERE {column_name} = 'UNRESOLVED'"
        )
    op.alter_column(
        "inspection_readings",
        "reading_status",
        existing_type=sa.String(length=21),
        type_=sa.String(length=15),
        existing_nullable=False,
    )
    _create_old_domain_checks()


def _drop_domain_checks() -> None:
    for constraint_name in (
        op.f("ck_inspection_readings_observed_state"),
        op.f("ck_inspection_readings_reading_status"),
        "ck_inspection_readings_comparison_result",
    ):
        op.drop_constraint(op.f(constraint_name), "inspection_readings", type_="check")
    for constraint_name in (
        "ck_flowtwin_changes_flowtwin_previous_result",
        "ck_flowtwin_changes_flowtwin_current_result",
    ):
        op.drop_constraint(op.f(constraint_name), "flowtwin_changes", type_="check")


def _create_new_domain_checks() -> None:
    op.create_check_constraint(
        op.f("ck_inspection_readings_observed_state"),
        "inspection_readings",
        "observed_state IN ('PALLET', 'EMPTY', 'UNRESOLVED')",
    )
    op.create_check_constraint(
        op.f("ck_inspection_readings_reading_status"),
        "inspection_readings",
        "reading_status IN ('ACCEPTED', 'RESCAN_REQUIRED', 'HUMAN_REVIEW_REQUIRED')",
    )
    _create_comparison_checks(
        ("CORRECT", "PALLET_MISMATCH", "CORRECT_EMPTY", "UNEXPECTED_PALLET", "EXPECTED_PALLET_MISSING", "UNRESOLVED")
    )


def _create_old_domain_checks() -> None:
    op.create_check_constraint(
        "ck_inspection_readings_observed_state",
        "inspection_readings",
        "observed_state IN ('PALLET', 'EMPTY', 'UNREADABLE')",
    )
    op.create_check_constraint(
        "ck_inspection_readings_reading_status",
        "inspection_readings",
        "reading_status IN ('ACCEPTED', 'REQUIRES_RESCAN', 'REJECTED')",
    )
    _create_comparison_checks(
        ("MATCH", "PALLET_MISMATCH", "EXPECTED_EMPTY", "UNEXPECTED_PALLET", "EXPECTED_PALLET_MISSING", "UNVERIFIED")
    )


def _create_comparison_checks(values: tuple[str, ...]) -> None:
    allowed_values = ", ".join(f"'{value}'" for value in values)
    op.create_check_constraint(
        op.f("ck_inspection_readings_comparison_result"),
        "inspection_readings",
        f"comparison_result IN ({allowed_values})",
    )
    op.create_check_constraint(
        op.f("ck_flowtwin_changes_flowtwin_previous_result"),
        "flowtwin_changes",
        f"previous_result IN ({allowed_values})",
    )
    op.create_check_constraint(
        op.f("ck_flowtwin_changes_flowtwin_current_result"),
        "flowtwin_changes",
        f"current_result IN ({allowed_values})",
    )
