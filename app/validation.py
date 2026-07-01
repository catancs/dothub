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
    if len(password or "") < 8:
        raise ValueError("password must be at least 8 characters")
