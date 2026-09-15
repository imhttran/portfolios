"""Email templates and the mailer.

Each template returns the queue row it should become, so an enqueue is just
``db.add``. Real SMTP when SMTP_HOST is set, otherwise the email is logged
instead of sent, so dev needs no mail server.
"""

from __future__ import annotations

import json
import smtplib
import ssl
import sys
from email.message import EmailMessage

from app.config import Settings
from app.models import EmailQueue


class MailError(Exception):
    """Raised when an SMTP send fails (the worker records it and retries)."""


def welcome_email(to: str) -> EmailQueue:
    return EmailQueue(
        to=to,
        subject="Your account has been created",
        body=(
            "Hi,\n\nYou've been successfully added to our system.\n\nThanks,\nThe Team"
        ),
    )


def verification_email(to: str, link: str) -> EmailQueue:
    return EmailQueue(
        to=to,
        subject="Verify your email address",
        body=(
            "Hi,\n\nPlease verify your email address by visiting this link:\n\n"
            f"{link}\n\nThanks,\nThe Team"
        ),
    )


def password_reset_email(to: str, link: str) -> EmailQueue:
    return EmailQueue(
        to=to,
        subject="Reset your password",
        body=(
            "Hi,\n\nA password reset was requested for this account. Click the "
            "link below to choose a new password (expires in 1 hour):\n\n"
            f"{link}\n\nIf you didn't request this, you can ignore this email.\n\n"
            "Thanks,\nThe Team"
        ),
    )


def login_code_email(to: str, code: str) -> EmailQueue:
    return EmailQueue(
        to=to,
        subject="Your login code",
        body=(
            "Hi,\n\nYour login verification code is:\n\n"
            f"{code}\n\nIt expires in 10 minutes.\n\nThanks,\nThe Team"
        ),
    )


def token_link(frontend_url: str, page: str, token: str) -> str:
    """Next.js client routes (no .html)."""
    return f"{frontend_url}/{page}?token={token}"


_logged_notice = False


def send_mail(settings: Settings, to: str, subject: str, text: str) -> None:
    """Send one email, or log it when no SMTP host is configured.

    Blocking; callers on the event loop should run it via ``asyncio.to_thread``.
    """
    global _logged_notice
    if not settings.smtp_host:
        if not _logged_notice:
            print(
                "[mailer] SMTP_HOST not set - emails are logged, not sent.",
                file=sys.stderr,
            )
            _logged_notice = True
        print(
            "[mailer] email: "
            + json.dumps(
                {
                    "from": settings.mail_from,
                    "to": to,
                    "subject": subject,
                    "text": text,
                }
            )
        )
        return

    # Reject header-injection attempts before building the message.
    if any(c in (to + subject + settings.mail_from) for c in "\r\n"):
        raise MailError("invalid header characters in email")

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)

    context = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            # Implicit TLS.
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, context=context, timeout=15
            ) as client:
                if settings.smtp_user:
                    client.login(settings.smtp_user, settings.smtp_pass)
                client.send_message(message)
        else:
            # Opportunistic STARTTLS.
            with smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=15
            ) as client:
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
                if settings.smtp_user:
                    client.login(settings.smtp_user, settings.smtp_pass)
                client.send_message(message)
    except (OSError, smtplib.SMTPException) as err:
        raise MailError(str(err)) from err
