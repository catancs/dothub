"""Web pages: /account (edit form, keys, setups) and /u/{username} public profile.

Mirrors tests/test_api_v2.py's TestClient + signup/publish approach. The TestClient
keeps the session cookie set by /api/signup, so authed page loads work without headers.
"""


def _signup(client, username, email="", password="pw"):
    email = email or f"{username}@x.com"
    r = client.post(
        "/api/signup", json={"username": username, "email": email, "password": password}
    )
    assert r.status_code == 200
    return r


def _publish(client, title, files=None):
    files = files or {"CLAUDE.md": "x"}
    r = client.post(
        "/api/setups", json={"title": title, "description": "d", "files": files}
    )
    assert r.status_code == 200
    return r.json()


def test_logged_out_account_redirects_to_login(client):
    r = client.get("/account", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_account_shows_username_and_setups(client, s3):
    _signup(client, "alice")
    _publish(client, "Deploy Flow")

    r = client.get("/account")
    assert r.status_code == 200
    assert "alice" in r.text
    assert "Deploy Flow" in r.text


def test_account_post_updates_profile(client, s3):
    _signup(client, "bob")

    r = client.post(
        "/account",
        data={
            "display_name": "Bob Builder",
            "bio": "I build setups",
            "link_github": "https://github.com/bob",
            "link_linkedin": "",
            "link_x": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/account"

    page = client.get("/account")
    assert page.status_code == 200
    assert "Bob Builder" in page.text
    assert "https://github.com/bob" in page.text


def test_public_profile_shows_setups_and_followers(client, s3):
    _signup(client, "carol")
    _publish(client, "Carol Flow")

    r = client.get("/u/carol")
    assert r.status_code == 200
    assert "Carol Flow" in r.text
    assert "followers" in r.text


def test_public_profile_missing_user_is_404(client):
    r = client.get("/u/nobody")
    assert r.status_code == 404
