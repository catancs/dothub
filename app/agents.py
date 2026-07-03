"""Coding-agent provenance registry.

The publishing agent declares which coding agent extracted the setup (an
`agent` slug). dothub maps known slugs to a display label, a brand-colored
category glyph, and shows provenance on the feed + detail pages. Unknown
slugs render with a generic glyph and the raw slug as the label — new agents
work immediately, they just look generic until added here.

Open-ended by design: the platform accepts any string.

Scope note: the registry covers agents that produce a *portable local setup*
worth sharing (CLI agents, editor/IDE agents, and AGENTS.md-based async
SWEs). Fully-hosted prompt-to-app builders (Replit, Lovable, v0, Bolt, ...)
have huge user bases but no extractable config bundle, so they are
intentionally omitted — an unknown slug still renders if one is passed.
"""

# Inline SVG only (no external fonts/CDN) — the app CSP blocks remote assets.
# One glyph per category; each uses currentColor so the template can tint it
# with the agent's brand color. 24x24 viewBox, stroke-based to match the
# existing icon style in the templates.
def _svg(body: str) -> str:
    return (
        '<svg class="ag-ic" width="16" height="16" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


# cli: a terminal prompt ">_"; ide: code brackets "< >"; cloud: a cloud.
_ICONS = {
    "cli": _svg('<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>'),
    "ide": _svg('<polyline points="8 8 4 12 8 16"/><polyline points="16 8 20 12 16 16"/>'
                '<line x1="13" y1="6" x2="11" y2="18"/>'),
    "cloud": _svg('<path d="M17.5 19a4.5 4.5 0 0 0 .5-8.98A6 6 0 0 0 6 9a4 4 0 0 0 0 10z"/>'),
}

# Claude Code keeps its own sunburst mark (our own product).
_CLAUDE_ICON = _svg(
    '<path d="M12 2v4M12 18v4M2 12h4M18 12h4M5 5l2.5 2.5M16.5 16.5L19 19'
    'M19 5l-2.5 2.5M7.5 16.5L5 19"/><circle cx="12" cy="12" r="3"/>'
)

# slug -> {label, cat, color}. `cat` picks the glyph; `color` tints it.
# Ranked roughly by mid-2026 user population within each cluster. Slugs are
# canonical: publishers should use these so provenance doesn't fragment.
AGENTS: dict[str, dict] = {
    # --- CLI / terminal agents ---
    "claude-code":  {"label": "Claude Code",  "cat": "cli", "color": "#D97757", "icon": _CLAUDE_ICON},
    "codex":        {"label": "Codex",        "cat": "cli", "color": "#10A37F"},
    "gemini-cli":   {"label": "Gemini CLI",   "cat": "cli", "color": "#4285F4"},
    "copilot-cli":  {"label": "Copilot CLI",  "cat": "cli", "color": "#6E40C9"},
    "cursor-cli":   {"label": "Cursor CLI",   "cat": "cli", "color": "#4B8BF5"},
    "opencode":     {"label": "OpenCode",     "cat": "cli", "color": "#E0A100"},
    "aider":        {"label": "Aider",        "cat": "cli", "color": "#4CAF50"},
    "goose":        {"label": "goose",        "cat": "cli", "color": "#2FBF71"},
    "qwen-code":    {"label": "Qwen Code",    "cat": "cli", "color": "#615CED"},
    "crush":        {"label": "Crush",        "cat": "cli", "color": "#D75FBB"},
    "amp":          {"label": "Amp",          "cat": "cli", "color": "#FF5543"},
    "warp":         {"label": "Warp",         "cat": "cli", "color": "#18B0D8"},
    "grok-cli":     {"label": "Grok CLI",     "cat": "cli", "color": "#8E8E93"},  # xAI; monochrome brand -> neutral tint
    # --- IDE / editor agents ---
    "copilot":     {"label": "GitHub Copilot", "cat": "ide", "color": "#6E40C9"},
    "amazon-q":    {"label": "Amazon Q",       "cat": "ide", "color": "#A166FF"},  # huge base; sunsetting -> Kiro by Apr 2027
    "kiro":        {"label": "Kiro",           "cat": "ide", "color": "#9046FF"},  # AWS; Amazon Q successor (Electric Violet)
    "cursor":      {"label": "Cursor",         "cat": "ide", "color": "#4B8BF5"},
    "windsurf":    {"label": "Windsurf",       "cat": "ide", "color": "#09B6A2"},
    "antigravity": {"label": "Antigravity",    "cat": "ide", "color": "#4285F4"},
    "junie":       {"label": "JetBrains Junie", "cat": "ide", "color": "#FE2857"},
    "zed":         {"label": "Zed",            "cat": "ide", "color": "#2F6EF7"},
    "trae":        {"label": "Trae",           "cat": "ide", "color": "#FF2D55"},
    "tabnine":     {"label": "Tabnine",        "cat": "ide", "color": "#3D5AFE"},
    "qodo":        {"label": "Qodo Gen",       "cat": "ide", "color": "#6D5AE6"},
    "augment":     {"label": "Augment Code",   "cat": "ide", "color": "#6E6E73"},  # monochrome brand -> neutral tint
    "kilo-code":   {"label": "Kilo Code",      "cat": "ide", "color": "#7C3AED"},
    "roo-code":    {"label": "Roo Code",       "cat": "ide", "color": "#6C4BF0"},  # Cline fork; maintained successor is Zoo Code
    "continue":    {"label": "Continue",       "cat": "ide", "color": "#E5484D"},
    "cline":       {"label": "Cline",          "cat": "ide", "color": "#3B82F6"},
    # --- Cloud / async SWE agents (AGENTS.md-based, shareable config) ---
    "devin":       {"label": "Devin",     "cat": "cloud", "color": "#5B6EF5"},
    "jules":       {"label": "Jules",     "cat": "cloud", "color": "#4285F4"},
    "factory":     {"label": "Factory",   "cat": "cloud", "color": "#E5673B"},
    "openhands":   {"label": "OpenHands", "cat": "cloud", "color": "#E8A33D"},  # All Hands AI; most-starred OSS SWE agent
}


def agent_info(slug: str | None) -> dict:
    """Return {'label', 'icon', 'color'} for a slug. Known slugs get their
    brand color + category glyph (or a bespoke icon); unknown/None fall back to
    a generic CLI glyph, no tint, and the raw slug as the label."""
    a = AGENTS.get(slug or "")
    if a:
        return {"label": a["label"], "icon": a.get("icon") or _ICONS[a["cat"]],
                "color": a["color"]}
    return {"label": slug or "agent", "icon": _ICONS["cli"], "color": None}


def is_known(slug: str | None) -> bool:
    return bool(slug and slug in AGENTS)
