"""Limit volunteers to one active emergency assignment at a time.

Revision ID: 0006_one_active_emergency_per_volunteer
Revises: 0005_emergency_dispatch
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_one_active_emergency_per_volunteer"
down_revision = "0005_emergency_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "mysql":
        op.add_column(
            "emergency_requests",
            sa.Column(
                "active_volunteer_id",
                sa.Integer(),
                sa.Computed(
                    "CASE WHEN assigned_volunteer_id IS NOT NULL "
                    "AND status IN ('assigned', 'responding', 'in_progress') "
                    "THEN assigned_volunteer_id ELSE NULL END",
                    persisted=True,
                ),
            ),
        )
        op.create_index(
            "uq_emergency_active_volunteer_assignment", "emergency_requests", ["active_volunteer_id"], unique=True
        )
    else:
        op.create_index(
            "uq_emergency_active_volunteer_assignment",
            "emergency_requests",
            ["assigned_volunteer_id"],
            unique=True,
            sqlite_where=sa.text(
                "assigned_volunteer_id IS NOT NULL AND status IN ('assigned', 'responding', 'in_progress')"
            ),
            postgresql_where=sa.text(
                "assigned_volunteer_id IS NOT NULL AND status IN ('assigned', 'responding', 'in_progress')"
            ),
        )


def downgrade() -> None:
    op.drop_index("uq_emergency_active_volunteer_assignment", table_name="emergency_requests")
    if op.get_bind().dialect.name == "mysql":
        op.drop_column("emergency_requests", "active_volunteer_id")
