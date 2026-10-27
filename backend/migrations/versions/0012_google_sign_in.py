"""Add Google account identity to users.

Revision ID: 0012_google_sign_in
Revises: 0011_adoption_missing_pet
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_google_sign_in"
down_revision = "0011_adoption_missing_pet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_subject", sa.String(length=255), nullable=True))
    op.create_index("uq_users_google_subject", "users", ["google_subject"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_google_subject", table_name="users")
    op.drop_column("users", "google_subject")
