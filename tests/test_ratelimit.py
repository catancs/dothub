def test_login_rate_limited_after_threshold(client):
    from app.db import SessionLocal, Base, engine
    from app.models import User
    from app import security
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(User(username="u", email="u@x.com", password_hash=security.hash_password("pw12345")))
    db.commit(); db.close()

    # 10 allowed, 11th should be 429
    last = None
    for i in range(11):
        last = client.post("/login", data={"identifier": "u", "password": "wrongpw1"},
                           headers={"X-Forwarded-For": "1.2.3.4"})
    assert last.status_code == 429


def test_rate_limit_429_has_retry_after(client):
    from app.db import SessionLocal, Base, engine
    from app.models import User
    from app import security
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(User(username="u", email="u@x.com", password_hash=security.hash_password("pw12345")))
    db.commit(); db.close()

    # Hammer past the per-minute limit; the 429 must carry Retry-After (spec).
    last = None
    for i in range(11):
        last = client.post("/login", data={"identifier": "u", "password": "wrongpw1"},
                           headers={"X-Forwarded-For": "1.2.3.4"})
    assert last.status_code == 429
    assert last.headers.get("Retry-After") == "60"
