"""The canonical gather spec must reach agents through both channels:
MCP server instructions and GET /llms.txt."""
from app.mcp_server import mcp, PUBLISHING_GUIDE


def test_guide_served_as_mcp_instructions():
    assert mcp.instructions == PUBLISHING_GUIDE


def test_guide_covers_the_synthesized_and_dangerous_bits():
    for needle in ("plugins.json", "enabledPlugins", "mcpServers",
                   "~/.claude.json", "prepare_setup", "MEMORY.md"):
        assert needle in PUBLISHING_GUIDE, needle


def test_llms_txt_route(client):
    r = client.get("/llms.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "agent publishing guide" in r.text
