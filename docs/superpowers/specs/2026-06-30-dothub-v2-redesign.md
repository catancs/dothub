# dothub v2: redesign and social features, design spec

Status: approved for planning (2026-06-30)
Supersedes the UI and feature surface of `2026-06-30-agent-setup-hub-design.md`. The v1 core (accounts, API keys, publish, S3 storage, remote MCP server, effects manifest, transparency-first install) stands and is reused. This document specifies what changes and what is added.

Visual source of truth: `docs/dothub-redesign-mockup.html` (self contained, openable from disk). The implementation reproduces that mockup's aesthetic exactly.

## 1. Goal

Turn dothub from a minimal feed into a complete, beautifully designed environment for sharing whole Claude Code setups. Add a bespoke design system, a logged in app shell with sections (Discover, Following, Setup detail, History, Account, Profile), the ability to read every file in a setup before installing, plugin capture, follow relationships, trending discovery, pull history, and in app revert of your own setups.

## 2. Scope

In scope:
1. A bespoke design system (the locked aesthetic below) applied across all pages.
2. App shell with server rendered pages and a top nav, gated by session auth.
3. Web auth pages (login, signup, logout). Today auth is JSON only.
4. Plugin capture as a references manifest (`plugins.json`) and a new `plugins` effect category.
5. Content viewing: the Setup detail serves every file's text, grouped by category.
6. Install requires login and records a pull. Anonymous install is removed.
7. Revert of your own published setups to a prior version.
8. Follow users, a Following feed, and public profile pages with counts and social links.
9. Trending Discover, ranked by pulls in a rolling window (24h, 7d, all).
10. History: a timeline of your pushes and pulls with contents and revert.
11. A module split so the page build can run as parallel subagents safely.

Out of scope (fast follow, listed in section 13).

## 3. Design system (locked)

No gradients anywhere. No em dashes in any copy. No emojis. Depth comes from layered grey surfaces, hairline borders, one soft shadow, and a faint blueprint dot grid (an SVG data URI of 1px dots, not a CSS gradient).

Fonts (loaded via Google Fonts link in `base.html`):
- Display and wordmark: Fraunces (optical serif), weights 400 to 700, italic used for accent words.
- UI and body: Hanken Grotesk, weights 400 to 700.
- Technical tokens (slugs, versions, counts, commands, keys, code): JetBrains Mono.

Color tokens (CSS custom properties in `static/app.css :root`, copied from the mockup):
```
--ink:#0e1c2b; --ink-2:#3a5169; --ink-3:#6f8298;
--paper:#dfe4ec; --surface:#eaeef4; --surface-2:#e0e6ef; --raise:#f1f4f9;
--line:#c9d3e0; --line-2:#d6dee9;
--blue:#4f7cf0; --blue-700:#3056c4; --blue-tint:#dde7fd;
--teal:#0f8e8a; --teal-600:#0c7470; --teal-tint:#d4ece9;
--amber:#9f5f1c; --amber-tint:#f2e3cd;   /* used only for the runs-code and secret warnings */
--radius:14px; --radius-sm:9px;
--shadow:0 1px 2px rgba(14,28,43,.05), 0 16px 34px -20px rgba(14,28,43,.30);
--shadow-sm:0 1px 2px rgba(14,28,43,.06);
```

Component primitives (all present in the mockup, to be lifted into `app.css`): top nav with wordmark and a teal status dot, setup card with hover lift and a left accent rule (blue normally, amber when the setup runs code), pill tab group, rolling window toggle, search field, stat tiles, dark mono command block, danger banner, expandable file row (native `details` element), version row with revert action, history timeline node, profile hero, social chip, section label with trailing rule, API key row.

Accessibility: text contrast meets WCAG AA against the grey surfaces, focus states visible, the file expanders are native `details` so they work without JavaScript.

## 4. Information architecture

App shell (`base.html`) renders the nav and a content block. Pages:

| Route | Page | Auth |
| --- | --- | --- |
| `/` | Discover (trending) and Following tabs | public, Following requires login |
| `/s/{slug}` | Setup detail with effects, contents, versions, revert | public |
| `/history` | Your push and pull timeline | login |
| `/account` | Your profile, edit, API keys, your setups | login |
| `/u/{username}` | Public profile, setups, follow button, counts | public |
| `/login`, `/signup`, `/logout` | Web auth | public |

