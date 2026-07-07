"""Email-verification flow and the gated publish enforcement.

The dev/test send path never hits the network (SES_SENDER unset), so we
monkeypatch app.email.send_verification_email to capture the verify_url instead.
Both signup entry points reference the send function via the module object, so
patching the module attribute intercepts either path.
"""

from sqlalchemy import select

from app import email as email_module
from app.config import settings
from app.models import User

PW = "Testpass123"


def _capture(monkeypatch):
    """Patch the sender; return a dict populated on each send."""
    box = {}

    def fake_send(to_email, verify_url):
        box["to"] = to_email
        box["url"] = verify_url

    monkeypatch.setattr(email_module, "send_verification_email", fake_send)
    return box


def _signup(client, username, email):
    r = client.post("/api/signup", json={
        "username": username, "email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r


def _token_from(box):
    return box["url"].rsplit("/", 1)[1]


def test_signup_creates_unverified_user_with_token(client, db, monkeypatch):
    box = _capture(monkeypatch)
    _signup(client, "freshie", "freshie@x.com")

    db.expire_all()
    u = db.scalar(select(User).where(User.username == "freshie"))
    assert u.email_verified is False
    assert u.verification_token_hash is not None
    assert u.verification_sent_at is not None
    # the captured link points at our verify route for this user
    assert box["to"] == "freshie@x.com"
    assert "/verify/" in box["url"]


def test_verify_link_flips_verified_and_clears_token(client, db, monkeypatch):
    box = _capture(monkeypatch)
    _signup(client, "linkuser", "linkuser@x.com")

    r = client.get(f"/verify/{_token_from(box)}")
    assert r.status_code == 200

    db.expire_all()
    u = db.scalar(select(User).where(User.username == "linkuser"))
    assert u.email_verified is True
    assert u.verification_token_hash is None
    assert u.verification_sent_at is None


def test_verify_unknown_token_is_404(client):
    r = client.get("/verify/definitely-not-a-real-token")
    assert r.status_code == 404


def test_resend_regenerates_token(client, db, monkeypatch):
    box = _capture(monkeypatch)
    _signup(client, "resender", "resender@x.com")
    first_url = box["url"]

    r = client.post("/api/resend-verification")
    assert r.status_code == 200
    assert box["url"] != first_url  # a fresh token was issued


def test_publish_blocked_for_unverified_when_required(client, s3, monkeypatch):
    _capture(monkeypatch)
    monkeypatch.setattr(settings, "require_email_verification", True)
    _signup(client, "gated", "gated@x.com")

    r = client.post("/api/setups", json={
        "title": "Gated Flow", "description": "d", "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 403


def test_publish_allowed_for_verified_when_required(client, s3, monkeypatch):
    box = _capture(monkeypatch)
    monkeypatch.setattr(settings, "require_email_verification", True)
    _signup(client, "goodcitizen", "goodcitizen@x.com")

    assert client.get(f"/verify/{_token_from(box)}").status_code == 200

    r = client.post("/api/setups", json={
        "title": "Verified Flow", "description": "d", "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200


def test_publish_allowed_when_flag_off_by_default(client, s3, monkeypatch):
    # require_email_verification defaults False; leave it untouched.
    _capture(monkeypatch)
    _signup(client, "defaultuser", "defaultuser@x.com")

    r = client.post("/api/setups", json={
        "title": "Default Flow", "description": "d", "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200
