def test_signup_login_key_publish_flow(client, s3):
    # signup logs the user in (session cookie kept by TestClient)
    r = client.post("/api/signup", json={"username": "cata", "email": "c@x.com", "password": "pw"})
    assert r.status_code == 200

    r = client.post("/api/keys", json={"label": "cli"})
    assert r.status_code == 200
    key = r.json()["api_key"]
    assert key.startswith("dh_")

    # publish via API key (Bearer)
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"title": "My Flow", "description": "d",
                          "files": {"CLAUDE.md": "x"}})
    assert r.status_code == 200
    assert r.json()["slug"] == "my-flow"

    r = client.get("/api/setups")
    assert any(s["slug"] == "my-flow" for s in r.json())


def test_publish_requires_auth(client, s3):
    r = client.post("/api/setups", json={"title": "X", "description": "", "files": {"a.md": "1"}})
    assert r.status_code == 401


def test_duplicate_signup_rejected(client, s3):
    client.post("/api/signup", json={"username": "a", "email": "a@x.com", "password": "p"})
    r = client.post("/api/signup", json={"username": "a", "email": "a@x.com", "password": "p"})
    assert r.status_code == 400


def test_login_flow(client, s3):
    client.post("/api/signup", json={"username": "lo", "email": "lo@x.com", "password": "secret"})
    # fresh client-like login round trip: wrong password rejected, right password OK
    r = client.post("/api/login", json={"email": "lo@x.com", "password": "wrong"})
    assert r.status_code == 401
    r = client.post("/api/login", json={"email": "lo@x.com", "password": "secret"})
    assert r.status_code == 200
    assert r.json()["username"] == "lo"


def test_unknown_setup_returns_404(client, s3):
    r = client.get("/api/setups/does-not-exist")
    assert r.status_code == 404
    r = client.get("/api/setups/does-not-exist/download")
    assert r.status_code == 404


def test_list_ordering_and_runs_code(client, s3):
    client.post("/api/signup", json={"username": "ord", "email": "ord@x.com", "password": "pw"})
    headers = None  # use session cookie held by TestClient

    # plain setup, no code effects
    r = client.post("/api/setups", json={
        "title": "Plain Flow", "description": "p",
        "files": {"CLAUDE.md": "just rules"},
    })
    assert r.status_code == 200
    assert r.json()["slug"] == "plain-flow"

    # setup with a hook command -> runs_code should be true
    hooks_json = '{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}'
    r = client.post("/api/setups", json={
        "title": "Hooky Flow", "description": "h",
        "files": {"CLAUDE.md": "rules", "hooks/hooks.json": hooks_json},
    })
    assert r.status_code == 200
    assert r.json()["slug"] == "hooky-flow"

    # bump downloads on the plain setup so it sorts first (downloads desc)
    r = client.get("/api/setups/plain-flow/download")
    assert r.status_code == 200
    assert "url" in r.json()

    listing = client.get("/api/setups").json()
    slugs = [s["slug"] for s in listing]
    assert slugs[0] == "plain-flow"  # more downloads sorts first

    by_slug = {s["slug"]: s for s in listing}
    assert by_slug["hooky-flow"]["runs_code"] is True
    assert by_slug["plain-flow"]["runs_code"] is False
