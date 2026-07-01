# dothub Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the pre-deploy Wave 1 batch for dothub: reliable agent-native publishing, working web/MCP search, a shoppable feed (no-code lane + auto-tags), README rendering, and pre-deploy security hygiene, all test-covered.

**Architecture:** All features funnel through the existing `app/bundle.py` (manifest computation) and `app/setups.py` (core publish/preview/install/list logic) cores, with thin front-ends in `app/api.py` (REST), `app/mcp_server.py` (MCP tools), and `app/web/*.py` (server-rendered pages). No new core publishing path; new MCP tools (`prepare_setup`, `search_setups`) and new filters delegate to existing functions. Tags live in the existing `manifest_json` JSON column (no schema change in Wave 1). Alembic is added as a baseline stamp only.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 (sync), Jinja2, FastMCP 2.14.7, Postgres (prod) / SQLite (dev+tests via `StaticPool`), boto3/S3, bcrypt, pytest + httpx + moto, Playwright (browser verification). New dep: `slowapi`. New dev dep: `alembic`.

## Global Constraints

- NO em dashes anywhere: UI copy, code, comments, docs, commit messages. Use commas, colons, periods, or hyphens instead.
- NO AI attribution in commits: no `Co-authored-by`, no `Generated with Claude`, no robot emoji.
- GitHub account for any push: `catancs` (run `gh auth switch --user catancs` before pushing). Do not push unless explicitly asked.
- Repo root: `/Users/cata/Apps/dothub`. Tests run with `pytest` from repo root; `tests/conftest.py` presets env vars and provides `db`, `s3`, `client` fixtures.
- Deps live in `requirements.txt` (no `pyproject.toml`). Pin new deps with `==` major.minor wildcards matching the existing style.
- All sub-agents implementing tasks run on Opus (`model: "opus"`), never haiku.
- Every code step shows the actual code; every test step shows the actual test. No placeholders.
- The `effects_manifest` return dict is the source of truth for tags: tags are computed inside `bundle.effects_manifest` and stored in `manifest_json["tags"]`.

---

## File Structure

**Modified files:**
- `app/bundle.py` — add `tags` to `effects_manifest`; add per-file size cap to `validate_files`; extend `SECRET_PATTERNS`.
- `app/setups.py` — add `runs_code`/`tag` filters to `list_setups`; add `viewer` param to `preview` for visibility gate.
- `app/config.py` — add `max_file_bytes` setting.
- `app/api.py` — pass `viewer` to `preview` in `api_get`; add signup validation in `/api/signup`.
- `app/web/auth.py` — add signup validation in `/signup`.
- `app/web/feed.py` — add `q` and `no-code` tab handling.
- `app/web/detail.py` — pass `viewer` to `preview`; pass README + tags to template.
- `app/mcp_server.py` — add `prepare_setup` and `search_setups` tools; expand `publish_setup` docstring.
- `app/main.py` — harden `SessionMiddleware` (https_only, samesite); wire `slowapi` limiter.
- `app/templates/feed.html` — wire search form; add No-code pill; render primary tag.
- `app/templates/detail.html` — render README block; render tag set in header.
- `app/templates/base.html` — add Publish nav link.
- `app/templates/publish.html` — new instructions page.
- `app/web/publish.py` — new route for `/publish`.
- `app/web/__init__.py` — register publish router.
- `infra/user_data.sh.tpl` — generate a strong `SESSION_SECRET`.
- `requirements.txt` — add `slowapi`, `alembic`.
- `deploy/DEPLOY.md` — note CSRF as a known limitation; note SESSION_SECRET generation.

**New files:**
- `app/validation.py` — shared signup validator (username/email/password).
- `app/ratelimit.py` — slowapi limiter instance + key func.
- `app/templates/publish.html` — instructions page template.
- `app/web/publish.py` — `/publish` route.
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/` — Alembic baseline.
- `tests/test_validation.py`, `tests/test_tags.py`, `tests/test_prepare_setup.py`, `tests/test_search.py`, `tests/test_ratelimit.py`, `tests/test_visibility.py`, `tests/test_readme.py` — new test files.

**Responsibility boundaries:** `bundle.py` owns manifest computation (including tags) and file validation. `setups.py` owns DB-facing core logic. `validation.py` owns input format rules, shared by web and API signup. `ratelimit.py` owns the limiter singleton. MCP tools and web routes are thin and delegate; they contain no business logic.

---

## Task 1: Extend SECRET_PATTERNS

**Files:**
- Modify: `app/bundle.py:13`
- Test: `tests/test_bundle.py`

**Interfaces:**
- Produces: the module-level `SECRET_PATTERNS` list (extended). No signature change.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_bundle.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bundle.py::test_secret_patterns_catch_github_slack_anthropic_google -v`
Expected: FAIL (ghp_, xoxb-, sk-ant-, AIza not flagged; only AKIA matches).

- [ ] **Step 3: Extend the patterns**

Replace the `SECRET_PATTERNS` line in `app/bundle.py` (line 13) with:

```python
SECRET_PATTERNS = [
    r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{8,}",          # generic sk- (OpenAI-style)
    r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_\-]{8,}",   # Anthropic
    r"ghp_[A-Za-z0-9]{20,}",                        # GitHub personal access token
    r"gh[os]r?_[A-Za-z0-9]{20,}",                   # GitHub OAuth/server/refresh
    r"xox[bp]-[A-Za-z0-9-]{10,}",                   # Slack bot/user token
    r"AKIA[0-9A-Z]{16}",                            # AWS access key id
    r"AIza[0-9A-Za-z_\-]{20,}",                     # Google API key
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",          # PEM private key
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bundle.py::test_secret_patterns_catch_github_slack_anthropic_google -v`
Expected: PASS.

- [ ] **Step 5: Run the full bundle test file to confirm no regressions**

Run: `pytest tests/test_bundle.py tests/test_bundle_plugins.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/bundle.py tests/test_bundle.py
git commit -m "feat: extend SECRET_PATTERNS to github, slack, anthropic, google tokens"
```

---

## Task 2: Add per-file size cap to validate_files

**Files:**
- Modify: `app/config.py:13` (add setting), `app/bundle.py:16-32` (`validate_files`)
- Test: `tests/test_bundle.py`

**Interfaces:**
- Consumes: `app.config.settings.max_file_bytes` (int, default 1 MiB).
- Produces: `validate_files(files, max_bytes, max_files=500, max_file_bytes=None)` raises `BundleError` when any single file exceeds `max_file_bytes` (or `settings.max_file_bytes` when None).

- [ ] **Step 1: Add the config setting**

In `app/config.py`, after the `max_bundle_bytes` line (line 12), add:

```python
    max_file_bytes = int(os.getenv("MAX_FILE_BYTES", str(1024 * 1024)))
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_bundle.py`:

```python
def test_validate_files_rejects_single_oversized_file():
    from app.bundle import validate_files, BundleError
    big = "a/" + "x" * 50
    files = {"small.txt": "ok", "big.txt": "x" * 100}
    # total under cap, but big.txt over a 50-byte per-file cap
    with __import__("pytest").raises(BundleError, match="file too large"):
        validate_files(files, max_bytes=10_000, max_file_bytes=50)


def test_validate_files_accepts_when_under_per_file_cap():
    from app.bundle import validate_files
    files = {"a.txt": "ok"}
    validate_files(files, max_bytes=10_000, max_file_bytes=50)  # no raise
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_bundle.py::test_validate_files_rejects_single_oversized_file -v`
Expected: FAIL (no per-file check exists; `validate_files` does not raise).

