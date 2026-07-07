import logging

from .config import settings

log = logging.getLogger(__name__)


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send the email-verification link.

    Pluggable by config: when SES_SENDER is set we deliver via AWS SES; when it
    is falsy (dev/test) we just log the link and return with no network call.

    This function NEVER raises. A failed send must not fail a signup, so SES
    errors are caught and logged.
    """
    if not settings.ses_sender:
        log.info("email verification (dev, SES off) for %s: %s", to_email, verify_url)
        return
    subject = "Verify your dothub email"
    text = (
        "Welcome to dothub!\n\n"
        f"Confirm your email address by opening this link:\n{verify_url}\n\n"
        "If you did not create this account you can ignore this message."
    )
    html = (
        "<p>Welcome to dothub!</p>"
        f'<p>Confirm your email address: <a href="{verify_url}">{verify_url}</a></p>'
        "<p>If you did not create this account you can ignore this message.</p>"
    )
    try:
        import boto3

        client = boto3.client("ses", region_name=settings.ses_region)
        client.send_email(
            Source=settings.email_from,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": text}, "Html": {"Data": html}},
            },
        )
    except Exception:
        log.exception("failed to send verification email to %s", to_email)
