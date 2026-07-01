import app.models  # noqa: register tables


def _signup_and_publish(client):
    r = client.post("/api/signup", json={
        "username": "cata", "email": "cata@x.com", "password": "pw123456"})
    assert r.status_code == 200
    r = client.post("/api/setups", json={
        "title": "TDD Discipline",
        "description": "Red green refactor enforced by hooks.",
        "slug": "tdd-discipline",
        "files": {"CLAUDE.md": "always test first"}})
    assert r.status_code == 200


def test_discover_lists_published_setup(client, s3):
    _signup_and_publish(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "TDD Discipline" in r.text
    assert "cata" in r.text


def test_following_requires_login_redirects(client, s3):
    # fresh client with no session cookie
    r = client.get("/?tab=following", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_discover_has_window_toggle_links(client, s3):
    _signup_and_publish(client)
    html = client.get("/").text
    assert "/?tab=discover&window=24h" in html
    assert "/?tab=discover&window=7d" in html
    assert "/?tab=discover&window=all" in html


def test_feed_search_box_filters_by_title(client, s3):
    # seed via API
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "Rails Startup", "d", {"skills/a/SKILL.md": "# a"}, slug="rails")
    setups.publish(db, u, "Writing Craft", "d", {"skills/b/SKILL.md": "# b"}, slug="writing")
    db.commit(); db.close()

    r = client.get("/?q=Rails")
    assert r.status_code == 200
    assert "rails" in r.text
    assert "writing" not in r.text


def test_feed_no_code_tab(client, s3):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "Pure", "d", {"skills/a/SKILL.md": "# a"}, slug="pure")
    setups.publish(db, u, "Hooked", "d",
                   {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'}, slug="hooked")
    db.commit(); db.close()

    r = client.get("/?tab=no-code")
    assert r.status_code == 200
    assert "pure" in r.text
    assert "hooked" not in r.text


def test_feed_tag_filter(client, s3):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "Pure", "d", {"skills/a/SKILL.md": "# a"}, slug="pure")
    setups.publish(db, u, "Hooked", "d",
                   {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'}, slug="hooked")
    db.commit(); db.close()

    r = client.get("/?tag=hooks")
    assert r.status_code == 200
    assert "hooked" in r.text
    assert "pure" not in r.text