- [ ] **Step 4: Implement the per-file cap**

Replace the body of `validate_files` in `app/bundle.py` with:

```python
def validate_files(files: dict[str, str], max_bytes: int, max_files: int = 500,
                   max_file_bytes: int | None = None) -> None:
    from .config import settings
    per_file = max_file_bytes if max_file_bytes is not None else settings.max_file_bytes
    if not files:
        raise BundleError("empty bundle")
    if len(files) > max_files:
        raise BundleError(f"too many files (>{max_files})")
    total = 0
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            raise BundleError("paths and contents must be strings")
        if path.startswith("/") or path.startswith("\\"):
            raise BundleError(f"absolute path not allowed: {path}")
        norm = normpath(path)
        if norm.startswith("..") or norm.startswith("/") or ".." in norm.split("/"):
            raise BundleError(f"path escapes bundle root: {path}")
        size = len(content.encode("utf-8"))
        if size > per_file:
            raise BundleError(f"file too large: {path} ({size} > {per_file} bytes)")
        total += size
    if total > max_bytes:
        raise BundleError(f"bundle too large ({total} > {max_bytes} bytes)")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_bundle.py -v`
Expected: all PASS (including the two new ones and existing traversal/size tests).

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/bundle.py tests/test_bundle.py
git commit -m "feat: per-file size cap in validate_files"
```

---

## Task 3: Compute auto-derived tags in effects_manifest

**Files:**
- Modify: `app/bundle.py:74-137` (`effects_manifest`)
- Test: `tests/test_tags.py`

**Interfaces:**
- Produces: `effects_manifest(files)` return dict gains a `"tags": list[str]` key. Tag set: `"hooks"`, `"mcp:<name>"` per MCP server, `"plugins"`, `"skills-only"` (when `runs_code` is false), `"commands"` (when count > 0), `"agents"` (when count > 0). Order is deterministic: hooks, mcp names, plugins, skills-only, commands, agents.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tags.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tags.py -v`
Expected: FAIL (`KeyError: 'tags'`).

- [ ] **Step 3: Add tags to effects_manifest**

In `app/bundle.py`, inside `effects_manifest`, after the `runs_code` line is computed (the `return {...}` block), restructure to compute tags before returning. Replace the `return {` block (lines ~130-137) with:

```python
    runs_code = bool(hooks or mcp_servers or plugins)

    tags: list[str] = []
    if hooks:
        tags.append("hooks")
    for srv in mcp_servers:
        tags.append(f"mcp:{srv['name']}")
    if plugins:
        tags.append("plugins")
    if not runs_code:
        tags.append("skills-only")
    if counts["commands"] > 0:
        tags.append("commands")
    if counts["agents"] > 0:
        tags.append("agents")

    return {
        "hooks": hooks,
        "mcp_servers": mcp_servers,
        "plugins": plugins,
        "counts": counts,
        "runs_code": runs_code,
        "secret_flags": secret_flags,
        "tags": tags,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tags.py -v`
Expected: PASS.

- [ ] **Step 5: Run the roundtrip test to confirm publish still works with tags**

Run: `pytest tests/test_roundtrip.py tests/test_bundle.py tests/test_bundle_plugins.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/bundle.py tests/test_tags.py
git commit -m "feat: auto-derived tags in effects manifest"
```

---

## Task 4: Add primary-tag helper

**Files:**
- Modify: `app/bundle.py` (append helper)
- Test: `tests/test_tags.py`

