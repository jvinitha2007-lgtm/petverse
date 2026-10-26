"""Track volunteer declines so they can leave a request queue.

Revision ID: 0007_emergency_volunteer_declines
Revises: 0006_one_active_emergency_per_volunteer
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_emergency_volunteer_declines"
down_revision = "0006_one_active_emergency_per_volunteer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emergency_declines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "emergency_request_id",
            sa.Integer(),
            sa.ForeignKey("emergency_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "volunteer_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "emergency_request_id",
            "volunteer_user_id",
            name="uq_emergency_decline_volunteer",
        ),
    )
    op.create_index(
        "ix_emergency_declines_volunteer_created",
        "emergency_declines",
        ["volunteer_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_emergency_declines_volunteer_created", table_name="emergency_declines")
    op.drop_table("emergency_declines")
