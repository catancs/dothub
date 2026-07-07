"""Server-rendered Setup detail page (/s/{slug})."""


def _publish_risky(client):
    """Sign up and publish a setup exercising hooks, plugins, a script tag, and a secret."""
    r = client.post("/api/signup", json={
        "username": "catancs", "email": "cat@example.com", "password": "Testpass123",
    })
    assert r.status_code == 200, r.text

    files = {
        "CLAUDE.md": "# Risky example\nMove fast.",
        "hooks/hooks.json": (
            '{"hooks": {"PreToolUse": [{"hooks": '
            '[{"type": "command", "command": "echo hello-hook"}]}]}}'
        ),
        "plugins.json": (
            '{"plugins": [{"name": "auto-shipper", "marketplace": "shady", '
            '"enabled": true}], "marketplaces": {"shady": '
            '{"source": "github", "repo": "owner/thing"}}}'
        ),
        # Script tag must be escaped; secret must trip the flag (not preceded by alnum).
        "notes.md": "Inject <script>alert(1)</script> and key sk-abcd1234efgh5678 here.",
    }
    r = client.post("/api/setups", json={
        "title": "Risky Example", "description": "teaching setup", "files": files,
    })
    assert r.status_code == 200, r.text
    return r.json()["slug"]


def test_detail_page_renders_contents_plugins_and_escapes(client, s3):
    slug = _publish_risky(client)

    r = client.get(f"/s/{slug}")
    assert r.status_code == 200, r.text
    html = r.text

    # Hook command text is shown verbatim.
    assert "echo hello-hook" in html

    # Plugin source repo is shown.
    assert "owner/thing" in html

    # The file content is present (the notes line shows up in the viewer).
    assert "Inject" in html
    assert "here." in html

    # The script tag is ESCAPED, never raw.
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)" not in html

    # The secret is surfaced via the secret banner / secret_flags.
    assert "Possible secret detected" in html
    assert "notes.md" in html


def test_detail_revert_absent_for_logged_out_client(client, s3):
    # Publish as the owner, then a second version so a prior version exists
    # (Revert only ever shows on non-current versions). View anonymously.
    slug = _publish_risky(client)
    r = client.post("/api/setups", json={
        "title": "Risky Example", "slug": slug,
        "files": {"CLAUDE.md": "# v2\nNow safer."},
    })
    assert r.status_code == 200, r.text
    client.cookies.clear()  # drop the session set during signup

    r = client.get(f"/s/{slug}")
    assert r.status_code == 200, r.text
    html = r.text

    # No Revert control and no Follow control for a logged-out viewer.
    assert "onclick=\"revert(" not in html
    assert "Follow" not in html


def test_detail_404_for_missing_slug(client, s3):
    r = client.get("/s/does-not-exist")
    assert r.status_code == 404
