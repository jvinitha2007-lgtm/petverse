"""Add email verification, password recovery tokens, and dashboard metrics.

Revision ID: 0009_email_verification_role_dashboards
Revises: 0008_private_messaging
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_email_verification_role_dashboards"
down_revision = "0008_private_messaging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(sa.text("UPDATE users SET email_verified = TRUE"))
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_auth_tokens_purpose",
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_tokens_user_purpose",
        "auth_tokens",
        ["user_id", "purpose", "used_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_user_purpose", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_column("users", "email_verified")
