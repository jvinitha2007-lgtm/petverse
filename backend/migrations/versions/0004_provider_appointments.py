"""Add verified provider profiles, availability, and bookings.

Revision ID: 0004_provider_appointments
Revises: 0003_remove_redundant_email_index
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_provider_appointments"
down_revision = "0003_remove_redundant_email_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("service_area", sa.String(160)),
        sa.Column("service_fee", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('veterinarian', 'groomer')", name="ck_provider_profiles_kind"),
        sa.CheckConstraint("service_fee >= 0", name="ck_provider_profiles_service_fee"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "provider_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "provider_id", sa.Integer(), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("starts_at < ends_at", name="ck_provider_availability_start_before_end"),
        sa.UniqueConstraint("provider_id", "starts_at", name="uq_provider_availability_start"),
    )
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "provider_id", sa.Integer(), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "availability_id",
            sa.Integer(),
            sa.ForeignKey("provider_availability.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("service_kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("owner_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'completed', 'cancelled')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint(
            "service_kind IN ('veterinarian', 'groomer')",
            name="ck_appointments_service_kind",
        ),
    )
    op.create_index(
        "uq_appointments_active_slot",
        "appointments",
        ["availability_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'confirmed')"),
        postgresql_where=sa.text("status IN ('pending', 'confirmed')"),
    )
    op.create_index("ix_appointments_owner_created", "appointments", ["owner_id", "created_at"])
    op.create_index("ix_appointments_provider_created", "appointments", ["provider_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_appointments_provider_created", table_name="appointments")
    op.drop_index("ix_appointments_owner_created", table_name="appointments")
    op.drop_index("uq_appointments_active_slot", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("provider_availability")
    op.drop_table("provider_profiles")
