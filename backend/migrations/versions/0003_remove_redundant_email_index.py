"""Remove the redundant non-unique email index.

Revision ID: 0003_remove_redundant_email_index
Revises: 0002_professional_verification
"""
from alembic import op

revision = "0003_remove_redundant_email_index"
down_revision = "0002_professional_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")


def downgrade() -> None:
    op.create_index("ix_users_email", "users", ["email"], unique=False)
