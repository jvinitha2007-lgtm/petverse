"""Add appointment- and assigned-emergency-scoped conversations.

Revision ID: 0008_private_messaging
Revises: 0007_emergency_volunteer_declines
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_private_messaging"
down_revision = "0007_emergency_volunteer_declines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="CASCADE")),
        sa.Column(
            "emergency_request_id",
            sa.Integer(),
            sa.ForeignKey("emergency_requests.id", ondelete="CASCADE"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(appointment_id IS NOT NULL AND emergency_request_id IS NULL) OR "
            "(appointment_id IS NULL AND emergency_request_id IS NOT NULL)",
            name="ck_conversations_one_context",
        ),
        sa.UniqueConstraint("appointment_id", name="uq_conversations_appointment"),
        sa.UniqueConstraint("emergency_request_id", name="uq_conversations_emergency"),
    )
    op.create_index("ix_conversations_updated", "conversations", ["updated_at"])
    op.create_table(
        "conversation_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_participant"),
    )
    op.create_index(
        "ix_conversation_participants_user", "conversation_participants", ["user_id", "conversation_id"]
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversation_participants_user", table_name="conversation_participants")
    op.drop_table("conversation_participants")
    op.drop_index("ix_conversations_updated", table_name="conversations")
    op.drop_table("conversations")
