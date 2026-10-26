import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
import ssl

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def send_email(recipient: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        raise EmailDeliveryError("SMTP is not configured")
    if (settings.smtp_username or settings.smtp_password) and not settings.smtp_starttls:
        raise EmailDeliveryError("Authenticated SMTP requires STARTTLS")

    message = EmailMessage()
    message["From"] = formataddr(("PetVerse", settings.smtp_from_email))
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("Unable to deliver account email")
        raise EmailDeliveryError("SMTP email delivery failed") from exc
