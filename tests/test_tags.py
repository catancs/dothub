from app.bundle import effects_manifest


def test_tags_for_full_setup():
    files = {
        "skills/x/SKILL.md": "# x",
        "commands/y.md": "# y",
        "agents/z.md": "# z",
        "hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo hi"}]}}',
        ".mcp.json": '{"mcpServers":{"linear":{"command":"npx"}}}',
        "plugins.json": '{"plugins":[{"name":"p","enabled":true}],"marketplaces":{}}',
    }
    m = effects_manifest(files)
    assert m["tags"][0] == "hooks"
    assert "mcp:linear" in m["tags"]
    assert "plugins" in m["tags"]
    assert "commands" in m["tags"]
    assert "agents" in m["tags"]
    assert "skills-only" not in m["tags"]


def test_tags_skills_only_when_no_code():
    files = {"skills/x/SKILL.md": "# x", "commands/y.md": "# y"}
    m = effects_manifest(files)
    assert m["runs_code"] is False
    assert "skills-only" in m["tags"]
    assert "hooks" not in m["tags"]
    assert "plugins" not in m["tags"]


def test_tags_deterministic_order():
    files = {
        "agents/z.md": "# z",
        "commands/y.md": "# y",
        "hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo hi"}]}}',
        ".mcp.json": '{"mcpServers":{"alpha":{"command":"x"},"beta":{"command":"y"}}}',
    }
    m = effects_manifest(files)
    # hooks first, then mcp names in file order, then commands, then agents
    assert m["tags"] == ["hooks", "mcp:alpha", "mcp:beta", "commands", "agents"]


def test_primary_tag_precedence():
    from app.bundle import primary_tag
    assert primary_tag({"runs_code": False, "tags": ["skills-only", "commands"]}) == "skills-only"
    assert primary_tag({"runs_code": True, "tags": ["hooks", "mcp:linear", "commands"]}) == "hooks"
    assert primary_tag({"runs_code": True, "tags": ["mcp:linear", "commands"]}) == "mcp:linear"
    assert primary_tag({"runs_code": True, "tags": ["plugins"]}) == "plugins"
    assert primary_tag({"runs_code": True, "tags": ["commands"]}) == "commands"
    assert primary_tag({"runs_code": True, "tags": ["agents"]}) == "agents"
    assert primary_tag({"runs_code": False, "tags": []}) is None
