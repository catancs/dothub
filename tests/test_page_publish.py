def test_publish_page_renders(client):
    r = client.get("/publish")
    assert r.status_code == 200
    assert "publish" in r.text.lower()
    assert "mcp" in r.text.lower()  # mentions the MCP add command


def test_publish_link_in_nav(client):
    r = client.get("/")
    assert 'href="/publish"' in r.text