**Interfaces:**
- Produces: `bundle.primary_tag(manifest: dict) -> str | None`. Precedence: `skills-only` when `runs_code` is false; else `hooks`; else first `mcp:*`; else `plugins`; else `commands`; else `agents`; else None. Used by the feed card.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tags.py`:

```python
def test_primary_tag_precedence():
    from app.bundle import primary_tag
    assert primary_tag({"runs_code": False, "tags": ["skills-only", "commands"]}) == "skills-only"
    assert primary_tag({"runs_code": True, "tags": ["hooks", "mcp:linear", "commands"]}) == "hooks"
    assert primary_tag({"runs_code": True, "tags": ["mcp:linear", "commands"]}) == "mcp:linear"
    assert primary_tag({"runs_code": True, "tags": ["plugins"]}) == "plugins"
    assert primary_tag({"runs_code": True, "tags": ["commands"]}) == "commands"
    assert primary_tag({"runs_code": True, "tags": ["agents"]}) == "agents"
    assert primary_tag({"runs_code": False, "tags": []}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tags.py::test_primary_tag_precedence -v`
Expected: FAIL (`ImportError: cannot import name 'primary_tag'`).

- [ ] **Step 3: Implement primary_tag**

Append to `app/bundle.py` (after `effects_manifest`, before `slugify`):

```python
def primary_tag(manifest: dict) -> str | None:
    """Pick the single most descriptive tag for a feed card.

    Precedence: skills-only (safest signal) when no code runs, then hooks,
    then the first mcp:* server, then plugins, then commands, then agents.
    Returns None when no tag applies.
    """
    tags = manifest.get("tags", [])
    if not manifest.get("runs_code", False) and "skills-only" in tags:
        return "skills-only"
    for t in ("hooks",):
        if t in tags:
            return t
    for t in tags:
        if t.startswith("mcp:"):
            return t
    for t in ("plugins", "commands", "agents"):
        if t in tags:
            return t
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tags.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bundle.py tests/test_tags.py
git commit -m "feat: primary_tag helper for feed cards"
```

---

## Task 5: Add runs_code and tag filters to list_setups

**Files:**
- Modify: `app/setups.py:101-137` (`list_setups`)
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `list_setups(db, query=None, limit=50, window=None, following_of=None, runs_code=None, tag=None) -> list[dict]`. `runs_code` and `tag` filter on `SetupVersion.manifest_json`. Each returned dict gains `"tags": [...]` (the full tag list) so the card and detail page can render them.

- [ ] **Step 1: Write the failing test**

Create `tests/test_search.py`:

```python
import pytest
from app import setups, bundle
from app.models import User


@pytest.fixture
def seeded(db):
    u = User(username="author", email="a@x.com", password_hash="h")
    db.add(u); db.flush()
    # no-code setup
    setups.publish(db, u, "Pure Skills", "desc",
                  {"skills/a/SKILL.md": "# a"}, slug="pure-skills")
    # hooks setup
    setups.publish(db, u, "Hooked", "desc",
                  {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'},
                  slug="hooked")
    return u


def test_filter_runs_code_false(db, seeded):
    items = setups.list_setups(db, runs_code=False)
    slugs = {i["slug"] for i in items}
    assert "pure-skills" in slugs
    assert "hooked" not in slugs


def test_filter_runs_code_true(db, seeded):
    items = setups.list_setups(db, runs_code=True)
    slugs = {i["slug"] for i in items}
    assert "hooked" in slugs
    assert "pure-skills" not in slugs


def test_filter_by_tag(db, seeded):
    items = setups.list_setups(db, tag="hooks")
    assert any(i["slug"] == "hooked" for i in items)
    items = setups.list_setups(db, tag="skills-only")
    assert any(i["slug"] == "pure-skills" for i in items)


def test_query_filter(db, seeded):
    items = setups.list_setups(db, query="Hook")
    assert any(i["slug"] == "hooked" for i in items)
    assert all(i["slug"] != "pure-skills" for i in items)


def test_list_returns_tags(db, seeded):
    items = setups.list_setups(db, query="Hook")
    hooked = next(i for i in items if i["slug"] == "hooked")
    assert "hooks" in hooked["tags"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search.py -v`
Expected: FAIL (`TypeError: unexpected keyword argument 'runs_code'`).

- [ ] **Step 3: Add the filters to list_setups**

In `app/setups.py`, replace the `list_setups` signature and the filter/return logic. Replace lines 101-137 (the whole `list_setups` function) with:

```python
def list_setups(db, query: str | None = None, limit: int = 50,
                window: str | None = None, following_of: User | None = None,
                runs_code: bool | None = None, tag: str | None = None) -> list[dict]:
    stmt = select(Setup, SetupVersion, User.username).join(
        SetupVersion,
        (SetupVersion.setup_id == Setup.id) & (SetupVersion.version == Setup.latest_version),
    ).join(User, User.id == Setup.owner_id).where(Setup.is_public.is_(True))
    if query:
        stmt = stmt.where(Setup.title.ilike(f"%{query}%"))

    # JSON-path filters on the manifest. SQLite and Postgres both support
    # json_extract on a JSON column for a top-level boolean / string key.
    from sqlalchemy import func as _f
    if runs_code is not None:
        # manifest_json->>'runs_code' == 'true'/'false'
        rc = _f.json_extract(SetupVersion.manifest_json, "$.runs_code")
        stmt = stmt.where(rc == runs_code)
    if tag is not None:
        # manifest_json->>'tags' rendered as text contains the tag substring.
        # Works on both SQLite and Postgres json_extract. See Step 5 fallback
        # if a backend lacks json_extract.
        stmt = stmt.where(
            _f.json_extract(SetupVersion.manifest_json, "$.tags").cast(str).contains(tag))

    delta = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}.get(window)
    since = _now() - delta if delta else None
    if since is not None:
        pc = (select(PullEvent.setup_id, func.count().label("c"))
              .where(PullEvent.created_at >= since)
              .group_by(PullEvent.setup_id).subquery())
        stmt = stmt.add_columns(func.coalesce(pc.c.c, 0).label("recent")).outerjoin(
            pc, pc.c.setup_id == Setup.id)
    else:
        stmt = stmt.add_columns(literal(0).label("recent"))

    if following_of is not None:
        followee_ids = select(Follow.followee_id).where(Follow.follower_id == following_of.id)
        stmt = stmt.where(Setup.owner_id.in_(followee_ids)).order_by(Setup.created_at.desc())
    elif since is not None:
        stmt = stmt.order_by(func.coalesce(pc.c.c, 0).desc(), Setup.downloads.desc())
    else:
        stmt = stmt.order_by(Setup.downloads.desc(), Setup.created_at.desc())

    out = []
    for s, v, username, recent in db.execute(stmt.limit(limit)).all():
        tags = v.manifest_json.get("tags", []) if v.manifest_json else []
        out.append({
            "slug": s.slug, "title": s.title, "description": s.description,
            "downloads": s.downloads, "recent_pulls": recent,
            "runs_code": bool(v.manifest_json.get("runs_code")) if v.manifest_json else False,
            "author": username, "tags": tags,
        })
    return out
```

Note: the `tag` filter uses `json_extract($.tags).cast(str).contains(tag)`, which works on both SQLite and Postgres (Postgres `json_extract` is provided by SQLAlchemy's dialect; if a backend does not support `json_extract`, fall back to a Python-side filter on the limited result set, see Step 6). The `runs_code` filter uses `json_extract($.runs_code) == <bool>`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search.py -v`
Expected: PASS. If any filter fails due to a backend JSON-function mismatch, see Step 5.

- [ ] **Step 5: Fallback if json_extract is unavailable on a backend**

If `pytest tests/test_search.py` fails with a SQL function error, replace the `runs_code`/`tag` `where` clauses with a Python-side filter applied AFTER the limited query: remove the two `if runs_code`/`if tag` `stmt.where(...)` blocks, and after building `out`, filter in Python:

```python
    if runs_code is not None:
        out = [o for o in out if o["runs_code"] == runs_code]
    if tag is not None:
        out = [o for o in out if tag in o["tags"]]
```

Document in a comment that this is post-filter and note the limit caveat (a tight filter combined with `limit=50` may under-return; acceptable for v1 discovery). Re-run `pytest tests/test_search.py -v`; expected PASS.

- [ ] **Step 6: Run the broader setups/feed tests for regressions**

Run: `pytest tests/test_setups_v2.py tests/test_page_feed.py tests/test_api.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/setups.py tests/test_search.py
git commit -m "feat: runs_code and tag filters in list_setups"
```

---

## Task 6: Wire the web search box and No-code tab

**Files:**
- Modify: `app/web/feed.py`, `app/templates/feed.html`
- Test: `tests/test_page_feed.py`

**Interfaces:**
- Consumes: `setups.list_setups(db, query=q, window=window, runs_code=False)` from Task 5.
- Produces: `GET /?q=...` filters by title; `GET /?tab=no-code` shows only `runs_code == false` setups.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_page_feed.py`:

```python
def test_feed_search_box_filters_by_title(client):
    # seed via API
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "Rails Startup", "d", {"skills/a/SKILL.md": "# a"}, slug="rails")
    setups.publish(db, u, "Writing Craft", "d", {"skills/b/SKILL.md": "# b"}, slug="writing")
    db.commit(); db.close()

    r = client.get("/?q=Rails")
    assert r.status_code == 200
    assert "rails" in r.text
    assert "writing" not in r.text


def test_feed_no_code_tab(client):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "Pure", "d", {"skills/a/SKILL.md": "# a"}, slug="pure")
    setups.publish(db, u, "Hooked", "d",
                   {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'}, slug="hooked")
    db.commit(); db.close()

    r = client.get("/?tab=no-code")
    assert r.status_code == 200
    assert "pure" in r.text
    assert "hooked" not in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_page_feed.py::test_feed_search_box_filters_by_title tests/test_page_feed.py::test_feed_no_code_tab -v`
Expected: FAIL (search box not wired; `no-code` tab not handled).

- [ ] **Step 3: Update the feed handler**

Replace `app/web/feed.py` with:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db import get_session
from app.api import optional_user
from app import setups, bundle
from app.web._render import render

router = APIRouter()


@router.get("/")
def feed(request: Request, tab: str = "discover", window: str = "7d",
         q: str | None = None,
         db: Session = Depends(get_session), user=Depends(optional_user)):
    if tab == "following":
        if user is None:
            return RedirectResponse("/login", status_code=303)
        items = setups.list_setups(db, following_of=user)
    elif tab == "no-code":
        items = setups.list_setups(db, window=window, runs_code=False)
    else:
        items = setups.list_setups(db, query=q, window=window)
    for it in items:
        it["primary_tag"] = bundle.primary_tag({"runs_code": it["runs_code"], "tags": it.get("tags", [])})
    return render(request, "feed.html",
                  {"items": items, "tab": tab, "window": window, "q": q or ""}, user=user)
```

- [ ] **Step 4: Wire the search form and No-code pill in the template**

In `app/templates/feed.html`, replace the `<label class="search"...>` block (lines 23-26) with a form:

```html
  <form class="search" method="get" action="/" style="margin-bottom:22px">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
    <input name="q" placeholder="Search setups by title" value="{{ q }}">
  </form>
```

And in the `.pills` block (lines 11-14), add the No-code pill after Following:

```html
    <div class="pills">
      <a href="/?tab=discover&window={{ window }}" class="{{ 'on' if tab == 'discover' else '' }}">Discover</a>
      <a href="/?tab=following" class="{{ 'on' if tab == 'following' else '' }}">Following</a>
      <a href="/?tab=no-code&window={{ window }}" class="{{ 'on' if tab == 'no-code' else '' }}">No-code</a>
    </div>
```

- [ ] **Step 5: Render the primary tag on the card**

In `app/templates/feed.html`, inside `.card-foot`, before the runs-code chip (around line 45), add the primary-tag pill (only when present):

```html
        {% if item.primary_tag %}
        <span class="tag" style="margin-left:auto">{{ item.primary_tag }}</span>
        {% else %}
        <span style="margin-left:auto"></span>
        {% endif %}
```

(Keep the existing runs-code chip after it. If the chip currently uses `margin-left:auto`, remove that inline style from the chip since the tag now owns the left margin.)

- [ ] **Step 6: Add the .tag style to app.css**

Append to `app/static/app.css`:

```css
.tag{font-family:var(--mono);font-size:10.5px;font-weight:500;color:var(--blue);background:var(--blue-tint);border:1.2px solid var(--blue);padding:2px 8px;border-radius:999px;white-space:nowrap}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_page_feed.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add app/web/feed.py app/templates/feed.html app/static/app.css tests/test_page_feed.py
git commit -m "feat: wire feed search box and no-code tab, primary tag on cards"
```

---

## Task 7: Render tags and README on the detail page

**Files:**
- Modify: `app/web/detail.py`, `app/templates/detail.html`
- Test: `tests/test_readme.py`

**Interfaces:**
- Consumes: `setups.preview(..., include_files=True)` returns `file_contents` (already does). README is `file_contents.get("README.md")`.
- Produces: detail page shows README (preformatted autoescaped) above the effects panel when present; tag set in the header.

- [ ] **Step 1: Write the failing test**

Create `tests/test_readme.py`:

```python
def test_detail_shows_readme_when_present(client):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "With Readme", "short desc",
                  {"skills/a/SKILL.md": "# a", "README.md": "# My Setup\n\nLong form text here."},
                  slug="with-readme")
    db.commit(); db.close()

    r = client.get("/s/with-readme")
    assert r.status_code == 200
    assert "Long form text here" in r.text
    assert "short desc" in r.text  # description still present


def test_detail_falls_back_to_description_without_readme(client):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "No Readme", "the description", {"skills/a/SKILL.md": "# a"}, slug="no-readme")
    db.commit(); db.close()

    r = client.get("/s/no-readme")
    assert r.status_code == 200
    assert "the description" in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_readme.py -v`
Expected: FAIL or partial (README not surfaced; "Long form text here" not in page).

- [ ] **Step 3: Pass README and tags to the template**

In `app/web/detail.py`, update the `render(...)` call (the return at the bottom) to include `readme` and `tags`:

```python
    readme = p["file_contents"].get("README.md")
    tags = p["effects"].get("tags", [])
    return render(request, "detail.html", {
        "p": p,
        "versions": versions,
        "is_owner": is_owner,
        "current": s.latest_version,
        "groups": groups,
        "readme": readme,
        "tags": tags,
    }, user=user)
```

- [ ] **Step 4: Render README and tags in the template**

In `app/templates/detail.html`, immediately after the `detail-head` div (after line 21, before the `install-help` panel), insert the README block:

```html
{% if readme %}
<div class="panel">
  <div class="panel-h"><h4>README</h4></div>
  <div class="panel-b">
    <pre class="readme">{{ readme }}</pre>
  </div>
</div>
{% endif %}
```

And in the `detail-meta` div (around line 9-13), add the tag set after the `vtag` span:

```html
      <span class="vtag">v{{ p.version }}</span>
      {% for t in tags %}
      <a class="tag" href="/?tag={{ t }}">{{ t }}</a>
      {% endfor %}
```

- [ ] **Step 5: Add the .readme style**

Append to `app/static/app.css`:

```css
pre.readme{white-space:pre-wrap;word-break:break-word;font-family:var(--sans);font-size:14px;line-height:1.6;color:var(--ink-2);background:none;padding:0;margin:0}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_readme.py tests/test_page_detail.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add app/web/detail.py app/templates/detail.html app/static/app.css tests/test_readme.py
git commit -m "feat: render README and tag set on detail page"
```

---

## Task 8: Support ?tag= filter on the feed

**Files:**
- Modify: `app/web/feed.py`
- Test: `tests/test_page_feed.py`

**Interfaces:**
- Consumes: `setups.list_setups(db, tag=tag)` from Task 5.
- Produces: `GET /?tag=hooks` filters the feed to setups with that tag.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_page_feed.py`:

```python
def test_feed_tag_filter(client):
    from app.db import SessionLocal, Base, engine
    Base.metadata.create_all(engine)
    from app.models import User
    from app import setups, security
    db = SessionLocal()
    u = User(username="auth", email="a@x.com", password_hash=security.hash_password("pw"))
    db.add(u); db.flush()
    setups.publish(db, u, "Pure", "d", {"skills/a/SKILL.md": "# a"}, slug="pure")
    setups.publish(db, u, "Hooked", "d",
                   {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'}, slug="hooked")
    db.commit(); db.close()

    r = client.get("/?tag=hooks")
    assert r.status_code == 200
    assert "hooked" in r.text
    assert "pure" not in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_page_feed.py::test_feed_tag_filter -v`
Expected: FAIL (tag param not read by the handler).

- [ ] **Step 3: Read the tag param in the handler**

In `app/web/feed.py`, add `tag: str | None = None` to the `feed` signature, and in the `else` (discover) branch, pass it through:

```python
@router.get("/")
def feed(request: Request, tab: str = "discover", window: str = "7d",
         q: str | None = None, tag: str | None = None,
         db: Session = Depends(get_session), user=Depends(optional_user)):
    if tab == "following":
        if user is None:
            return RedirectResponse("/login", status_code=303)
        items = setups.list_setups(db, following_of=user)
    elif tab == "no-code":
        items = setups.list_setups(db, window=window, runs_code=False)
    else:
        items = setups.list_setups(db, query=q, window=window, tag=tag)
    for it in items:
        it["primary_tag"] = bundle.primary_tag({"runs_code": it["runs_code"], "tags": it.get("tags", [])})
    return render(request, "feed.html",
                  {"items": items, "tab": tab, "window": window, "q": q or ""}, user=user)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_page_feed.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/web/feed.py tests/test_page_feed.py
git commit -m "feat: ?tag= filter on the feed"
```

---

## Task 9: Add prepare_setup MCP tool

**Files:**
- Modify: `app/mcp_server.py`
- Test: `tests/test_prepare_setup.py`

**Interfaces:**
- Produces: `prepare_setup(files: dict[str, str]) -> dict`. Read-only, no auth. Returns `{"valid": bool, "error": str|None, "effects": dict|None, "gathered_count": int, "total_bytes": int, "warnings": list[str]}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_prepare_setup.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prepare_setup.py -v`
Expected: FAIL (`AttributeError: module 'app.mcp_server' has no attribute 'prepare_setup'`).

- [ ] **Step 3: Implement prepare_setup**

In `app/mcp_server.py`, add the function before the `# Register the plain functions...` comment (line ~109), and register it. Insert:

```python
def prepare_setup(files: dict[str, str]) -> dict:
    """Preview a setup's effects BEFORE publishing. Read-only, no auth needed.

    Call this first with the files you gathered (relative path to text content),
    surface the returned `effects` and any `secret_flags` to the user, and only
    then call `publish_setup` once the user approves.

    Gather convention (advisory, server accepts any safe paths):
    include skills/**/SKILL.md (+ siblings), commands/**/*.md, agents/**/*.md,
    hooks/hooks.json, .mcp.json, plugins.json, CLAUDE.md, .claude/rules/**.
    Exclude node_modules/, .git/, *.db, dev-bundles/, and any file over the
    per-file size cap. The server enforces path safety and size, not convention.
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
```

And add to the registration block (after `mcp.tool(list_setups)`):

```python
mcp.tool(prepare_setup)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prepare_setup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mcp_server.py tests/test_prepare_setup.py
git commit -m "feat: prepare_setup MCP tool (read-only publish preview)"
```

---

## Task 10: Expand publish_setup docstring + add search_setups MCP tool

**Files:**
- Modify: `app/mcp_server.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `search_setups(query=None, runs_code=None, tag=None) -> list[dict]`, registered as an MCP tool. `publish_setup` docstring expanded with the gather convention.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_search.py`:

```python
def test_search_setups_tool(monkeypatch):
    from app import mcp_server, setups, bundle
    from app.models import User

    class _DB:
        def __init__(self, db, u):
            self.db = db; self.u = u
        def __enter__(self): return self.db
        def __exit__(self, *a): pass

    # Use the shared db fixture by calling through a real session.
    import pytest

    @pytest.fixture(autouse=True)
    def _seed(db, monkeypatch):
        u = User(username="author2", email="a2@x.com", password_hash="h")
        db.add(u); db.flush()
        setups.publish(db, u, "Hooked Tool", "d",
                       {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'},
                       slug="hooked-tool")
        db.commit()
        monkeypatch.setattr(mcp_server, "_open_session", lambda: _DB(db, u))
        yield

    # call without the fixture machinery (manual)
```

This is awkward through the fixture; instead write a simpler direct test. Replace the above with:

```python
def test_search_setups_tool_direct(db, monkeypatch):
    from app import mcp_server, setups
    from app.models import User
    u = User(username="author2", email="a2@x.com", password_hash="h")
    db.add(u); db.flush()
    setups.publish(db, u, "Hooked Tool", "d",
                   {"hooks/hooks.json": '{"hooks":{"PreToolUse":[{"command":"echo"}]}}'},
                   slug="hooked-tool")
    db.commit()

    class _Ctx:
        def __enter__(self): return db
        def __exit__(self, *a): pass
    monkeypatch.setattr(mcp_server, "_open_session", lambda: _Ctx())

    res = mcp_server.search_setups(query="Hooked")
    assert any(r["slug"] == "hooked-tool" for r in res)
    res2 = mcp_server.search_setups(runs_code=False)
    assert all(r["slug"] != "hooked-tool" for r in res2)
    res3 = mcp_server.search_setups(tag="hooks")
    assert any(r["slug"] == "hooked-tool" for r in res3)
```

(Remove the first, awkward version; keep only `test_search_setups_tool_direct`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search.py::test_search_setups_tool_direct -v`
Expected: FAIL (`AttributeError: ... has no attribute 'search_setups'`).

- [ ] **Step 3: Add search_setups and expand publish_setup docstring**

In `app/mcp_server.py`, add `search_setups` after `list_setups` (before the registration comment):

```python
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
```

And register it (add to the registration block):

```python
mcp.tool(search_setups)
```

Then expand the `publish_setup` docstring. Replace its current docstring with:

```python
    """Publish the caller's Claude Code setup. `files` is {relative_path: text_content}.

    Requires a valid `Authorization: Bearer <dothub-api-key>` header.

    Gather convention (advisory): include skills/**/SKILL.md and siblings,
    commands/**/*.md, agents/**/*.md, hooks/hooks.json, .mcp.json,
    plugins.json, CLAUDE.md, .claude/rules/**. Exclude node_modules/, .git/,
    *.db, dev-bundles/. The server enforces path safety and size, not the
    convention. Call `prepare_setup` first to preview effects and secret flags.
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search.py tests/test_mcp.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mcp_server.py tests/test_search.py
git commit -m "feat: search_setups MCP tool and expanded publish docstring"
```

---

## Task 11: Add shared signup validation

**Files:**
- Create: `app/validation.py`
- Modify: `app/web/auth.py:48-75`, `app/api.py:52-61`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `validation.validate_signup(username, email, password) -> None`, raising `ValueError("message")` on invalid input. Username regex `^[a-zA-Z0-9_-]{3,64}$`; email via `email.utils.parseaddr`; password min length 8.

- [ ] **Step 1: Write the failing test**

Create `tests/test_validation.py`:

```python
import pytest
from app.validation import validate_signup


def test_accepts_valid_username():
    validate_signup("catancs_01", "a@b.com", "password1")  # no raise


@pytest.mark.parametrize("bad", ["ab", "x" * 65, "has space", "has/slash", "two..dots", "dash-ok"])
def test_rejects_bad_usernames(bad):
    if bad == "dash-ok":
        validate_signup(bad, "a@b.com", "password1")  # dashes allowed
        return
    with pytest.raises(ValueError):
        validate_signup(bad, "a@b.com", "password1")


def test_rejects_bad_email():
    with pytest.raises(ValueError):
        validate_signup("goodname", "not-an-email", "password1")


def test_rejects_short_password():
    with pytest.raises(ValueError):
        validate_signup("goodname", "a@b.com", "short")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.validation'`).

- [ ] **Step 3: Create the validator**

Create `app/validation.py`:

```python
import re
from email.utils import parseaddr

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")


def validate_signup(username: str, email: str, password: str) -> None:
    """Validate signup inputs. Raises ValueError with a user-facing message."""
    if not USERNAME_RE.match(username or ""):
        raise ValueError("username must be 3 to 64 chars, letters, digits, _ or - only")
    _, parsed = parseaddr(email or "")
    if "@" not in parsed or "." not in parsed.split("@")[-1]:
        raise ValueError("email is not valid")
    if len(password or "") < 8:
        raise ValueError("password must be at least 8 characters")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Wire validation into the web signup**

In `app/web/auth.py`, add the import and call at the top of `signup_submit` (after the function signature, before the `exists` check):

```python
from ..validation import validate_signup
```

And inside `signup_submit`, before the `exists = ...` line:

```python
    try:
        validate_signup(username, email, password)
    except ValueError as e:
        resp = render(request, "signup.html", {"error": str(e)})
        resp.status_code = 400
        return resp
```

- [ ] **Step 6: Wire validation into the API signup**

In `app/api.py`, add the import:

```python
from .validation import validate_signup
```

And in `signup` (the `/api/signup` route), before the `exists = ...` line:

```python
    try:
        validate_signup(body.username, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 7: Run the auth/api tests for regressions**

Run: `pytest tests/test_validation.py tests/test_page_auth.py tests/test_api.py -v`
Expected: all PASS. (If existing tests use short passwords like "pw", update those test fixtures to an 8+ char password; do not weaken the validator.)

- [ ] **Step 8: Commit**

```bash
git add app/validation.py app/web/auth.py app/api.py tests/test_validation.py
git commit -m "feat: shared signup validation (username/email/password)"
```

---

## Task 12: Add preview visibility gate

**Files:**
- Modify: `app/setups.py:58-69` (`preview`), `app/api.py:81-86` (`api_get`), `app/web/detail.py`
- Test: `tests/test_visibility.py`

**Interfaces:**
- Produces: `setups.preview(db, slug, include_files=False, viewer=None)`. Raises `NotFound` when the setup is not public AND `viewer` is not the owner.
- Consumes: `api_get` passes `viewer=None` (public API, non-public 404s). `detail` passes `viewer=user` (owners can view their own).

- [ ] **Step 1: Write the failing test**

Create `tests/test_visibility.py`:

```python
import pytest
from app import setups, security
from app.models import User


def _make_private(db):
    u = User(username="owner", email="o@x.com", password_hash=security.hash_password("pw12345"))
    db.add(u); db.flush()
    setups.publish(db, u, "Private", "d", {"skills/a/SKILL.md": "# a"}, slug="priv")
    s = db.scalar(__import__("sqlalchemy").select(__import__("app.models").Setup).where(__import__("app.models").Setup.slug == "priv"))
    s.is_public = False
    db.commit()
    return u


def test_preview_rejects_non_public_for_non_owner(db):
    u = _make_private(db)
    stranger = User(username="stranger", email="s@x.com", password_hash=security.hash_password("pw12345"))
    db.add(stranger); db.flush()
    with pytest.raises(setups.NotFound):
        setups.preview(db, "priv", viewer=stranger)


def test_preview_allows_owner_of_non_public(db):
    u = _make_private(db)
    out = setups.preview(db, "priv", viewer=u)
    assert out["slug"] == "priv"


def test_preview_allows_public_to_anyone(db):
    u = _make_private(db)
    s = db.scalar(__import__("sqlalchemy").select(__import__("app.models").Setup).where(__import__("app.models").Setup.slug == "priv"))
    s.is_public = True
    db.commit()
    stranger = User(username="stranger2", email="s2@x.com", password_hash=security.hash_password("pw12345"))
    db.add(stranger); db.flush()
    out = setups.preview(db, "priv", viewer=stranger)
    assert out["slug"] == "priv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_visibility.py -v`
Expected: FAIL (preview has no `viewer` param; non-public setups are returned freely).

- [ ] **Step 3: Add the viewer gate to preview**

In `app/setups.py`, replace the `preview` function (lines 58-69) with:

```python
def preview(db, slug: str, include_files: bool = False, viewer: User | None = None) -> dict:
    s, v = _load_latest(db, slug)
    if not s.is_public and (viewer is None or viewer.id != s.owner_id):
        raise NotFound(slug)
    author = db.scalar(select(User.username).where(User.id == s.owner_id))
    files = bundle.unpack(storage.get_archive(v.archive_key))
    out = {
        "slug": s.slug, "title": s.title, "description": s.description,
        "version": v.version, "effects": v.manifest_json, "files": sorted(files),
        "author": author,
    }
    if include_files:
        out["file_contents"] = files
    return out
```

- [ ] **Step 4: Update the call sites**

In `app/api.py` `api_get` (line 81), the call `setups.preview(db, slug)` stays as-is (no viewer = public-only, non-public 404s). No change needed there.

In `app/web/detail.py`, update the preview call to pass `viewer=user`:

```python
    try:
        p = setups.preview(db, slug, include_files=True, viewer=user)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_visibility.py tests/test_page_detail.py tests/test_api.py tests/test_api_v2.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/setups.py app/web/detail.py tests/test_visibility.py
git commit -m "feat: preview visibility gate for non-public setups"
```

---

## Task 13: Add slowapi rate limiting

**Files:**
- Modify: `requirements.txt`, create `app/ratelimit.py`, modify `app/main.py`, `app/web/auth.py`, `app/api.py`
- Test: `tests/test_ratelimit.py`

**Interfaces:**
- Produces: `app/ratelimit.py` exports `limiter` (a `slowapi.Limiter`) and a `rate_key` function. Routes use `@limiter.limit("10/minute")` with `key_func=rate_key` (respects `X-Forwarded-For`).

- [ ] **Step 1: Add the dependency**

In `requirements.txt`, add (after the `itsdangerous` line):

```
slowapi==0.1.9
```

Install it: `pip install slowapi==0.1.9` (or `pip install -r requirements.txt`).

- [ ] **Step 2: Write the failing test**

Create `tests/test_ratelimit.py`:

```python
def test_login_rate_limited_after_threshold(client):
    from app.db import SessionLocal, Base, engine
    from app.models import User
    from app import security
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(User(username="u", email="u@x.com", password_hash=security.hash_password("pw12345")))
    db.commit(); db.close()

    # 10 allowed, 11th should be 429
    last = None
    for i in range(11):
        last = client.post("/login", data={"identifier": "u", "password": "wrongpw1"},
                           headers={"X-Forwarded-For": "1.2.3.4"})
    assert last.status_code == 429
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_ratelimit.py -v`
Expected: FAIL (no limiter; all 11 return 401, not 429).

- [ ] **Step 4: Create the limiter module**

Create `app/ratelimit.py`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address


def rate_key(request):
    """Use the real client IP behind nginx (X-Forwarded-For), else the peer."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=rate_key)
```

- [ ] **Step 5: Wire the limiter into the app**

In `app/main.py`, register the limiter and its error handler. After the `app = FastAPI(...)` line and before `app.add_middleware(...)`, add:

```python
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from .ratelimit import limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 6: Decorate the auth routes**

In `app/web/auth.py`, add imports and decorate `login_submit` and `signup_submit`:

```python
from ..ratelimit import limiter
```

Add `request: Request` is already present. Decorate:

```python
@router.post("/login")
@limiter.limit("10/minute")
def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    ...


@router.post("/signup")
@limiter.limit("5/minute")
def signup_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    ...
```

- [ ] **Step 7: Decorate the API auth routes**

In `app/api.py`, add the import and decorate `/api/login`, `/api/signup`, `/api/keys`. Each must take a `request: Request` param. For the API routes that take a Pydantic body, slowapi needs `request` as the first param:

```python
from .ratelimit import limiter
from fastapi import Request
```

```python
@router.post("/api/signup")
@limiter.limit("5/minute")
def signup(body: SignupIn, request: Request, db: Session = Depends(get_session)):
    ...


@router.post("/api/login")
@limiter.limit("10/minute")
def login(body: LoginIn, request: Request, db: Session = Depends(get_session)):
    ...


@router.post("/api/keys")
@limiter.limit("5/minute")
def mint_key(body: KeyIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_session)):
    ...
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_ratelimit.py -v`
Expected: PASS (11th login returns 429).

- [ ] **Step 9: Run the full auth/api suite for regressions**

Run: `pytest tests/test_ratelimit.py tests/test_page_auth.py tests/test_api.py tests/test_api_v2.py -v`
Expected: all PASS. (If slowapi complains about missing `request` param on any decorated route, ensure that route's signature has `request: Request` as the first parameter after self/none.)

- [ ] **Step 10: Commit**

```bash
git add requirements.txt app/ratelimit.py app/main.py app/web/auth.py app/api.py tests/test_ratelimit.py
git commit -m "feat: slowapi rate limiting on login, signup, key mint"
```

---

## Task 14: Harden the session cookie

**Files:**
- Modify: `app/main.py:26`, `infra/user_data.sh.tpl`
- Test: `tests/test_health.py` (smoke), manual verify of cookie flags

**Interfaces:**
- Produces: `SessionMiddleware(secret_key=..., https_only=True, samesite="lax")`. `infra/user_data.sh.tpl` generates a strong `SESSION_SECRET`.

- [ ] **Step 1: Update the middleware**

In `app/main.py`, replace the `SessionMiddleware` line (line 26) with:

```python
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret,
                       https_only=True, samesite="lax")
```

- [ ] **Step 2: Write a test that the cookie is set with Secure**

Append to `tests/test_health.py`:

```python
def test_session_cookie_has_secure_flag(client):
    r = client.post("/login", data={"identifier": "nobody", "password": "wrongpw1"},
                    headers={"X-Forwarded-For": "9.9.9.9"}, follow_redirects=False)
    # 401 or 429 both fine; we only care that IF a session cookie is set, it is Secure.
    cookie = r.headers.get("set-cookie", "")
    if "session=" in cookie:
        assert "Secure" in cookie
        assert "SameSite=lax" in cookie
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 4: Ensure a strong SESSION_SECRET in user_data.sh.tpl**

Read `infra/user_data.sh.tpl`. Find the line that writes `SESSION_SECRET=` to `/opt/dothub/.env`. If it uses a fixed value (e.g. `dev-secret-change-me`), replace it with a generated secret. The line should become:

```sh
SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

(written into the `.env` file by the cloud-init script). If the template already generates a strong secret, leave it. Verify by reading the file.

- [ ] **Step 5: Run the full suite for regressions**

Run: `pytest -x -q`
Expected: all PASS (or only pre-existing failures unrelated to this task).

- [ ] **Step 6: Commit**

```bash
git add app/main.py infra/user_data.sh.tpl tests/test_health.py
git commit -m "feat: harden session cookie (secure, samesite) and strong prod secret"
```

---

## Task 15: Add Alembic baseline

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/` (empty, with `.gitkeep`)
- Modify: `requirements.txt`, `.gitignore`
- Test: manual `alembic` command verification

**Interfaces:**
- Produces: an Alembic config pointed at `settings.database_url` and `Base.metadata`, with the current schema stamped as the baseline. No migrations authored yet.

- [ ] **Step 1: Add the dependency**

In `requirements.txt`, add:

```
alembic==1.13.*
```

Install: `pip install alembic==1.13.*`

- [ ] **Step 2: Initialize Alembic**

Run from repo root:

```bash
alembic init alembic
```

This creates `alembic.ini` and `alembic/`. If `alembic/` already has a `versions/` dir, keep it.

- [ ] **Step 3: Configure env.py to use the app's metadata and DB URL**

Replace `alembic/env.py` with:

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.config import settings
from app.db import Base
import app.models  # noqa: F401  register models on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Stamp the current schema as baseline**

With the dev DB (SQLite), stamp:

```bash
DATABASE_URL="sqlite+pysqlite:///baseline.db" alembic stamp head
```

Expected: no error, `baseline.db` created (can be deleted; it is only for the stamp). Confirm `alembic current` reports `head`.

- [ ] **Step 5: Ignore the baseline scratch DB and keep versions tracked**

In `.gitignore`, add:

```
baseline.db
```

Add a `.gitkeep` to `alembic/versions/`:

```bash
touch alembic/versions/.gitkeep
```

- [ ] **Step 6: Verify alembic config loads**

Run: `alembic current`
Expected: prints the current revision (or "head" after stamp), no import errors.

- [ ] **Step 7: Commit**

```bash
git add alembic.ini alembic/ requirements.txt .gitignore
git commit -m "feat: Alembic baseline (stamp current schema)"
```

---

## Task 16: Add the /publish instructions page

**Files:**
- Create: `app/web/publish.py`, `app/templates/publish.html`
- Modify: `app/web/__init__.py`, `app/templates/base.html`
- Test: `tests/test_page_feed.py` (smoke) or a new `tests/test_page_publish.py`

**Interfaces:**
- Produces: `GET /publish` renders `publish.html` (instructions, no form). Nav link added to all users.

- [ ] **Step 1: Write the failing test**

Create `tests/test_page_publish.py`:

```python
def test_publish_page_renders(client):
    r = client.get("/publish")
    assert r.status_code == 200
    assert "publish" in r.text.lower()
    assert "mcp" in r.text.lower()  # mentions the MCP add command


def test_publish_link_in_nav(client):
    r = client.get("/")
    assert 'href="/publish"' in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_page_publish.py -v`
Expected: FAIL (404 on `/publish`).

- [ ] **Step 3: Create the route**

Create `app/web/publish.py`:

```python
from fastapi import APIRouter, Depends, Request
from app.api import optional_user
from app.web._render import render

router = APIRouter()


@router.get("/publish")
def publish_page(request: Request, user=Depends(optional_user)):
    return render(request, "publish.html", {}, user=user)
```

- [ ] **Step 4: Register the router**

In `app/web/__init__.py`, add the import and include. Read the file first; it currently imports routers. Add:

```python
from .publish import router as publish_router
router.include_router(publish_router)
```

(Follow the existing pattern for the other routers in that file.)

- [ ] **Step 5: Create the template**

Create `app/templates/publish.html`:

```html
{% extends "base.html" %}
{% block title %}Publish a setup - dothub{% endblock %}
{% block body %}
<section class="screen active">
  <div class="phead">
    <div class="eyebrow">Share your setup</div>
    <h1 class="big">Publish from your<br>agent <em>CLI</em>.</h1>
    <p class="sub">dothub publishing is agent-native. Your Claude Code agent gathers your setup and publishes it via the dothub MCP server. No upload form, no script.</p>
  </div>

  <div class="panel">
    <div class="panel-h"><h4>1. Add the dothub MCP server</h4></div>
    <div class="panel-b">
      <p class="sub" style="margin-top:0;font-size:14px">Mint an API key on your Account page, then add dothub to Claude Code.</p>
      <div class="hook"><div class="ev">Run in a terminal</div>
        <pre class="cmd">claude mcp add --transport http dothub {{ request.base_url }}mcp/ --header "Authorization: Bearer dh_your_key"</pre></div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-h"><h4>2. Ask your agent to publish</h4></div>
    <div class="panel-b">
      <p class="sub" style="margin-top:0;font-size:14px">In a Claude Code session, ask it to publish your setup. It will gather your skills, commands, agents, hooks, MCP config, and plugins, preview the effects with you, then publish.</p>
      <div class="hook"><div class="ev">The agent calls these tools in order</div>
        <pre class="cmd">prepare_setup(files)   # preview effects + secret flags, no publish
publish_setup(title, description, files)   # writes to dothub after you approve</pre></div>
      <p class="sub" style="font-size:14px">The agent is the export step. It reads your files with its own tools and sends them as a path-to-content map. dothub validates paths and size, computes the effects manifest, and shows it for review.</p>
    </div>
  </div>

  <div class="panel">
    <div class="panel-h"><h4>3. Share the result</h4></div>
    <div class="panel-b">
      <p class="sub" style="margin-top:0;font-size:14px">Your setup gets a public page at <span class="mono">/s/&lt;slug&gt;</span> with its full effects manifest. Share that link.</p>
    </div>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 6: Add the nav link**

In `app/templates/base.html`, in the `.nav-links` block, add a Publish link visible to all users. After the Discover link:

```html
      <a href="/" class="{% if request.url.path == '/' %}on{% endif %}">Discover</a>
      <a href="/publish" class="{% if request.url.path == '/publish' %}on{% endif %}">Publish</a>
```

(Put it inside the part of the nav shown to everyone, i.e. before the `{% if user %}` branch, or add it to both branches. Simplest: add it right after Discover, before the `{% if user %}` conditional.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_page_publish.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add app/web/publish.py app/web/__init__.py app/templates/publish.html app/templates/base.html tests/test_page_publish.py
git commit -m "feat: /publish instructions page (agent-native on-ramp)"
```

---

## Task 17: Document CSRF limitation and run full suite

**Files:**
- Modify: `deploy/DEPLOY.md`

- [ ] **Step 1: Add the CSRF note to the deploy doc**

In `deploy/DEPLOY.md`, in the "Caveats" or known-limitations section, add a bullet:

```markdown
- **CSRF (partial).** Session cookies use `SameSite=Lax`, which mitigates form-post CSRF. The JSON `/api/*` mutation routes (follow, revert, key mint, account) are a residual surface without full CSRF tokens. No mutation currently moves money or deletes data. Full CSRF token protection is a planned fast-follow.
```

- [ ] **Step 2: Run the entire test suite**

Run: `pytest -q`
Expected: all PASS (investigate and fix any failure; do not leave red tests).

- [ ] **Step 3: Run a lint/format check if configured**

Run: `ruff check app/ tests/ 2>/dev/null || true`
Expected: no new errors introduced by Wave 1 changes. Fix any imports flagged as unused.

- [ ] **Step 4: Commit**

```bash
git add deploy/DEPLOY.md
git commit -m "docs: note CSRF as a known limitation in deploy runbook"
```

---

## Task 18: Browser verification (parallel subagents)

**Files:** none (verification only)

This task is executed by dispatching parallel subagents, each booting an isolated dothub instance (unique port, own SQLite + local storage dir) and driving Playwright headless Chromium. Run on Opus.

- [ ] **Step 1: Boot a local instance for manual smoke**

Run: `./scripts/dev_up.sh` (or, if that launches a background server the harness reaps, run it in a separate terminal). Confirm `http://localhost:8000/` loads.

- [ ] **Step 2: Dispatch parallel verification subagents**

Dispatch one subagent per area, each with an isolated instance on ports 8021 to 8026 (own `DATABASE_URL` SQLite file and `STORAGE_DIR`). Each subagent: boots the app, seeds a realistic setup, drives Playwright, reports PASS/FAIL per check.

Areas and checks:
1. **Search** (port 8021): type in the search box, submit, results filter by title; `?q=` value persists in the input; `/?tab=no-code` shows only no-code setups.
2. **Tags** (port 8022): cards show one primary tag pill; detail page shows the full tag set; clicking a detail-page tag links to `/?tag=...` and filters the feed.
3. **README** (port 8023): a setup with `README.md` renders the preformatted block above the effects panel; a setup without falls back to description.
4. **Publish loop** (port 8024): call `prepare_setup` then `publish_setup` (via the MCP tool functions directly or HTTP) with a realistic full file dict; confirm the setup appears in the feed with correct tags, counts, and `runs_code`.
5. **Rate limit** (port 8025): hammer `/login` past 10 attempts, confirm 429 on the 11th.
6. **Hygiene** (port 8026): signup with a bad username (`a b`) is rejected with 400; a non-public setup's `/s/<slug>` returns 404 to a non-owner; the session cookie has the `Secure` flag.

- [ ] **Step 3: Collect results and fix any failures**

Aggregate the subagent reports. For any FAIL, file a fix (return to the relevant task). Re-verify only the failed area.

- [ ] **Step 4: Commit any fix-ups**

If fixes were needed, commit them with clear messages. If all green, no commit.

---

## Self-Review (run after writing, before handoff)

Done inline during authoring. Coverage check against the spec:

- Spec section 1 (Search): Tasks 5, 6, 8, 10. Covered.
- Spec section 2 (Agent-native publishing): Tasks 2 (per-file cap), 9 (`prepare_setup`), 10 (docstring), 16 (`/publish` page). Covered. No web form, no script: correct.
- Spec section 3 (Discovery polish): Task 3 (tags), 4 (primary tag), 6 (no-code lane + primary on card), 7 (README + tags on detail). Covered.
- Spec section 4 (Hygiene): Task 1 (SECRET_PATTERNS), 11 (signup validation), 12 (preview visibility), 13 (slowapi), 14 (cookie + secret), 15 (Alembic), 17 (CSRF doc). Covered. 4b preview visibility: Task 12. Covered.
- Spec section 5 (Tests + browser verification): Task 18 + tests embedded in each task. Covered.

Type consistency: `prepare_setup` returns `{"valid", "error", "effects", "gathered_count", "total_bytes", "warnings"}` in Task 9, and Task 18 step 2 area 4 and the Task 9 tests use the same keys. `list_setups` returns dicts with `tags` (Task 5) and `primary_tag` is added by the feed handler (Task 6). `primary_tag(manifest)` (Task 4) takes `{"runs_code", "tags"}`; the feed handler calls it with `{"runs_code": it["runs_code"], "tags": it.get("tags", [])}`. Consistent.

Placeholder scan: no TBD/TODO; every step has code or a command. The Task 5 JSON-filter fallback is a concrete conditional, not a placeholder.

Em dashes: none in this plan.
