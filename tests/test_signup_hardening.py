"""Password-policy hardening enforced at the HTTP boundary (JSON API + web form).

The unit-level rules live in tests/test_validation.py; here we assert both
signup entry points reject a weak password (400) and accept the compliant one.
"""

WEAK = "pw123456"          # 8 chars, no uppercase -> now rejected
STRONG = "Testpass123"     # >=10 chars, upper + lower + digit -> accepted


def test_api_signup_rejects_weak_password(client):
    r = client.post("/api/signup", json={
        "username": "weakapi", "email": "weakapi@x.com", "password": WEAK})
    assert r.status_code == 400


def test_api_signup_accepts_compliant_password(client):
    r = client.post("/api/signup", json={
        "username": "strongapi", "email": "strongapi@x.com", "password": STRONG})
    assert r.status_code == 200
    assert r.json()["username"] == "strongapi"


def test_web_signup_rejects_weak_password(client):
    r = client.post(
        "/signup",
        data={"username": "weakweb", "email": "weakweb@x.com", "password": WEAK},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_web_signup_accepts_compliant_password(client):
    r = client.post(
        "/signup",
        data={"username": "strongweb", "email": "strongweb@x.com", "password": STRONG},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
