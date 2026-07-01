import pytest
from app.bundle import validate_files, pack, unpack, effects_manifest, slugify, BundleError

def test_validate_rejects_traversal():
    with pytest.raises(BundleError):
        validate_files({"../evil.sh": "x"}, max_bytes=1000)

def test_validate_rejects_absolute():
    with pytest.raises(BundleError):
        validate_files({"/etc/passwd": "x"}, max_bytes=1000)

def test_validate_rejects_oversize():
    with pytest.raises(BundleError):
        validate_files({"a.md": "x" * 2000}, max_bytes=1000)

def test_pack_unpack_roundtrip():
    files = {"CLAUDE.md": "hello", "skills/x/SKILL.md": "do x"}
    assert unpack(pack(files)) == files

def test_pack_is_deterministic():
    files = {"b.md": "1", "a.md": "2"}
    assert pack(files) == pack(files)

def test_effects_manifest_detects_hooks_and_mcp():
    files = {
        "hooks/hooks.json": '{"hooks": {"PreToolUse": [{"hooks": [{"type":"command","command":"rm -rf /tmp/x"}]}]}}',
        ".mcp.json": '{"mcpServers": {"weather": {"command": "uvx", "args": ["weather-mcp"]}}}',
        "skills/a/SKILL.md": "x",
        "commands/c.md": "x",
    }
    m = effects_manifest(files)
    assert m["runs_code"] is True
    assert {"event": "PreToolUse", "command": "rm -rf /tmp/x"} in m["hooks"]
    assert {"name": "weather", "command": "uvx", "args": ["weather-mcp"]} in m["mcp_servers"]
    assert m["counts"]["skills"] == 1 and m["counts"]["commands"] == 1

def test_effects_manifest_no_code():
    m = effects_manifest({"CLAUDE.md": "just rules"})
    assert m["runs_code"] is False

def test_secret_flag():
    m = effects_manifest({"x.md": "key sk-ABCD12345678 here"})
    assert any("x.md" in f for f in m["secret_flags"])

def test_secret_flag_no_false_positive_midword():
    # 'task-...' / 'risk-...' must NOT be flagged as an sk- secret
    m = effects_manifest({"x.md": "see the task-12345678 item and risk-99999999 note"})
    assert m["secret_flags"] == []

def test_slugify():
    assert slugify("My Cool Flow!") == "my-cool-flow"


from app.bundle import effects_manifest, SECRET_PATTERNS


def test_secret_patterns_catch_github_slack_anthropic_google():
    files = {
        "CLAUDE.md": "token is ghp_0123456789abcdef0123456789abcdef0123",
        "a.txt": "slack xoxb-1234567890-abcdef",
        "b.txt": "anthropic sk-ant-abc123def456",
        "c.txt": "google AIzaSyA" + "B" * 30,
        "d.txt": "aws AKIAIOSFODNN7EXAMPLE",
    }
    m = effects_manifest(files)
    paths = {f.split(":")[0] for f in m["secret_flags"]}
    assert "CLAUDE.md" in paths   # ghp_
    assert "a.txt" in paths       # xoxb-
    assert "b.txt" in paths       # sk-ant-
    assert "c.txt" in paths       # AIza
    assert "d.txt" in paths       # AKIA (existing, must still match)
