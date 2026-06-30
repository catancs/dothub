import app.models  # noqa: F401 — register tables on Base.metadata before db fixture's create_all
from app import setups  # noqa: F401 — ensure models import at collection time

import pytest


def test_mcp_publish_preview_install_list(db, s3, monkeypatch):
    from app.models import User, ApiKey
    from app import security, mcp_server

    u = User(username="cata", email="c@x.com", password_hash="x")
    db.add(u)
    db.commit()
    plain, kh = security.generate_api_key()
    db.add(ApiKey(user_id=u.id, key_hash=kh))
    db.commit()

    # make the tools use our test db session + our auth key
    monkeypatch.setattr(mcp_server, "_open_session", lambda: db)
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: plain)

    res = mcp_server.publish_setup("My Flow", "d", {"CLAUDE.md": "x"})
    assert res["slug"] == "my-flow"

    prev = mcp_server.preview_setup("my-flow")
    assert prev["effects"]["runs_code"] is False

    inst = mcp_server.install_setup("my-flow")
    assert inst["files"] == {"CLAUDE.md": "x"}

    listing = mcp_server.list_setups()
    assert any(s["slug"] == "my-flow" for s in listing)


def test_mcp_publish_requires_key(db, s3, monkeypatch):
    from app import mcp_server

    monkeypatch.setattr(mcp_server, "_open_session", lambda: db)
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: None)
    with pytest.raises(PermissionError):
        mcp_server.publish_setup("X", "", {"a.md": "1"})


def test_mcp_publish_invalid_key_rejected(db, s3, monkeypatch):
    from app import mcp_server

    monkeypatch.setattr(mcp_server, "_open_session", lambda: db)
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: "not-a-real-key")
    with pytest.raises(PermissionError):
        mcp_server.publish_setup("X", "", {"a.md": "1"})


def test_mcp_tools_registered():
    """The four functions are registered as MCP tools on the FastMCP instance."""
    import asyncio
    from app import mcp_server

    tools = asyncio.run(mcp_server.mcp.get_tools())
    for name in ("publish_setup", "preview_setup", "install_setup", "list_setups"):
        assert name in tools


def test_mcp_app_mountable():
    """get_mcp_app() returns an ASGI app carrying a lifespan for mounting."""
    from app import mcp_server

    mcp_app = mcp_server.get_mcp_app()
    assert callable(mcp_app)
    assert mcp_app.lifespan is not None
