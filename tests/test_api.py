def test_signup_login_key_publish_flow(client, s3):
    # signup logs the user in (session cookie kept by TestClient)
    r = client.post("/api/signup", json={"username": "cata", "email": "c@x.com", "password": "pw123456"})
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
    items = r.json()
    assert any(s["slug"] == "my-flow" for s in items)
    # author (owner's username) is exposed on each listing item
    item = next(s for s in items if s["slug"] == "my-flow")
    assert item["author"] == "cata"


def test_publish_requires_auth(client, s3):
    r = client.post("/api/setups", json={"title": "X", "description": "", "files": {"a.md": "1"}})
    assert r.status_code == 401


def test_publish_bad_bundle_returns_400(client, s3):
    # signup mints a session; mint a Bearer key mirroring the publish-flow test
    r = client.post("/api/signup", json={"username": "bad", "email": "bad@x.com", "password": "pw123456"})
    assert r.status_code == 200
    key = client.post("/api/keys", json={"label": "cli"}).json()["api_key"]

    # path-traversal in files -> bundle.BundleError -> HTTP 400 (not 500)
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"title": "Bad Bundle", "description": "d",
                          "files": {"../evil.md": "x"}})
    assert r.status_code == 400


def test_publish_to_others_slug_returns_403(client, s3):
    # user A publishes slug "x"
    ra = client.post("/api/signup", json={"username": "alice", "email": "alice@x.com", "password": "pw123456"})
    assert ra.status_code == 200
    key_a = client.post("/api/keys", json={"label": "cli"}).json()["api_key"]
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key_a}"},
                    json={"title": "x", "description": "d", "files": {"CLAUDE.md": "a"}})
    assert r.status_code == 200
    assert r.json()["slug"] == "x"

    # user B (different account + own key) tries to publish the same slug -> 403
    rb = client.post("/api/signup", json={"username": "bob", "email": "bob@x.com", "password": "pw123456"})
    assert rb.status_code == 200
    key_b = client.post("/api/keys", json={"label": "cli"}).json()["api_key"]
    r = client.post("/api/setups",
                    headers={"Authorization": f"Bearer {key_b}"},
                    json={"title": "x", "description": "d", "files": {"CLAUDE.md": "b"}})
    assert r.status_code == 403


def test_duplicate_signup_rejected(client, s3):
    client.post("/api/signup", json={"username": "aaa", "email": "a@x.com", "password": "pw123456"})
    r = client.post("/api/signup", json={"username": "aaa", "email": "a@x.com", "password": "pw123456"})
    assert r.status_code == 400


def test_login_flow(client, s3):
    client.post("/api/signup", json={"username": "lon", "email": "lon@x.com", "password": "secret123"})
    # fresh client-like login round trip: wrong password rejected, right password OK
    r = client.post("/api/login", json={"email": "lon@x.com", "password": "wrong"})
    assert r.status_code == 401
    r = client.post("/api/login", json={"email": "lon@x.com", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["username"] == "lon"


def test_unknown_setup_returns_404(client, s3):
    r = client.get("/api/setups/does-not-exist")
    assert r.status_code == 404
    # download is auth-gated now: sign up first so we reach 404 (not 401)
    client.post("/api/signup", json={"username": "seek", "email": "seek@x.com", "password": "pw123456"})
    r = client.post("/api/setups/does-not-exist/download")
    assert r.status_code == 404


def test_list_ordering_and_runs_code(client, s3):
    client.post("/api/signup", json={"username": "ord", "email": "ord@x.com", "password": "pw123456"})
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
    r = client.post("/api/setups/plain-flow/download")
    assert r.status_code == 200
    assert "url" in r.json()

    listing = client.get("/api/setups").json()
    slugs = [s["slug"] for s in listing]
    assert slugs[0] == "plain-flow"  # more downloads sorts first

    by_slug = {s["slug"]: s for s in listing}
    assert by_slug["hooky-flow"]["runs_code"] is True
    assert by_slug["plain-flow"]["runs_code"] is False
