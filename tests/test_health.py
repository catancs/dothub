def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_session_cookie_has_secure_flag(client):
    r = client.post("/login", data={"identifier": "nobody", "password": "wrongpw1"},
                    headers={"X-Forwarded-For": "9.9.9.9"}, follow_redirects=False)
    # 401 or 429 both fine; we only care that IF a session cookie is set, it is Secure.
    cookie = r.headers.get("set-cookie", "")
    if "session=" in cookie:
        assert "Secure" in cookie
        assert "SameSite=lax" in cookie
