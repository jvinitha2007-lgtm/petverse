"""Create PetVerse owner foundation tables.

Revision ID: 0001_foundation
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_table(
        "pets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("species", sa.String(40), nullable=False),
        sa.Column("breed", sa.String(80)),
        sa.Column("birth_date", sa.Date()),
        sa.Column("sex", sa.String(20)),
        sa.Column("weight_kg", sa.Float()),
        sa.Column("allergies", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pets_owner_archived", "pets", ["owner_id", "archived"])
    op.create_table(
        "medical_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("professional_record", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_medical_records_pet_recorded", "medical_records", ["pet_id", "recorded_at"])
    op.create_table(
        "care_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pet_id", sa.Integer(), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_care_tasks_pet_due", "care_tasks", ["pet_id", "due_at"])


def downgrade() -> None:
    op.drop_index("ix_care_tasks_pet_due", table_name="care_tasks")
    op.drop_table("care_tasks")
    op.drop_index("ix_medical_records_pet_recorded", table_name="medical_records")
    op.drop_table("medical_records")
    op.drop_index("ix_pets_owner_archived", table_name="pets")
    op.drop_table("pets")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
