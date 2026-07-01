import pytest
from app.validation import validate_signup


def test_accepts_valid_username():
    validate_signup("catancs_01", "a@b.com", "password1")  # no raise


@pytest.mark.parametrize("bad", ["ab", "x" * 65, "has space", "has/slash", "two..dots", "dash-ok"])
def test_rejects_bad_usernames(bad):
    if bad == "dash-ok":
        validate_signup(bad, "a@b.com", "password1")  # dashes allowed
        return
    with pytest.raises(ValueError):
        validate_signup(bad, "a@b.com", "password1")


def test_rejects_bad_email():
    with pytest.raises(ValueError):
        validate_signup("goodname", "not-an-email", "password1")


def test_rejects_short_password():
    with pytest.raises(ValueError):
        validate_signup("goodname", "a@b.com", "short")
