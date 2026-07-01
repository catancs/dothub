import pytest
from app import mcp_server, bundle


def test_prepare_setup_valid_full(monkeypatch):
    files = {
        "skills/a/SKILL.md": "# a",
        "hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo hi"}]}}',
        ".mcp.json": '{"mcpServers":{"linear":{"command":"npx"}}}',
    }
    res = mcp_server.prepare_setup(files)
    assert res["valid"] is True
    assert res["error"] is None
    assert res["gathered_count"] == 3
    assert res["total_bytes"] > 0
    assert res["effects"]["runs_code"] is True
    assert "hooks" in res["effects"]["tags"]


def test_prepare_setup_rejects_traversal(monkeypatch):
    files = {"../etc/passwd": "x"}
    res = mcp_server.prepare_setup(files)
    assert res["valid"] is False
    assert "escapes bundle root" in res["error"]
    assert res["effects"] is None


def test_prepare_setup_flags_secret():
    files = {"CLAUDE.md": "token ghp_" + "a" * 30}
    res = mcp_server.prepare_setup(files)
    assert res["valid"] is True  # not a hard error
    assert len(res["effects"]["secret_flags"]) >= 1


def test_prepare_setup_no_auth_required(monkeypatch):
    # prepare_setup must NOT call _require_user; calling it with no bearer
    # header in context should still succeed.
    monkeypatch.setattr(mcp_server, "_bearer_key", lambda: None)
    files = {"skills/a/SKILL.md": "# a"}
    res = mcp_server.prepare_setup(files)
    assert res["valid"] is True
