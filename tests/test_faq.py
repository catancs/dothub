def test_faq_page_renders(client):
    r = client.get("/faq")
    assert r.status_code == 200
    body = r.text.lower()
    assert "effects manifest" in body
    assert "publish" in body


def test_faq_covers_key_topics(client):
    r = client.get("/faq")
    assert r.status_code == 200
    body = r.text.lower()
    # Agent-native publishing has no web upload form.
    assert "no upload form" in body or "no upload button" in body
    # The MCP add command is shown so users can connect Claude Code.
    assert "claude mcp add" in body
    # Secret handling is called out.
    assert "secret_flags" in body


def test_faq_link_in_nav(client):
    r = client.get("/")
    assert 'href="/faq"' in r.text
