import pytest
from app.validation import validate_signup

VALID_PW = "Testpass123"


def test_accepts_valid_username():
    validate_signup("catancs_01", "a@b.com", VALID_PW)  # no raise


@pytest.mark.parametrize("bad", ["ab", "x" * 65, "has space", "has/slash", "two..dots", "dash-ok"])
def test_rejects_bad_usernames(bad):
    if bad == "dash-ok":
        validate_signup(bad, "a@b.com", VALID_PW)  # dashes allowed
        return
    with pytest.raises(ValueError):
        validate_signup(bad, "a@b.com", VALID_PW)


def test_rejects_bad_email():
    with pytest.raises(ValueError):
        validate_signup("goodname", "not-an-email", VALID_PW)


def test_accepts_valid_password():
    validate_signup("goodname", "a@b.com", VALID_PW)  # no raise


def test_rejects_short_password():
    # 9 chars: has upper/lower/digit but under the 10-char minimum
    with pytest.raises(ValueError):
        validate_signup("goodname", "a@b.com", "Testpas12")


def test_rejects_password_without_uppercase():
    with pytest.raises(ValueError):
        validate_signup("goodname", "a@b.com", "testpass123")


def test_rejects_password_without_lowercase():
    with pytest.raises(ValueError):
        validate_signup("goodname", "a@b.com", "TESTPASS123")


def test_rejects_password_without_digit():
    with pytest.raises(ValueError):
        validate_signup("goodname", "a@b.com", "TestpassAbc")
