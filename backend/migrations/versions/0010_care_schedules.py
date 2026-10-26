"""Add recurring care schedules and email reminder tracking.

Revision ID: 0010_care_schedules
Revises: 0009_email_verification_role_dashboards
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_care_schedules"
down_revision = "0009_email_verification_role_dashboards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("care_tasks") as batch_op:
        batch_op.add_column(sa.Column("instructions", sa.String(length=500)))
        batch_op.add_column(sa.Column("repeat_interval_minutes", sa.Integer()))
        batch_op.add_column(
            sa.Column("reminder_days_before", sa.Integer(), server_default="1", nullable=False),
        )
        batch_op.add_column(sa.Column("reminder_sent_at", sa.DateTime(timezone=True)))
        batch_op.create_check_constraint(
            "ck_care_tasks_repeat_interval",
            "repeat_interval_minutes IS NULL OR repeat_interval_minutes BETWEEN 1 AND 525600",
        )
        batch_op.create_check_constraint(
            "ck_care_tasks_reminder_days",
            "reminder_days_before BETWEEN 0 AND 30",
        )
    op.create_index(
        "ix_care_tasks_reminders",
        "care_tasks",
        ["completed", "reminder_sent_at", "due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_care_tasks_reminders", table_name="care_tasks")
    with op.batch_alter_table("care_tasks") as batch_op:
        batch_op.drop_constraint("ck_care_tasks_reminder_days", type_="check")
        batch_op.drop_constraint("ck_care_tasks_repeat_interval", type_="check")
        batch_op.drop_column("reminder_sent_at")
        batch_op.drop_column("reminder_days_before")
        batch_op.drop_column("repeat_interval_minutes")
        batch_op.drop_column("instructions")
