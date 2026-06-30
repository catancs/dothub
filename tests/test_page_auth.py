"""Web auth pages: login, signup, logout.

The /account page is built by a separate page task and is only a stub in this
worktree, so authentication state is asserted via routes owned here (the auth
session cookie) and via the foundation's current_user-protected API route
(POST /api/keys), which returns 200 when authenticated and 401 when not.
"""


def _authed(client) -> bool:
    """True if the client's session authenticates against a protected route."""
    return client.post("/api/keys", json={"label": "probe"}).status_code == 200


def test_get_login_and_signup_render(client):
    assert client.get("/login").status_code == 200
    assert client.get("/signup").status_code == 200


def test_signup_logs_in_and_redirects(client):
    r = client.post(
        "/signup",
        data={"username": "alice", "email": "alice@example.com", "password": "pw12345"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    # Session cookie is set by the route we own, and it authenticates.
    assert client.cookies.get("session")
    assert _authed(client)


def test_logout_clears_session(client):
    client.post(
        "/signup",
        data={"username": "bob", "email": "bob@example.com", "password": "pw12345"},
        follow_redirects=False,
    )
    assert _authed(client)

    r = client.post("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    # Session cookie is cleared and the client is no longer authenticated.
    assert client.cookies.get("session") is None
    assert not _authed(client)


def test_login_with_correct_credentials(client):
    client.post(
        "/signup",
        data={"username": "carol", "email": "carol@example.com", "password": "pw12345"},
        follow_redirects=False,
    )
    client.post("/logout", follow_redirects=False)
    assert not _authed(client)

    r = client.post(
        "/login",
        data={"email": "carol@example.com", "password": "pw12345"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert _authed(client)


def test_login_with_wrong_password_returns_401(client):
    client.post(
        "/signup",
        data={"username": "dave", "email": "dave@example.com", "password": "pw12345"},
        follow_redirects=False,
    )
    client.post("/logout", follow_redirects=False)

    r = client.post(
        "/login",
        data={"email": "dave@example.com", "password": "WRONG"},
        follow_redirects=False,
    )
    assert r.status_code == 401
    assert "Wrong email or password" in r.text
    assert not _authed(client)
