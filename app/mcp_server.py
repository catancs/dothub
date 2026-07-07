"""Remote MCP server exposing dothub's publish/preview/install/list as tools.

The agent self-push surface: a Claude Code agent talks to this server over HTTP
(streamable-http) and can publish its own setup, preview/install others, and
browse the public feed.

Design notes (FastMCP 2.14.7):
- `@mcp.tool` / `mcp.tool(fn)` registers a `FunctionTool` object; it does NOT
  leave a plain callable bound to the name. So we define each tool body as a
  plain module-level function and register it *functionally* via `mcp.tool(fn)`
  WITHOUT rebinding the name. That keeps `publish_setup` etc. directly callable
  (and unit-testable) while still registering them as MCP tools.
- `_open_session()` and `_bearer_key()` are separate module functions so tests
  can monkeypatch them. `_bearer_key()` is the ONLY place that calls
  `get_http_headers()`, so it's the only thing requiring an active HTTP context.
"""

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from sqlalchemy import select

from .db import SessionLocal
from .models import User, ApiKey
from . import security, setups

PUBLISHING_GUIDE = """\
# dothub — agent publishing guide

dothub is agent-first. There is no upload form and no server-side extractor:
you, the coding agent, gather the user's Claude Code setup, preview its
effects, and publish. This is the canonical gather spec.

## Bundle layout (relative paths, UTF-8 text only)

Gather from the user scope (~/.claude/) and, for project setups, the project
(.claude/ and repo root). Map sources to these bundle paths:

- skills/<name>/SKILL.md + text siblings  <- ~/.claude/skills/ or .claude/skills/
- commands/**/*.md                        <- ~/.claude/commands/ or .claude/commands/
- agents/**/*.md                          <- ~/.claude/agents/ or .claude/agents/
- output-styles/**                        <- ~/.claude/output-styles/
- keybindings.json                        <- ~/.claude/keybindings.json
- CLAUDE.md                               <- global or project CLAUDE.md
- .claude/rules/**                        <- project rules
- settings.json, settings.local.json      <- ~/.claude/ or .claude/ settings.
  Keep hooks, statusLine, env, permissions, enabledPlugins, outputStyle,
  model. Strip anything secret-looking from env values before uploading.
- .mcp.json                               <- project .mcp.json as-is. For
  user-scope servers, copy ONLY the "mcpServers" object from ~/.claude.json
  into .mcp.json. NEVER upload ~/.claude.json itself: it holds private state.
- plugins.json                            <- synthesize; Claude Code has no
  such file. Build
    {"marketplaces": {"<mkt>": {"repo": "owner/repo"}},
     "plugins": [{"name": "<plugin>", "marketplace": "<mkt>", "enabled": true}]}
  from enabledPlugins in settings.json (keys are "plugin@marketplace") and
  ~/.claude/plugins/known_marketplaces.json (source.repo). Skip disabled
  plugins. Never upload plugin caches or install state.

## Never include

Memory (MEMORY.md, memory/), conversation history, credentials or live
tokens, API keys in env values, .git/, node_modules/, *.db, binaries. Setups
are text-only by design.

## Limits

500 files, 1 MB per file, 5 MB per bundle. Oversized publishes are rejected
whole; trim file contents rather than silently dropping setup pieces.

## Agent

Pass your own `agent` slug to publish_setup so installers see provenance.
Canonical slugs include: claude-code, codex, gemini-cli, copilot-cli,
cursor-cli, opencode, aider, goose, qwen-code, crush, amp, warp, grok-cli
(CLIs); copilot, cursor, windsurf, antigravity, amazon-q, kiro, junie, zed,
trae, tabnine, qodo, augment, kilo-code, roo-code, continue, cline (editors);
devin, jules, factory, openhands (async SWEs). Use the slug for your agent so
provenance doesn't fragment; any other string still works, rendering with a
generic icon and your slug as the label. Defaults to "claude-code" when omitted.

## Flow

1. prepare_setup(files) — dry run. Show the returned effects, secret_flags
   and warnings to the user before publishing.
2. publish_setup(title, description, files) — after explicit user approval.
   Re-publishing the same slug creates a new version.

Hooks, MCP servers, plugins and statusLine commands are shown to installers
as "runs code" effects. Installers rely on your gathering being complete: a
setup whose hooks you forgot advertises itself as safer than it is.

Installing is the reverse: install_setup(slug) returns {files}; show the
effects, get approval, then write files into ~/.claude/ (user scope) or the
project .claude/.
"""

mcp = FastMCP("dothub", instructions=PUBLISHING_GUIDE)


def _open_session():
    return SessionLocal()


def _bearer_key() -> str | None:
    """Extract the plaintext API key from the request's Authorization header.

    The single place that touches the HTTP context. Returns None when there is
    no usable bearer token (or no HTTP context at all).
    """
    headers = get_http_headers()
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


def _require_user(db) -> User:
    key = _bearer_key()
    if not key:
        raise PermissionError("missing API key")
    ak = db.scalar(select(ApiKey).where(ApiKey.key_hash == security.hash_api_key(key)))
    if not ak:
        raise PermissionError("invalid API key")
    return db.get(User, ak.user_id)


