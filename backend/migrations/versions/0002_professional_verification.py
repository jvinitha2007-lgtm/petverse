"""Add administrator controls and professional verification.

Revision ID: 0002_professional_verification
Revises: 0001_foundation
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_professional_verification"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "professional_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_role", sa.String(24), nullable=False),
        sa.Column("organization_name", sa.String(160), nullable=False),
        sa.Column("credential_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("review_notes", sa.Text()),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "requested_role IN ('veterinarian', 'groomer', 'shelter', 'volunteer')",
            name="ck_professional_applications_requested_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_professional_applications_status",
        ),
    )
    op.create_index(
        "uq_professional_applications_pending_user",
        "professional_applications",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_professional_applications_status_created",
        "professional_applications",
        ["status", "created_at"],
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("is_suspended", server_default=None)
    with op.batch_alter_table("professional_applications") as batch_op:
        batch_op.alter_column("status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_professional_applications_status_created", table_name="professional_applications")
    op.drop_index("uq_professional_applications_pending_user", table_name="professional_applications")
    op.drop_table("professional_applications")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_suspended")
