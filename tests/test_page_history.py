"""History timeline page (/history).

Uses the TestClient `client` fixture (keeps the session cookie set by
/api/signup) plus the moto `s3` fixture for archive storage.
"""


def _signup(client, username, password="pw"):
    r = client.post("/api/signup",
                    json={"username": username, "email": f"{username}@x.io", "password": password})
    assert r.status_code == 200, r.text


def _publish(client, title, files=None):
    files = files or {"CLAUDE.md": "x"}
    r = client.post("/api/setups", json={"title": title, "description": "d", "files": files})
    assert r.status_code == 200, r.text
    return r.json()["slug"]


def test_history_shows_push_and_pull(client, s3):
    _signup(client, "alice")
    pushed_slug = _publish(client, "Pushed Only Flow")      # push-only setup
    pulled_slug = _publish(client, "Pulled Flow")           # this one we will also pull

    # download requires auth; the session cookie from signup covers it -> records a pull
    r = client.get(f"/api/setups/{pulled_slug}/download")
    assert r.status_code == 200, r.text

    r = client.get("/history")
    assert r.status_code == 200, r.text
    body = r.text
    # both kind chips render in the timeline (not just the static filter pills)
    assert 'class="kind push"' in body
    assert 'class="kind pull"' in body
    # both slugs appear in the timeline
    assert pushed_slug in body
    assert pulled_slug in body


def test_history_filter_pulled_excludes_push_only(client, s3):
    _signup(client, "bob")
    pushed_slug = _publish(client, "Bob Pushed Only")       # push-only, never pulled
    pulled_slug = _publish(client, "Bob Pulled Flow")

    r = client.get(f"/api/setups/{pulled_slug}/download")
    assert r.status_code == 200, r.text

    r = client.get("/history?filter=pulled")
    assert r.status_code == 200, r.text
    body = r.text
    # only the pulled entry remains; the push-only slug is gone
    assert pulled_slug in body
    assert pushed_slug not in body
    # a Pulled chip is rendered, but no Pushed chip (the static filter pill
    # label "Pushed" is always present, so check the timeline chip class)
    assert 'class="kind pull"' in body
    assert 'class="kind push"' not in body


def test_history_requires_login_redirects(client, s3):
    r = client.get("/history", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
