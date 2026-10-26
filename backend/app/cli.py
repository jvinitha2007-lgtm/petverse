import argparse
import sys

from sqlalchemy import select

from app.core.care_reminders import send_due_care_reminders
from app.db import SessionLocal
from app.models import AuditLog, User


def promote_admin(email: str) -> int:
    normalized_email = email.strip().lower()
    if not normalized_email:
        print("An account email is required.", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == normalized_email))
        if user is None:
            print("No account exists with that email. Register an owner account first.", file=sys.stderr)
            return 1
        if user.is_suspended:
            print("Cannot grant administrator access to a suspended account.", file=sys.stderr)
            return 1
        if user.role == "admin":
            print("That account is already an administrator.")
            return 0
        previous_role = user.role
        user.role = "admin"
        db.add(AuditLog(
            actor_id=user.id,
            target_user_id=user.id,
            action="administrator_provisioned_by_cli",
            details=f"previous_role={previous_role}",
        ))
        db.commit()
        print(f"Administrator access granted to {normalized_email}.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PetVerse operator-only account management")
    commands = parser.add_subparsers(dest="command", required=True)
    promote = commands.add_parser("promote-admin", help="Grant admin access to an existing account")
    promote.add_argument("email")
    commands.add_parser("send-care-reminders", help="Send scheduled vaccination and medication reminders")
    args = parser.parse_args()
    if args.command == "promote-admin":
        return promote_admin(args.email)
    if args.command == "send-care-reminders":
        with SessionLocal() as db:
            sent, failed = send_due_care_reminders(db)
        print(f"Care reminders sent: {sent}; failed: {failed}.")
        return 1 if failed else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
