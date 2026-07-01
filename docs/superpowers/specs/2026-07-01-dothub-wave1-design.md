# dothub Wave 1 design

Date: 2026-07-01
Status: approved (design review), pending implementation plan
Scope: pre-deploy feature and hygiene batch. Wave 2 (moat deepening) is separate.

## Context

dothub is a social hub for sharing whole Claude Code setups (skills, commands, agents, hooks, MCP config, plugins) as versioned bundles. A single FastAPI app serves both a server-rendered web feed and a remote MCP server, so an agent can publish and pull setups itself. The effects manifest, computed server-side at publish time, is the core trust primitive: it enumerates the exact hook commands (verbatim), MCP servers, plugins, `runs_code`, secret flags, and counts, surfaced for review before install.

A grounded ideation pass against the real code surfaced nine improvement concepts plus a pre-deploy hygiene list. This spec covers Wave 1: the subset that should land before the AWS deploy because it fixes broken funnels, makes the feed shoppable, and closes security gaps that would be unsafe on a public-facing instance. Wave 2 (manifest diff, severity/network detection, agent pull receipt, `diff_installed`, detected prerequisites) is deferred to a post-deploy fast-follow and depends on Wave 1's manifest work.

## Goals

- Make the agent-driven publish loop reliable and consistent: an agent can discover a full setup and publish it without fumbling, with a preview-before-publish safety gate.
- Fix the broken web search funnel (decorative input that does nothing) and add a publish on-ramp page that points users at the agent-driven flow.
- Make the feed shoppable by the signals dothub already computes (`runs_code`, derived tags).
- Close pre-deploy security gaps: session cookie flags, preview visibility leak, signup validation, rate limiting, shallow secret detection, missing migration path.
- Enforce all of the above with tests and isolated-instance browser verification.

## Non-goals