The nav shows Discover, Following, History, Account when logged in, and Discover plus Log in and Sign up when logged out.

## 5. Data model changes

Reuse existing `User`, `ApiKey`, `Setup`, `SetupVersion`. Add fields and tables. All timestamps are timezone aware via the existing `_utcnow`.

User, add nullable columns:
- `display_name: str | None` (String 120)
- `bio: str | None` (String 500)
- `link_github: str | None` (String 200)
- `link_linkedin: str | None` (String 200)
- `link_x: str | None` (String 200)

New table `Follow`:
- `id` pk
- `follower_id` FK user.id
- `followee_id` FK user.id
- `created_at` default `_utcnow`
- `UniqueConstraint(follower_id, followee_id, name="uq_follow")`
- A user cannot follow themselves (enforced in the endpoint, not the schema).

New table `PullEvent`:
- `id` pk
- `user_id` FK user.id
- `setup_id` FK setup.id
- `version: int` (the version pulled)
- `created_at` default `_utcnow`, indexed (drives trending and history)

Content of a past pull is not duplicated. A `SetupVersion` is immutable, so a `PullEvent` plus `(setup_id, version)` reconstructs exactly what was pulled.

## 6. Capture model and the plugins manifest

A bundle is a `{relative_path: text_content}` map, packed deterministically as today. The capture convention (documented in the README and applied by the agent) collects:

| Path in bundle | Source on disk | Notes |
| --- | --- | --- |
| `CLAUDE.md`, `.claude/rules/*` | same | rules |
| `skills/*/SKILL.md` and skill files | `~/.claude/skills` or project | skills |
| `commands/*.md` | commands | commands |
| `agents/*.md` | agents | agents |
| `hooks/hooks.json` | hooks config | hooks, runs code |
| `.mcp.json` | MCP config | MCP servers, runs code |
| `plugins.json` | derived from settings.json | plugins, runs code (new) |

Plugins are captured by reference, not by value. The agent reads `~/.claude/settings.json`, takes the enabled entries from `enabledPlugins` (the keys set to true, each of the form `name@marketplace`) and the matching entries from `extraKnownMarketplaces`, and writes a normalized `plugins.json` at the bundle root:

```json
{
  "plugins": [
    { "name": "superpowers", "marketplace": "claude-plugins-official", "enabled": true }
  ],
  "marketplaces": {
    "claude-plugins-official": { "source": "github", "repo": "anthropics/claude-plugins" }
  }
}
```

The plugin cache (the downloaded plugin code under `plugins/cache/`) is never uploaded. On install the agent re-adds each marketplace and enables each plugin, with the user's approval, and Claude Code fetches the code from the github source.

Secrets are never uploaded. The README capture convention restates this, and the effects manifest flags `sk-`, `AKIA`, and PRIVATE KEY patterns. Responsibility remains the user's.

## 7. Effects manifest additions

`bundle.effects_manifest(files)` keeps `hooks`, `mcp_servers`, `counts`, `secret_flags`, and adds:
- `plugins`: parsed from `plugins.json` if present. A list of `{ "name", "marketplace", "source" }` where `source` is the `owner/repo` string from the matching marketplace (or empty if unknown). Parsing tolerates malformed JSON the same way the hooks and MCP parsing does (try, except ValueError and AttributeError, leave empty).
- `counts.plugins`: number of enabled plugins.
- `runs_code`: now `bool(hooks or mcp_servers or plugins)`.

The detail page renders plugins with their source repos and an amber provenance dot, because enabling a plugin runs third-party code.

## 8. Content viewing

The Setup detail shows every file's text, grouped into Rules, Skills, Commands, Agents, and Config (hooks, mcp, plugins), each file in a native `details` expander rendered through Jinja autoescape so it is XSS safe. Secret matches are highlighted in place.

