import app.models  # noqa: F401 - register tables before the db fixture's create_all


def test_api_signup_notifies_admin(client, s3, monkeypatch):
    from app import email
    captured = []
    monkeypatch.setattr(email, "send_signup_notification", lambda u, e: captured.append((u, e)))
    r = client.post("/api/signup",
                    json={"username": "newbie", "email": "newbie@x.com", "password": "Testpass123"})
    assert r.status_code == 200
    assert captured == [("newbie", "newbie@x.com")]


def test_web_signup_notifies_admin(client, s3, monkeypatch):
    from app.web import auth
    captured = []
    monkeypatch.setattr(auth.mailer, "send_signup_notification", lambda u, e: captured.append((u, e)))
    r = client.post("/signup",
                    data={"username": "webbie", "email": "webbie@x.com", "password": "Testpass123"})
    assert r.status_code in (200, 303)
    assert captured == [("webbie", "webbie@x.com")]


def test_send_signup_notification_noop_without_admin(monkeypatch):
    from app import email
    from app.config import settings
    monkeypatch.setattr(settings, "admin_notify_email", None)
    # Should return without attempting any send (no exception, no SES call).
    assert email.send_signup_notification("x", "x@y.com") is None