def publish_setup(
    title: str,
    description: str,
    files: dict[str, str],
    slug: str | None = None,
    agent: str = "claude-code",
    public: bool = False,
) -> dict:
    """Publish the caller's coding-agent setup. `files` is {relative_path: text_content}.

    Requires a valid `Authorization: Bearer <dothub-api-key>` header.

    Published PRIVATELY by default: a private setup is visible only to its owner
    and is hidden from the public feed, search, and everyone else. Tell the user
    it landed privately and that they choose when to go public — they open the
    setup's page and click "Publish to everyone" (or pass public=true here to
    publish immediately). The response's `is_public` reflects the result.

    `agent` declares which coding agent extracted this setup (e.g. "claude-code",
    "codex", "cursor", "windsurf", "antigravity"). Shown to installers as a
    provenance indicator. Pass your own identifier if not in that list.

    Gather per the publishing guide (this server's MCP instructions, also at
    GET /llms.txt): map ~/.claude and project .claude into bundle-root paths
    (skills/, commands/, agents/, output-styles/, settings.json, CLAUDE.md,
    .mcp.json), synthesize plugins.json from enabledPlugins, and never upload
    ~/.claude.json, memory files, or secrets. The server enforces path safety
    and size, not the convention. Call `prepare_setup` first to preview
    effects and secret flags.
    """
    db = _open_session()
    try:
        user = _require_user(db)
        return setups.publish(db, user, title, description, files, slug, agent,
                              is_public=public)
    finally:
        db.close()


def preview_setup(slug: str) -> dict:
    """Return the effects manifest + file list for a setup, WITHOUT installing.

    Show this to the user first so they can review what the setup does. The
    caller is authenticated, so this also previews the caller's own private
    setups (a private setup stays hidden from everyone else).
    """
    db = _open_session()
    try:
        user = _require_user(db)
        return setups.preview(db, slug, viewer=user)
    finally:
        db.close()


def install_setup(slug: str) -> dict:
    """Return a setup's files + effects so the agent can write them locally.

    Only do this AFTER the user has reviewed the preview and approved.
    Requires a valid `Authorization: Bearer <dothub-api-key>` header.
    """
    db = _open_session()
    try:
        user = _require_user(db)
        return setups.install(db, slug, user)
    finally:
        db.close()


def list_setups(query: str | None = None) -> list[dict]:
    """List public setups (each entry includes a `runs_code` flag)."""
    db = _open_session()
    try:
        return setups.list_setups(db, query=query)
    finally:
        db.close()


def search_setups(query: str | None = None,
                  runs_code: bool | None = None,
                  tag: str | None = None) -> list[dict]:
    """Search public setups by title and/or filter by whether they run code
    or by an auto-derived tag (e.g. "hooks", "skills-only", "mcp:linear").

    Use this to find setups matching a need, e.g. only no-code setups
    (runs_code=False) or only setups with hooks (tag="hooks").
    """
    db = _open_session()
    try:
        return setups.list_setups(db, query=query, runs_code=runs_code, tag=tag)
    finally:
        db.close()


def prepare_setup(files: dict[str, str]) -> dict:
    """Preview a setup's effects BEFORE publishing. Read-only, no auth needed.

    Call this first with the files you gathered (relative path to text content),
    surface the returned `effects` and any `secret_flags` to the user, and only
    then call `publish_setup` once the user approves.

    Gather per the publishing guide (this server's MCP instructions, also at
    GET /llms.txt): map ~/.claude and project .claude into bundle-root paths,
    synthesize plugins.json from enabledPlugins, exclude ~/.claude.json,
    memory files, and secrets. The server enforces path safety and size, not
    the convention.
    """
    from . import bundle as _bundle
    from .config import settings
    try:
        _bundle.validate_files(files, settings.max_bundle_bytes)
    except _bundle.BundleError as e:
        return {"valid": False, "error": str(e), "effects": None,
                "gathered_count": len(files), "total_bytes": 0, "warnings": []}
    effects = _bundle.effects_manifest(files)
    total = sum(len(c.encode("utf-8")) for c in files.values())
    warnings: list[str] = []
    if not any(p.startswith("skills/") for p in files):
        warnings.append("no skills/ files found")
    if "hooks/hooks.json" in files and not effects["hooks"]:
        warnings.append("hooks.json present but no hook commands parsed")
    return {"valid": True, "error": None, "effects": effects,
            "gathered_count": len(files), "total_bytes": total, "warnings": warnings}


# Register the plain functions as MCP tools without rebinding their names, so
# they remain directly importable + callable for unit tests.
mcp.tool(publish_setup)
mcp.tool(preview_setup)
mcp.tool(install_setup)
mcp.tool(list_setups)
mcp.tool(search_setups)
mcp.tool(prepare_setup)


def get_mcp_app():
    """ASGI app for mounting under the main FastAPI app at /mcp.

    The returned app carries a `.lifespan` that initializes the MCP session
    manager; the parent FastAPI app MUST run that lifespan (see app.main).
    """
    return mcp.http_app(path="/")