Implementation: extend the core to optionally return file contents.
- `setups.preview(db, slug, include_files=False)`. Default false preserves the current MCP behavior and token economy. The web detail route calls it with `include_files=True`, which unpacks the latest version and returns `files: {path: content}` in addition to the manifest and the path list.
- Bundles are size limited (`MAX_BUNDLE_BYTES`, 5 MB), so rendering inline is bounded and safe. A raw single file endpoint is a fast follow, not needed for v1.

## 9. Behaviors

### 9.1 Web auth
Add `login.html` and `signup.html`. `GET /login` and `GET /signup` render forms. `POST /login` verifies email and password and sets `request.session["uid"]`. `POST /signup` creates the user (reusing the existing logic) and logs in. `POST /logout` clears the session. The existing `current_user` dependency already accepts session or Bearer, unchanged.

### 9.2 Install requires login, records a pull
`setups.install(db, slug, user)` gains a required `user`. It records `PullEvent(user_id=user.id, setup_id, version=latest)`, increments `downloads`, and returns files, effects, and version as today.
- REST `GET /api/setups/{slug}/download` requires `current_user`.
- MCP `install_setup` calls `_require_user(db)` and passes the user.
- Anonymous install is removed. Existing tests that installed or downloaded anonymously are updated to authenticate, and a new test asserts anonymous install returns 401 over REST and a PermissionError over MCP.

### 9.3 Revert (own setups only)
`setups.revert(db, user, slug, target_version) -> dict`:
1. Load the setup. If `setup.owner_id != user.id`, raise `OwnershipError` (maps to 403).
2. Load the target `SetupVersion`. If absent, raise `NotFound` (maps to 404).
3. `new_version = setup.latest_version + 1`.
4. Copy the archive: read `storage.get_archive(target.archive_key)`, write it to `new_key = f"{slug}/v{new_version}.tar.gz"`.
5. Create `SetupVersion(setup_id, version=new_version, manifest_json=target.manifest_json, archive_key=new_key, size_bytes=target.size_bytes)`.
6. Set `setup.latest_version = new_version`, commit.
7. Return `{ "slug", "version": new_version, "reverted_from": target_version }`.

Revert never rewrites or deletes a version, so the `UniqueConstraint(setup_id, version)` is always satisfied and history stays append only. Endpoint: `POST /api/setups/{slug}/revert` body `{ "version": int }`, auth and owner required. UI: a Revert action on each prior version on the detail page and on each push entry in History.

### 9.4 Trending Discover
`setups.list_setups(db, query=None, window=None, following_of=None)`:
- `window` in `{"24h", "7d"}`: order by the count of `PullEvent` for the setup with `created_at >= now - window`, descending, then by `downloads` descending. Setups with zero recent pulls still appear, after ranked ones (left join, coalesce count to 0).
- `window` None or `"all"`: order by `downloads` descending, then `created_at` descending.
- `following_of=user`: restrict to setups whose `owner_id` is in that user's followees, ordered by `created_at` descending.
The Discover page defaults to `window="7d"` with a 24h, 7d, all toggle. Each card shows its recent pull count. The time window comparison uses standard SQL and works on SQLite and Postgres.

### 9.5 Follow and profiles
- `POST /api/follow/{username}` (auth) creates a `Follow`, idempotent, rejects self follow with 400.
- `DELETE /api/follow/{username}` (auth) removes it, idempotent.
- `/u/{username}` shows display name, handle, bio, social links, follower and following counts, the user's public setups, an `is_following` aware Follow or Unfollow button when logged in.
- The Following tab on `/` uses `following_of=current_user`.

### 9.6 History
`/history` shows a merged, reverse chronological timeline:
- Push entries from the current user's `SetupVersion` rows (joined through owned setups), each with version, file count, timestamp, View contents, and Revert to this.
- Pull entries from the current user's `PullEvent` rows, each with setup, version, timestamp, runs-code chip, View contents, and Re-pull this version (which instructs the agent to install that version).
Filter pills: All, Pushed, Pulled.

### 9.7 Profile editing
`GET /account` renders the edit form prefilled. `POST /account` updates `display_name`, `bio`, `link_github`, `link_linkedin`, `link_x`. Links are stored as given and rendered with `rel="noopener noreferrer nofollow"`.

## 10. API and route summary

