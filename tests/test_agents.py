"""Agent-provenance registry: known agents get label+icon+brand color, unknown
fall back to a generic glyph with the raw slug and no tint."""
from app.agents import agent_info, is_known, AGENTS


def test_known_agent_returns_label_icon_color():
    info = agent_info("claude-code")
    assert info["label"] == "Claude Code"
    assert "<svg" in info["icon"] and "ag-ic" in info["icon"]
    assert info["color"].startswith("#")


def test_every_known_agent_is_well_formed():
    for slug, a in AGENTS.items():
        info = agent_info(slug)
        assert a["label"], slug
        assert a["cat"] in ("cli", "ide", "cloud"), slug
        assert a["color"].startswith("#"), slug
        assert "<svg" in info["icon"] and "ag-ic" in info["icon"], slug


def test_expected_agents_present():
    # a representative spread across the three clusters must be covered,
    # including the mid-2026 high-population additions (Copilot CLI, Amazon Q,
    # Kiro, Roo Code, Qodo, Augment, OpenHands).
    for slug in ("claude-code", "codex", "gemini-cli", "copilot", "cursor",
                 "windsurf", "antigravity", "cline", "zed", "aider", "devin",
                 "jules", "opencode", "copilot-cli", "cursor-cli", "amazon-q",
                 "kiro", "roo-code", "qodo", "augment", "openhands", "grok-cli"):
        assert is_known(slug), slug


def test_category_glyphs_differ():
    # CLI, IDE and cloud agents get visually distinct glyphs
    cli = agent_info("codex")["icon"]
    ide = agent_info("cursor")["icon"]
    cloud = agent_info("devin")["icon"]
    assert cli != ide != cloud and cli != cloud


def test_unknown_slug_falls_back_generic_no_tint():
    info = agent_info("some-new-agent")
    assert info["label"] == "some-new-agent"
    assert "<svg" in info["icon"]
    assert info["color"] is None  # no brand tint for unknown


def test_none_slug_falls_back_to_default_label():
    info = agent_info(None)
    assert info["label"] == "agent"
    assert info["color"] is None


def test_is_known():
    assert is_known("claude-code")
    assert is_known("codex")
    assert not is_known("nope")
    assert not is_known(None)
