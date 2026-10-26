"""Add shelter adoption listings, missing pet reports, and sightings.

Revision ID: 0011_adoption_missing_pet
Revises: 0010_care_schedules
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_adoption_missing_pet"
down_revision = "0010_care_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "adoption_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shelter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pet_name", sa.String(length=80), nullable=False),
        sa.Column("species", sa.String(length=40), nullable=False),
        sa.Column("breed", sa.String(length=80)),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service_area", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="available", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('available', 'pending', 'adopted', 'withdrawn')",
            name="ck_adoption_listings_status",
        ),
    )
    op.create_index("ix_adoption_listings_status_created", "adoption_listings", ["status", "created_at"])
    op.create_table(
        "missing_pet_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id", ondelete="SET NULL")),
        sa.Column("pet_name", sa.String(length=80), nullable=False),
        sa.Column("species", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service_area", sa.String(length=160), nullable=False),
        sa.Column("contact_instructions", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="missing", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('missing', 'found', 'closed')", name="ck_missing_pet_reports_status"),
    )
    op.create_index("ix_missing_pet_reports_status_created", "missing_pet_reports", ["status", "created_at"])
    op.create_index("ix_missing_pet_reports_owner_created", "missing_pet_reports", ["owner_id", "created_at"])
    op.create_table(
        "pet_sightings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("missing_pet_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("service_area", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pet_sightings_report_created", "pet_sightings", ["report_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_pet_sightings_report_created", table_name="pet_sightings")
    op.drop_table("pet_sightings")
    op.drop_index("ix_missing_pet_reports_owner_created", table_name="missing_pet_reports")
    op.drop_index("ix_missing_pet_reports_status_created", table_name="missing_pet_reports")
    op.drop_table("missing_pet_reports")
    op.drop_index("ix_adoption_listings_status_created", table_name="adoption_listings")
    op.drop_table("adoption_listings")
