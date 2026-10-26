import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import email
from app.models import CareTask, Pet, User

logger = logging.getLogger(__name__)


def send_due_care_reminders(db: Session, now: datetime | None = None) -> tuple[int, int]:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    rows = db.execute(
        select(CareTask, Pet, User)
        .join(Pet, CareTask.pet_id == Pet.id)
        .join(User, Pet.owner_id == User.id)
        .where(
            CareTask.completed.is_(False),
            CareTask.reminder_sent_at.is_(None),
            Pet.archived.is_(False),
            User.email_verified.is_(True),
            User.is_suspended.is_(False),
        )
        .order_by(CareTask.due_at)
        .limit(1000)
    ).all()

    sent = 0
    failed = 0
    for task, pet, owner in rows:
        due_at = task.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if due_at > current_time + timedelta(days=task.reminder_days_before):
            continue
        due_label = due_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        instructions = f"\n\nCare details: {task.instructions}" if task.instructions else ""
        body = (
            f"Hi {owner.full_name},\n\n"
            f"{task.title} for {pet.name} is due {due_label}.\n"
            f"Type: {task.category}{instructions}\n\n"
            "This is a reminder based on the schedule you entered in PetVerse. "
            "For medical questions, follow your veterinarian's advice."
        )
        try:
            email.send_email(owner.email, f"PetVerse care reminder: {task.title}", body)
        except email.EmailDeliveryError:
            db.rollback()
            failed += 1
            logger.exception("Failed care reminder delivery for task id=%s", task.id)
            continue

        task.reminder_sent_at = current_time
        db.commit()
        sent += 1
    return sent, failed
