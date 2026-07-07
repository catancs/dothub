import re
from email.utils import parseaddr

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")


def validate_signup(username: str, email: str, password: str) -> None:
    """Validate signup inputs. Raises ValueError with a user-facing message."""
    if not USERNAME_RE.match(username or ""):
        raise ValueError("username must be 3 to 64 chars, letters, digits, _ or - only")
    _, parsed = parseaddr(email or "")
    if "@" not in parsed or "." not in parsed.split("@")[-1]:
        raise ValueError("email is not valid")
    pw = password or ""
    if len(pw) < 10:
        raise ValueError("password must be at least 10 characters")
    if not any(c.islower() for c in pw):
        raise ValueError("password must include a lowercase letter")
    if not any(c.isupper() for c in pw):
        raise ValueError("password must include an uppercase letter")
    if not any(c.isdigit() for c in pw):
        raise ValueError("password must include a number")
