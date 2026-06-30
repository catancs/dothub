import app.models  # noqa: register tables


def _signup_and_publish(client):
    r = client.post("/api/signup", json={
        "username": "cata", "email": "cata@x.com", "password": "pw"})
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
