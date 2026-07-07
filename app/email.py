import logging

from .config import settings

log = logging.getLogger(__name__)


def _send(to_email: str, subject: str, text: str, html: str | None = None) -> bool:
    """Send one email via AWS SES. Returns True on a successful send.

    When SES is unconfigured (SES_SENDER unset, e.g. dev/test) this logs and
    returns False with no network call. Never raises: a failed send must not
    break the request that triggered it.
    """
    if not settings.ses_sender:
        log.info("email (SES off) to %s: %s", to_email, subject)
        return False
    body = {"Text": {"Data": text}}
    if html:
        body["Html"] = {"Data": html}
    try:
        import boto3

        boto3.client("ses", region_name=settings.ses_region).send_email(
            Source=settings.email_from,
            Destination={"ToAddresses": [to_email]},
            Message={"Subject": {"Data": subject}, "Body": body},
        )
        return True
    except Exception:
        log.exception("failed to send email to %s", to_email)
        return False


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send the email-verification link to a new user."""
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
    _send(to_email, "Verify your dothub email", text, html)


def send_signup_notification(username: str, email_addr: str) -> None:
    """Notify the site admin that a new user signed up. No-op if unconfigured."""
    if not settings.admin_notify_email:
        return
    text = (
        "A new user just signed up on dothub.\n\n"
        f"Username: {username}\n"
        f"Email:    {email_addr}\n"
    )
    _send(settings.admin_notify_email, f"New dothub signup: {username}", text)