JSON API (in `app/api.py`, extended): existing signup, login, keys, setups list, setup get, publish, download (now auth), plus `POST /api/setups/{slug}/revert`, `POST` and `DELETE /api/follow/{username}`, `POST /api/account` (profile update).

MCP tools (in `app/mcp_server.py`): `publish_setup`, `preview_setup`, `list_setups` unchanged in signature. `install_setup` now requires auth and records a pull. A future `view_setup` returning contents is a fast follow.

Web pages: see section 4, one router module per area.

## 11. Architecture and module split (for a parallel safe build)

Foundation modules (built first, sequentially, because everything depends on them):
- `app/models.py`: add `Follow`, `PullEvent`, and the User columns.
- `app/bundle.py`: add plugin parsing and the `plugins` effect, update `runs_code`.
- `app/setups.py`: add `revert`, the `user` and pull recording in `install`, `include_files` in `preview`, and the `window` and `following_of` ranking in `list_setups`.
- `app/api.py`: add revert, follow, account endpoints, and the install auth change.
- `app/mcp_server.py`: install auth change.
- `app/static/app.css` and `app/templates/base.html`: the design system and shell.
- `app/web/__init__.py`: aggregates the per area routers.

Page modules (built in parallel, each owns one router file plus its template, all against the frozen design system and the foundation interfaces):
- `app/web/feed.py` and `templates/feed.html`: Discover and Following.
- `app/web/detail.py` and `templates/detail.html`: Setup detail, contents, versions, revert UI.
- `app/web/history.py` and `templates/history.html`: History timeline.
- `app/web/account.py` and `templates/account.html`, `profile.html`: Account, Profile, edit.
- `app/web/auth.py` and `templates/login.html`, `signup.html`: web auth.

`app/main.py` mounts `static`, includes the JSON `api` router and the aggregated `web` router, and keeps the existing MCP mount and lifespan. Fonts load from the Google Fonts link in `base.html` (self hosting is a fast follow).

## 12. Security and trust

- Plugins are the highest trust item, because enabling one runs third-party code from a github repo. The manifest always shows the source repo so the installer can judge provenance. This is more important than for hooks or MCP.
- Content viewing strengthens transparency. The manifest summarizes, the file browser lets a careful reader inspect every line, including skills the manifest only counts.
- Install now requires login, which both enables history and ties pulls to an accountable identity.
- Revert is owner only and append only. No destructive version edits.
- All rendered file content and user supplied profile text passes through Jinja autoescape. Social links carry `rel="noopener noreferrer nofollow"`.
- The transparency-first stance is unchanged. dothub shows effects and contents, it does not vet them, and installing is the user's responsibility.

## 13. Out of scope, deferred to fast follow

- A raw single file API endpoint and full text search.
- Self hosted fonts for offline and performance.
- Plugin version pinning (we capture marketplace and name, resolving to current upstream).
- Pull revert (this release does revert of published setups only, per decision).
- Notifications, teams, and organizations.
- A `view_setup` MCP tool returning contents.

## 14. Testing

SQLite in memory and moto for S3, as today. New and updated tests:
- Models: `Follow` uniqueness and self follow rejection, `PullEvent` creation.
- Install: requires auth (401 REST, PermissionError MCP), records a `PullEvent`, increments downloads.
- Revert: owner creates a new version copying content and manifest, non owner gets 403, unknown version gets 404, the version sequence never collides.
- Trending: `list_setups` window ranking orders by recent pulls, setups with no recent pulls still appear.
- Plugins: `effects_manifest` parses `plugins.json` into `plugins` with source repos, `runs_code` becomes true, malformed JSON is tolerated.
- Content: web detail returns file contents, autoescape renders a script tag inertly.
- Follow and profile: follow and unfollow endpoints, profile counts, profile update persists.
- Each web page renders for the correct auth state.
- The `BundleError` to 400 mapping and prior v1 tests continue to pass.

## 15. Build approach

Subagent driven, Opus only, no AI attribution in commits, no em dashes in any copy or doc. Phase 1 builds the foundation modules and their tests sequentially. Phase 2 dispatches one Opus subagent per page module in parallel, each owning a disjoint router and template against the frozen design system and the foundation interfaces. Phase 3 is a whole branch review, then finishing the branch.