- Web upload form for publishing. Publishing stays agent/MCP-native by deliberate product decision.
- Author-curated tags. Tags are auto-derived from the manifest only.
- Rendered (HTML) markdown for README. v1 renders README as preformatted autoescaped text.
- Full CSRF token protection on `/api/*` mutation routes. Deferred to a fast-follow; `SameSite=Lax` plus the no-money-no-delete mutation surface is the interim posture, documented as a known limitation.
- Zip upload support. tar.gz only, matching the storage format.
- Verified-author provenance (#3) and collections (#10). Both are L-effort and out of Wave 1.

## Architecture

Wave 1 touches four layers, all funneling through the existing `setups` and `bundle` cores so safety checks stay in one place.

```
bundle.py            effects_manifest() + tags, validate_files (per-file cap), SECRET_PATTERNS
        |
setups.py            list_setups (q/runs_code/tag filters), publish, preview (visibility gate), install
        |
   +----+----+-------------------+
   |         |                   |
api.py     mcp_server.py        web/*.py
/api/*     publish_setup        /  (feed: q, tab=no-code)
           prepare_setup (new)  /s/<slug> (tags, README)
           search_setups (new)  /publish (instructions page)
```

The same `setups.publish` core already backs the API and MCP fronts. Wave 1 adds two MCP tools (`prepare_setup`, `search_setups`) as thin front-ends and adds filters to `setups.list_setups` consumed by both the web feed and the new MCP search tool. No new core publishing path is introduced.

## Component design

### 1. Search (broken funnel fix)

**Problem.** `app/templates/feed.html` line 25 has a `<label class="search"><input placeholder="...">` with no `name` and no `action`. Typing does nothing. On the agent side, `list_setups` accepts `query` but no MCP tool exposes filtered search.

**Web.** Wrap the input in `<form method="get" action="/">`; give the input `name="q"`. In `app/web/feed.py`, add `q: str | None = None` to the `feed` handler and pass it to `setups.list_setups(db, query=q, window=window)`. Persist the submitted value into the input's `value` attribute so it survives the round trip. The `q` parameter rides alongside the existing `tab` and `window` params; the pill hrefs are left as-is (additive) so `q` does not collide with tab/window state.

**`setups.list_setups` extension.** Add optional filters: `runs_code: bool | None = None`, `tag: str | None = None`. Push both into the SQL `where` clause (not a Python post-filter) so they respect the `limit(50)` ordering. `runs_code` filters on the manifest JSON; `tag` filters on tag membership in the manifest's `tags` list. Implementation uses SQLAlchemy 2.0 JSON path access that works on both SQLite and Postgres; if the exact incantation differs between backends, fall back to `func.json_extract` (SQLite) and a `->>` cast (Postgres) gated on backend detection. The concrete expression is verified during implementation with a passing test on both backends.

**MCP `search_setups`.** New module-level function in `app/mcp_server.py`, registered via `mcp.tool(search_setups)` without rebinding the name (matching the existing pattern at lines 111-114). Signature: `search_setups(query: str | None = None, runs_code: bool | None = None, tag: str | None = None) -> list[dict]`. Delegates to `setups.list_setups`. The docstring states that `query` matches setup titles, `runs_code` filters on whether the setup runs code, and `tag` filters on an auto-derived tag.

**v1 scope.** Search matches title only. Author/slug matching is a later enhancement.

### 2. Agent-native publishing (reliability of the gather-publish loop)

**Decision.** Publishing stays agent/MCP-native. No web upload form, no export script, no CLI tool. The agent is the export mechanism: it reads files with its filesystem tools and sends `{path: content}` to `publish_setup`. The server does not enforce a root allowlist (advisory convention only); safety is enforced via traversal/size validation and the effects manifest, not path restrictions. Rationale: a hook that runs `bin/lint.sh` shows up verbatim in the manifest regardless of where `lint.sh` lives, so the user still sees what it does. An allowlist would restrict without adding safety.

**`prepare_setup` MCP tool (new).** Read-only, no auth required. Signature: `prepare_setup(files: dict[str, str]) -> dict`. Runs `bundle.validate_files` and `bundle.effects_manifest` and returns:
- `valid: bool`. If false, `error` holds the exact `BundleError` message.
- `effects`: the full manifest (hooks, mcp_servers, plugins, counts, runs_code, secret_flags, tags).
- `gathered_count`: number of files.
- `total_bytes`: summed content size.
- `warnings`: best-effort consistency hints. Examples: "no SKILL.md found under skills/", "hooks.json present but empty", "`.mcp.json` references MCP server 'foo' but no matching plugin/skill". Warnings are advisory and never block publish.

The intended loop: agent gathers files, calls `prepare_setup`, surfaces `effects` and any `secret_flags` to the user for approval, then calls `publish_setup`. This makes publish a two-step, reviewable act and lets the agent see secret leaks before they ship.

**`publish_setup` docstring contract.** The existing `publish_setup` docstring is expanded to state the default gather convention explicitly, because MCP tool descriptions are the agent's instruction manual:
- Include by default: `skills/**/SKILL.md` and sibling files in each skill dir, `commands/**/*.md`, `agents/**/*.md`, `hooks/hooks.json`, `.mcp.json`, `plugins.json`, `CLAUDE.md`, `.claude/rules/**`.
- Exclude by default: `node_modules/`, `.git/`, `*.db`, `dev-bundles/`, and any single file over the per-file size cap.
- The convention is advisory; the server accepts any valid `{path: content}`.

**Per-file size cap.** `bundle.validate_files` currently enforces only a total `MAX_BUNDLE_BYTES`. Add a per-file max (default 1 MiB, configurable via `MAX_FILE_BYTES` env, falling back to a sensible fraction of the bundle cap) so a single runaway file fails loudly with a clear message instead of the whole bundle failing opaquely. The cap is checked inside `validate_files` alongside the existing traversal and total-size checks.

**`/publish` instructions page.** A new `GET /publish` route renders `publish.html`, login-optional. It is instructions, not a form: "ask your agent to publish your setup" with the MCP add command (`claude mcp add --transport http dothub <base_url>/mcp/ --header "Authorization: Bearer dh_..."`) and a note that the agent should call `prepare_setup` first to review effects. A nav link to `/publish` is added to `base.html`, shown to all users (the on-ramp is relevant whether or not you are logged in).

**No changes** to the existing `/api/setups` POST or `publish_setup` signatures beyond the docstring. The JSON `{files: {...}}` shape is unchanged.

### 3. Discovery polish

**3a. No-code feed lane.** `feed.html` gains a third pill alongside Discover and Following: No-code. The `feed` handler gains a `tab == "no-code"` branch calling `setups.list_setups(db, window=window, runs_code=False)`. Reuses the `runs_code` filter added in section 1. The card's existing "no code" chip provides consistent visual language.

**3b. Auto-derived tags.** In `bundle.effects_manifest`, compute a `tags` list from the bundle:
- `"hooks"` if any hooks present.
- `"mcp:<name>"` for each MCP server name.
- `"plugins"` if any plugins present.
- `"skills-only"` if `runs_code` is false.
- `"commands"` if `counts.commands > 0`.
- `"agents"` if `counts.agents > 0`.

Tags land in `manifest_json` (no schema change). Authors cannot override tags. Tags render as small pills: on the feed card, the **primary tag only**; on the detail page header, the full tag set.

**Primary-tag precedence** (used for the card): prefer `skills-only` when `runs_code` is false; otherwise prefer `hooks`, then `mcp:<name>` (first MCP server), then `plugins`, then the first non-zero count tag (`commands`, then `agents`). If none apply, no pill is shown.

**`?tag=` feed filter.** `setups.list_setups` gains the `tag` param (section 1). Clicking a tag on the detail page links to `/?tag=<tag>`. Tag pills on the card are not clickable in v1 (the primary tag is a label, not a link); only the detail-page tag set links to the filtered feed. This keeps the card quiet while still making tags navigable from the detail page.

**3c. README rendering.** If the bundle contains `README.md` at root, render it on `/s/<slug>` above the "What this setup does" panel. Falls back to `Setup.description` if absent. v1 renders README as **preformatted autoescaped text** (a `<pre>` with the raw markdown source), consistent with the existing file-content browser which already autoescapes. No markdown library, no HTML-injection surface. Rendered markdown is a future one-library swap, scoped to a later task.

### 4. Pre-deploy hygiene

**4a. Session cookie + secret.** `app/main.py` line 26 adds `SessionMiddleware` with only `secret_key`. Set `https_only=True` and `samesite="lax"`. Confirm `infra/user_data.sh.tpl` injects a strong generated `SESSION_SECRET`; if it currently uses the `dev-secret-change-me` default, wire a generated secret (e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"` at cloud-init time) into the `.env`. Verify during implementation by reading the template.

**4b. Preview visibility gate.** `app/api.py` line 81 (`api_get`) calls `setups.preview` for any slug with no `is_public` check; `setups.preview` does not filter. Add an optional `viewer: User | None` param to `setups.preview`; reject non-public setups unless `viewer` is the owner. Update both call sites: the public API (no viewer, so non-public 404s) and the detail page (viewer = current user, so owners can view their own non-public setups).

**4c. Signup validation.** Add a shared validator (e.g. `app/security.py` or a new `app/validation.py`) used by both `app/web/auth.py` signup and `app/api.py` `/api/signup`:
- Username regex `^[a-zA-Z0-9_-]{3,64}$`. Usernames become URL paths (`/u/{username}`), so this rejects `/`, spaces, `..`.
- Email format check (stdlib `email` parser or a simple regex).
- Password min length 8.

On invalid input, the web route re-renders with an error; the API route returns 400 with a message.

**4d. Rate limiting (`slowapi`).** Add the `slowapi` dependency. Wire a `Limiter` in `app/main.py` with `key_func` respecting `X-Forwarded-For` (critical behind nginx, where `request.client.host` is always `127.0.0.1`). Apply per-route limits via decorator:
- `/login`, `/api/login`: 10/minute per IP.
- `/signup`, `/api/signup`: 5/minute per IP.
- `/api/keys`: 5/minute per IP.

In-memory backend (resets on restart), fine for single-instance deploy. Returns 429 with `Retry-After`.

**4e. `SECRET_PATTERNS` extension.** `app/bundle.py` line 13 currently matches `sk-...`, AWS `AKIA`, PEM private keys. Add: GitHub PATs (`ghp_`, `gho_`, `ghs_`, `ghr_`), Slack (`xoxb-`, `xoxp-`), Anthropic (`sk-ant-`), Google API (`AIza`). Patterns are substring/regex matches, framed in the UI as best-effort signals (matching the existing secret-flag copy).

**4f. Alembic baseline.** `app/db.py` uses `Base.metadata.create_all`. Adopt Alembic: `alembic init`, configure `alembic.ini` and `env.py` to use `settings.database_url` and `Base.metadata`, then `alembic stamp head` against the current schema as the baseline. No migrations are authored in Wave 1; the baseline exists so Wave 2's `changelog` column and any future model change migrate cleanly on the prod RDS. `create_all` remains for dev/test first-boot until the first real migration is added.

**4g. CSRF (deferred).** Full CSRF tokens on `/api/*` mutation routes are deferred. `SameSite=Lax` (set in 4a) mitigates form-post CSRF; the JSON `fetch` mutation routes remain a residual surface. The deploy doc is updated to list CSRF as a known limitation. Rationale: no mutation currently moves money or deletes data, and full CSRF is a cross-cutting change touching every form and `fetch` call, better scoped to a dedicated fast-follow than rushed pre-launch.

## Data flow

**Publish (agent).** Agent gathers files per the docstring convention. Calls `prepare_setup(files)` (no auth). Server validates, computes manifest + tags, returns effects/flags/warnings. Agent surfaces to user. User approves. Agent calls `publish_setup(title, description, files, slug)` (auth required). Server re-validates, re-computes manifest, packs tar.gz, stores, commits `Setup` + `SetupVersion`, returns `{slug, version, url}`. Setup appears in feed with tags and `runs_code` chip.

**Search (web).** User types in the box, form submits `GET /?q=...`. `feed` handler passes `q` to `list_setups`. Results render with primary-tag pills and runs-code chips.

**Search (agent).** Agent calls `search_setups(query=..., runs_code=False, tag="hooks")`. Returns the same list shape as `list_setups`.

**Browse no-code.** User clicks the No-code pill. `feed` handler calls `list_setups(runs_code=False, window=window)`. Only `runs_code == false` setups render.

**View detail.** `GET /s/<slug>`. `setups.preview(slug, viewer=user)`. Page renders README (if present) or description, then the effects panel with tags in the header, then contents, then version history.

## Error handling

- `BundleError` from `validate_files` (traversal, total size, per-file size, too many files): surfaced as `valid: false` with the message in `prepare_setup`; raised as 400 in `/api/setups` and `publish_setup`.
- `OwnershipError` (slug owned by another user): 403 in API; `PermissionError` in MCP.
- `NotFound` (slug missing, or non-public setup viewed by non-owner): 404 in API; raises in MCP.
- `prepare_setup` never raises on invalid bundles; it returns `valid: false` so the agent can report the problem rather than the call failing opaquely.
- Rate limit: 429 with `Retry-After`, before the handler body runs.
- Signup validation: 400 (API) or re-render with error (web).

## Testing

**Unit tests.**
- `bundle.py`: tags computed correctly per manifest shape; `runs_code == false` yields `skills-only` tag and no `hooks`/`mcp`/`plugins` tags; per-file cap rejects an oversized single file with a clear message; extended `SECRET_PATTERNS` catch GitHub PAT, Slack, Anthropic, Google tokens (and existing `sk-`/AKIA/PEM still match).
- `setups.list_setups`: `q`, `runs_code`, and `tag` filters each return the correct subset and respect `limit`. Tested on SQLite (dev) and, where feasible, the same assertions against Postgres semantics for the JSON-path filter.
- `setups.publish` + `prepare_setup`: a realistic full-setup fixture (skills + commands + hooks + mcp + plugins + CLAUDE.md) round-trips with expected counts, tags, and flags; a traversal fixture is rejected; a leaked-secret fixture is flagged in `prepare_setup` before publish.
- `setups.preview`: non-public setup rejected for non-owner, allowed for owner.
- Signup validator: accepts `catancs_01`, rejects `../`, spaces, sub-3-char, and bad email; enforces password min length.
- Primary-tag precedence: each precedence case returns the expected single tag.

**MCP tool tests.** `search_setups` and `prepare_setup` called directly (plain functions, per the existing `mcp_server.py` pattern) with monkeypatched `_open_session`/`_bearer_key`. Assert return shapes. No live HTTP.

**Route tests.** `/?q=...` and `/?tab=no-code` return filtered results; `/publish` renders; `/login` returns 429 after the rate limit is exceeded.

**Browser verification (parallel subagents).** Each subagent boots its own isolated dothub instance (unique port, own SQLite file and local storage dir) and drives Playwright headless Chromium:
- Search: type, submit, results filter; `?q=` persists in the input.
- No-code lane: pill shows only `runs_code == false` setups; chips match.
- Tags: cards show one primary pill; detail page shows the full set; detail-page tag links filter the feed.
- README: a setup with `README.md` renders the preformatted block above the effects panel; one without falls back to description.
- Rate limit: hammer `/login` past the limit, confirm 429.
- Agent publish loop: call `prepare_setup` then `publish_setup` with a realistic file dict; confirm the setup appears in the feed with correct tags and effects.

The realistic-setup fixture is the executable guarantee that "agents can discover the full setup and publish it." If the gather contract breaks, this test fails before deploy.

## Migration and deploy notes

- `slowapi` is the one new runtime dependency. Add to `pyproject.toml`/requirements; the `user_data.sh.tpl` venv install picks it up.
- Alembic is a new dev dependency for migrations. The `alembic/` directory and `alembic.ini` are committed; the baseline is stamped on first prod boot (or `create_all` runs for dev, with stamp applied separately).
- No schema changes in Wave 1 (tags live in `manifest_json`, which is already JSON). The first real migration is Wave 2's `changelog` column.
- `SESSION_SECRET` generation and cookie flags must be verified in `user_data.sh.tpl` before the certbot/TLS step.
- CSRF is documented as a known limitation in `deploy/DEPLOY.md`.

## Out of scope (Wave 2 and beyond)

- Manifest diff between versions (#1).
- Effect severity + network-egress detection (#2).
- Agent pull receipt (#5).
- `diff_installed` MCP tool (#7, depends on #1).
- Detected prerequisites in the manifest (#8).
- Verified-author provenance (#3), collections (#10), draft/unlisted setups (#13), install-count dedup (#15), version changelogs (#16), real `/healthz` (#17), structured request logging (#18).
- Full CSRF protection (#4g fast-follow).
