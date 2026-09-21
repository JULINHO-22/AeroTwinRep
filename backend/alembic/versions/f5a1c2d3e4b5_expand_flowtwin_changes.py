"""expand FlowTwin change classifications

Revision ID: f5a1c2d3e4b5
Revises: e91d43a7b5c2
"""
from alembic import op
import sqlalchemy as sa

revision = "f5a1c2d3e4b5"
down_revision = "e91d43a7b5c2"
branch_labels = None
depends_on = None

def upgrade():
    op.drop_constraint("flowtwin_change_type", "flowtwin_changes", type_="check")
    op.create_check_constraint("flowtwin_change_type", "flowtwin_changes", "change_type IN ('PALLET_ADDED','PALLET_REMOVED','PALLET_CHANGED','RESULT_CHANGED','BECAME_UNRESOLVED','RESOLVED_SINCE_PREVIOUS','EXPECTED_CHANGED','PERSISTENT_DISCREPANCY','AUTHORIZED_MOVEMENT')")
    op.create_unique_constraint("uq_flowtwin_change_logical", "flowtwin_changes", ["current_inspection_id", "previous_inspection_id", "location_id", "change_type"])

def downgrade():
    # The predecessor schema cannot represent the expanded FlowTwin types.
    # A downgrade is necessarily lossy for those derived, reproducible rows;
    # remove them before reintroducing the legacy constraint.  This also keeps
    # a full test reset (`downgrade base`) safe after demo data was seeded.
    op.execute(
        "DELETE FROM flowtwin_changes WHERE change_type NOT IN "
        "('PALLET_ADDED','PALLET_REMOVED','PALLET_CHANGED','RESULT_CHANGED')"
    )
    op.execute("ALTER TABLE flowtwin_changes DROP CONSTRAINT IF EXISTS uq_flowtwin_change_logical")
    op.drop_constraint("flowtwin_change_type", "flowtwin_changes", type_="check")
    op.create_check_constraint("flowtwin_change_type", "flowtwin_changes", "change_type IN ('PALLET_ADDED','PALLET_REMOVED','PALLET_CHANGED','RESULT_CHANGED')")
