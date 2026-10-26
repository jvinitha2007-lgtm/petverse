"""Add emergency requests, volunteer availability, and in-app alerts.

Revision ID: 0005_emergency_dispatch
Revises: 0004_provider_appointments
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_emergency_dispatch"
down_revision = "0004_provider_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "volunteer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_area", sa.String(160)),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_volunteer_profiles_available", "volunteer_profiles", ["is_available", "service_area"])
    op.create_table(
        "emergency_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id", ondelete="SET NULL")),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(400)),
        sa.Column("assigned_volunteer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('breathing_difficulty', 'suspected_poisoning', 'serious_injury', "
            "'severe_bleeding', 'seizure', 'heat_emergency', 'road_accident', 'missing_pet', "
            "'injured_stray', 'other')",
            name="ck_emergency_requests_category",
        ),
        sa.CheckConstraint("severity IN ('critical', 'urgent')", name="ck_emergency_requests_severity"),
        sa.CheckConstraint(
            "status IN ('submitted', 'assigned', 'responding', 'in_progress', 'completed', 'cancelled', 'escalated')",
            name="ck_emergency_requests_status",
        ),
    )
    op.create_index(
        "ix_emergency_requests_status_created", "emergency_requests", ["status", "created_at"]
    )
    op.create_index(
        "ix_emergency_requests_owner_created", "emergency_requests", ["owner_id", "created_at"]
    )
    op.create_index(
        "ix_emergency_requests_volunteer_created",
        "emergency_requests",
        ["assigned_volunteer_id", "created_at"],
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column(
            "emergency_request_id",
            sa.Integer(),
            sa.ForeignKey("emergency_requests.id", ondelete="CASCADE"),
        ),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
    )
    op.create_index(
        "ix_notifications_user_unread_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_emergency_requests_volunteer_created", table_name="emergency_requests")
    op.drop_index("ix_emergency_requests_owner_created", table_name="emergency_requests")
    op.drop_index("ix_emergency_requests_status_created", table_name="emergency_requests")
    op.drop_table("emergency_requests")
    op.drop_index("ix_volunteer_profiles_available", table_name="volunteer_profiles")
    op.drop_table("volunteer_profiles")
