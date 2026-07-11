"""Send a real test email via Brevo to verify BREVO_API_KEY / EMAILS_FROM_EMAIL are set up correctly.

Usage:
    python scripts/test_brevo_email.py you@example.com
"""

import logging
import sys

from app.core.config import settings
from app.services.email_service import generate_test_email, send_email

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_brevo_email.py <recipient-email>")
        sys.exit(1)

    email_to = sys.argv[1]

    if not settings.emails_enabled:
        print(
            "Emails are not enabled. Set BREVO_API_KEY and EMAILS_FROM_EMAIL in your .env file."
        )
        sys.exit(1)

    print(f"Sending from: {settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>")
    print(f"Sending to:   {email_to}")

    email_data = generate_test_email(email_to=email_to)
    try:
        send_email(
            email_to=email_to,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    except Exception as exc:
        print(f"Failed to send email: {exc}")
        sys.exit(1)

    print("Email sent successfully. Check the recipient's inbox.")


if __name__ == "__main__":
    main()
