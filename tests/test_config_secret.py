import pytest

from app.config import Settings, assert_prod_secret

DEV_SECRET = "dev-secret-change-me"


def _settings(base_url, session_secret):
    s = Settings()
    s.base_url = base_url
    s.session_secret = session_secret
    return s


def test_https_with_dev_secret_raises():
    s = _settings("https://dothub.example.com", DEV_SECRET)
    with pytest.raises(RuntimeError):
        assert_prod_secret(s)


def test_http_with_dev_secret_ok():
    s = _settings("http://localhost:8000", DEV_SECRET)
    assert_prod_secret(s) is None


def test_https_with_real_secret_ok():
    s = _settings("https://dothub.example.com", "a-real-strong-secret")
    assert_prod_secret(s) is None


def test_http_with_real_secret_ok():
    s = _settings("http://localhost:8000", "a-real-strong-secret")
    assert_prod_secret(s) is None
