# dothub v2 redesign, implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development to implement this plan task by task. Foundation tasks (1 to 5) run sequentially. Page tasks (6 to 10) touch disjoint files and run as parallel Opus subagents after the foundation is frozen.

Goal: redesign dothub with a bespoke design system and add plugins capture, content viewing, follow and profiles, trending discovery, pull history, and owner revert.

Architecture: one FastAPI app, server rendered Jinja pages on a shared design system, JSON API, and the existing remote MCP server. Foundation modules (models, bundle, setups, api, mcp, design system, app shell, stub web routers) are built first. Each page is then one router file plus one template, built in parallel against the frozen foundation.

Tech stack: FastAPI, SQLAlchemy 2.0 sync, Postgres or SQLite, S3 or local disk, Jinja2, FastMCP. Tests use SQLite in memory and moto.

Visual source of truth: `docs/dothub-redesign-mockup.html`. Reproduce its markup and the design tokens exactly.

## Global Constraints

- No em dashes anywhere, in copy, code, comments, or docs. Use periods, commas, colons, parentheses.
- No gradients. Depth via the grey token palette, hairlines, one soft shadow, and the SVG blueprint dot grid.
- Fonts: Fraunces (display), Hanken Grotesk (UI), JetBrains Mono (technical tokens). Never Inter, Roboto, Arial, or system-ui as the design face.
- Color tokens are fixed in section 3 of the spec and live in `app/static/app.css :root`.
- Commits contain no AI attribution (no Co-authored-by, no Generated with Claude, no robot emoji). Conventional messages.
- All sub-agents run on Opus.
- Reuse the existing `current_user` dependency (accepts session cookie or Bearer API key).
- All file content and user text renders through Jinja autoescape. Never mark setup content or profile text safe.
- Spec: `docs/superpowers/specs/2026-06-30-dothub-v2-redesign.md`.

---

## Task 1: Design system, app shell, static, and stub web routers

Foundation. Establishes the shared visual layer and the routing skeleton so page tasks never edit shared files.

Files:
- Create `app/static/app.css` (design tokens plus component classes, lifted verbatim from the `<style>` block of `docs/dothub-redesign-mockup.html`).
- Create `app/templates/base.html` (the app shell: html head with the Google Fonts link and the app.css link, the sticky top nav with wordmark and nav links, and a `{% block body %}{% endblock %}`). Nav shows Discover, Following, History, Account when `user` is set, else Discover, Log in, Sign up. Pass `user` to every page render.
- Create `app/web/__init__.py` exposing `router = APIRouter()` that includes the five page routers.
- Create `app/web/feed.py`, `app/web/detail.py`, `app/web/history.py`, `app/web/account.py`, `app/web/auth.py`, each exposing `router = APIRouter()` as a stub (no routes yet, just the object).
- Modify `app/main.py`: mount static at `/static`, include the aggregated web router. Keep the JSON api router, the MCP mount, and the lifespan.
- Test `tests/test_shell.py`.

Interfaces:
- Produces: `app/templates/base.html` with `{% block body %}`, used by every page. The shared `templates` Jinja env is created in a small `app/web/_render.py` helper: `templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))` and a convenience `render(request, name, ctx)` that injects `user` via `current_user` if present. Page tasks import `templates` and `current_user`.

Steps:
- [ ] Step 1: write `tests/test_shell.py`:
```python
import app.models  # noqa: register tables
from fastapi.testclient import TestClient

def test_static_css_served(client):
    r = client.get("/static/app.css")
    assert r.status_code == 200
    assert "--blue:#4f7cf0" in r.text

def test_app_boots_with_web_router(client):
    # health still works and an unknown page is a clean 404, not a 500
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/nope").status_code == 404
```
- [ ] Step 2: run it, expect failure (no static mount).
- [ ] Step 3: create `app/static/app.css` by copying the full contents of the `<style>` element in `docs/dothub-redesign-mockup.html` (tokens and all component classes). Remove the leading `<style>` and trailing `</style>` tags.
- [ ] Step 4: create `app/templates/base.html` with the head (fonts link, `<link rel="stylesheet" href="/static/app.css">`), the nav (reproduce `header.nav` from the mockup, links are real hrefs: `/`, `/?tab=following`, `/history`, `/account`, `/login`, `/signup`), the avatar monogram from `user.username[:2]` when logged in, and `{% block body %}{% endblock %}`.
- [ ] Step 5: create `app/web/_render.py` with the `templates` env and `render(request, name, ctx, user=None)` helper that sets `ctx["request"]`, `ctx["user"]`.
- [ ] Step 6: create the five stub router modules and `app/web/__init__.py` aggregating them.
- [ ] Step 7: modify `app/main.py` to `app.mount("/static", StaticFiles(directory=...))` and `app.include_router(web_router)`.
- [ ] Step 8: run `pytest tests/test_shell.py -v`, expect pass. Run the full suite, expect no regressions.
- [ ] Step 9: commit `feat: design system, app shell, static, web router skeleton`.

## Task 2: Data model additions

Foundation. Adds Follow, PullEvent, and the User profile columns.

Files:
- Modify `app/models.py`.
- Test `tests/test_models_v2.py`.

Interfaces:
- Produces: `Follow(id, follower_id, followee_id, created_at)` with `UniqueConstraint("follower_id","followee_id", name="uq_follow")`. `PullEvent(id, user_id, setup_id, version, created_at indexed)`. `User` gains nullable `display_name, bio, link_github, link_linkedin, link_x`.

Steps:
- [ ] Step 1: write `tests/test_models_v2.py` (module level `import app.models`):
```python
import app.models  # noqa
import pytest
from sqlalchemy.exc import IntegrityError

def test_follow_unique(db):
    from app.models import User, Follow
    a = User(username="a", email="a@x", password_hash="h")
    b = User(username="b", email="b@x", password_hash="h")
    db.add_all([a, b]); db.commit()
    db.add(Follow(follower_id=a.id, followee_id=b.id)); db.commit()
    db.add(Follow(follower_id=a.id, followee_id=b.id))
    with pytest.raises(IntegrityError):
        db.commit()

def test_pull_event_and_profile_fields(db):
    from app.models import User, Setup, PullEvent
    u = User(username="p", email="p@x", password_hash="h", display_name="P", link_x="x.com/p")
    db.add(u); db.commit()
    s = Setup(owner_id=u.id, slug="s", title="S"); db.add(s); db.commit()
    db.add(PullEvent(user_id=u.id, setup_id=s.id, version=1)); db.commit()
    assert db.query(PullEvent).count() == 1
    assert u.display_name == "P" and u.link_x == "x.com/p"
```
- [ ] Step 2: run, expect failure.
- [ ] Step 3: add the columns and tables to `app/models.py`:
```python
class Follow(Base):
    __tablename__ = "follow"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id", name="uq_follow"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    followee_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class PullEvent(Base):
    __tablename__ = "pull_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    setup_id: Mapped[int] = mapped_column(ForeignKey("setup.id"))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
```
And on `User` add: `display_name`, `bio`, `link_github`, `link_linkedin`, `link_x`, each `Mapped[str | None] = mapped_column(String(...), nullable=True)` with sizes 120, 500, 200, 200, 200.
- [ ] Step 4: run `pytest tests/test_models_v2.py -v`, expect pass.
- [ ] Step 5: commit `feat: Follow, PullEvent, and profile fields`.

## Task 3: Plugins in the effects manifest

Foundation. Parses `plugins.json` and adds the plugins effect.

Files:
- Modify `app/bundle.py`.
- Test `tests/test_bundle_plugins.py`.

Interfaces:
- Produces: `effects_manifest` returns `plugins: [{name, marketplace, source}]`, `counts.plugins`, and `runs_code = bool(hooks or mcp_servers or plugins)`.

Steps:
- [ ] Step 1: write `tests/test_bundle_plugins.py`:
```python
from app.bundle import effects_manifest
import json

def test_plugins_parsed_and_runs_code():
    files = {"plugins.json": json.dumps({
        "plugins": [{"name": "superpowers", "marketplace": "official", "enabled": True}],
        "marketplaces": {"official": {"source": "github", "repo": "anthropics/claude-plugins"}},
    })}
    m = effects_manifest(files)
    assert m["plugins"] == [{"name": "superpowers", "marketplace": "official", "source": "anthropics/claude-plugins"}]
    assert m["counts"]["plugins"] == 1
    assert m["runs_code"] is True

def test_malformed_plugins_tolerated():
    m = effects_manifest({"plugins.json": "{not json"})
    assert m["plugins"] == [] and m["counts"]["plugins"] == 0
```
- [ ] Step 2: run, expect failure.
- [ ] Step 3: in `effects_manifest`, after the mcp block, add:
```python
plugins = []
if "plugins.json" in files:
    try:
        doc = json.loads(files["plugins.json"])
        markets = doc.get("marketplaces", {})
        for p in doc.get("plugins", []):
            if not p.get("enabled", True):
                continue
            mk = markets.get(p.get("marketplace", ""), {})
            plugins.append({
                "name": p.get("name", ""),
                "marketplace": p.get("marketplace", ""),
                "source": mk.get("repo", ""),
            })
    except (ValueError, AttributeError):
        pass
```
Add `"plugins": len(plugins)` to `counts`, add `"plugins": plugins` to the return, and change `runs_code` to `bool(hooks or mcp_servers or plugins)`.
- [ ] Step 4: run `pytest tests/test_bundle_plugins.py -v`, expect pass. Run `tests/test_bundle.py`, expect pass.
- [ ] Step 5: commit `feat: plugins effect from plugins.json manifest`.

## Task 4: Setups core, install auth, pull recording, preview contents, revert, trending

Foundation. The keystone logic.

Files:
- Modify `app/setups.py`.
- Test `tests/test_setups_v2.py`.

Interfaces:
- Produces:
  - `install(db, slug, user) -> dict` (user now required; records a PullEvent; downloads += 1).
  - `preview(db, slug, include_files=False) -> dict` (adds `files: {path: content}` when true).
  - `revert(db, user, slug, target_version) -> dict` returning `{slug, version, reverted_from}`; raises `OwnershipError` for non owner, `NotFound` for missing setup or version.
  - `list_setups(db, query=None, window=None, following_of=None) -> list[dict]` with trending and following.

Steps:
- [ ] Step 1: write `tests/test_setups_v2.py` covering: install requires a user and writes a PullEvent and bumps downloads; preview include_files returns contents; revert as owner creates version N+1 copying the target manifest and content and moves latest; revert by a non owner raises OwnershipError; revert of a missing version raises NotFound; list_setups window="7d" orders a recently pulled setup ahead of an unpulled one and still lists the unpulled one; list_setups following_of returns only followed owners' setups. Use the existing publish round trip and the `s3` moto fixture. (Full assertions in the brief.)
- [ ] Step 2: run, expect failure.
- [ ] Step 3: implement the changes:
  - `install` signature becomes `(db, slug, user)`. After loading the latest version, add `db.add(PullEvent(user_id=user.id, setup_id=setup.id, version=v.version))` before commit, keep the downloads increment and return shape.
  - `preview(db, slug, include_files=False)`: when true, `files = unpack(storage.get_archive(v.archive_key))` and include `"files": files` (a `{path: content}` dict). Keep the existing `files` path list under its current key, name the contents key `file_contents` to avoid collision. (Confirm the existing key name in code and keep it; add `file_contents` for the dict.)
  - `revert(db, user, slug, target_version)`: per spec section 9.3. Use `storage.get_archive` and `storage.put_archive`.
  - `list_setups`: add `window` and `following_of`. For windows, left join a per setup count of PullEvent within `now - delta` and order by that count desc then downloads desc. For following, filter owner_id in the set of followee ids. Keep the existing author join and the manifest derived `runs_code` per item, and add `recent_pulls` to each item dict.
- [ ] Step 4: run `pytest tests/test_setups_v2.py tests/test_roundtrip.py -v`, expect pass.
- [ ] Step 5: commit `feat: install auth and pulls, preview contents, revert, trending`.

## Task 5: JSON API and MCP wiring

Foundation. Surfaces the new core via REST and updates the MCP install tool.

Files:
- Modify `app/api.py` (add revert, follow, account endpoints; require auth on download; pass user to install).
- Modify `app/mcp_server.py` (install requires auth).
- Test `tests/test_api_v2.py`.

Interfaces:
- Produces: `POST /api/setups/{slug}/revert`, `POST /api/follow/{username}`, `DELETE /api/follow/{username}`, `POST /api/account`, and `GET /api/setups/{slug}/download` now requires `current_user` and records a pull.

Steps:
- [ ] Step 1: write `tests/test_api_v2.py`: anonymous download returns 401; authenticated download records a pull and returns the url; revert by owner returns the new version and by a stranger returns 403; follow then unfollow a user updates the follower count; `POST /api/account` updates profile fields; MCP `install_setup` raises PermissionError without a key. Use the TestClient and the helper that signs up and mints a key, mirroring `tests/test_api.py`.
- [ ] Step 2: run, expect failure.
- [ ] Step 3: implement endpoints. `download` gains `user: User = Depends(current_user)` and calls `setups.install(db, slug, user)`. `revert` validates body `{version:int}`, catches `OwnershipError` to 403 and `NotFound` to 404. Follow endpoints resolve the target by username, reject self follow with 400, are idempotent. `account` updates the five fields from a Pydantic body. In `mcp_server.install_setup`, call `_require_user(db)` and pass the user to `setups.install`.
- [ ] Step 4: run `pytest tests/test_api_v2.py tests/test_api.py tests/test_mcp.py -v`, expect pass. The two prior anonymous install tests are updated here to authenticate.
- [ ] Step 5: commit `feat: revert, follow, account API and MCP install auth`.

## Task 6 (parallel): Discover and Following feed page

Files: implement `app/web/feed.py` and create `app/templates/feed.html`. Test `tests/test_page_feed.py`.

Route: `GET /` reads `tab` (`discover` default or `following`) and `window` (`24h`, `7d` default, `all`) query params. Discover calls `setups.list_setups(db, window=window)`. Following requires login and calls `list_setups(following_of=user)`. Render `feed.html` extending `base.html`, reproducing the Discover section of the mockup: the heading block, the pills (Discover, Following) as links that set `tab`, the window toggle as links that set `window`, and the card grid. Bind per card: rank index, title, `author/slug`, version, description, author monogram, `recent_pulls` (or downloads for all), and the runs-code or no-code chip from the item `runs_code`. Apply the `flag` class when `runs_code`.

Test: GET / renders 200 and lists a published setup with its author; `?tab=following` without login redirects to `/login`; the window toggle links carry the window value.

Steps: write the failing test, implement the route and template by translating the mockup Discover markup into Jinja, run the test, commit `feat: Discover and Following feed page`.

## Task 7 (parallel): Setup detail with effects, contents, versions, revert

Files: implement `app/web/detail.py` and create `app/templates/detail.html`. Test `tests/test_page_detail.py`.

Route: `GET /s/{slug}` calls `setups.preview(db, slug, include_files=True)` and loads the version list and the owner. Render `detail.html` reproducing the mockup Setup screen: the effects panel (danger banner when `runs_code`, secret banner when `secret_flags`, stat tiles for hooks, plugins, skills, files, the hook commands in dark mono blocks, and the plugins block listing each plugin name, marketplace, and source repo), the Contents panel (group `file_contents` by category: Rules, Skills, Commands, Agents, Config which includes hooks, mcp, plugins, each a native `details` expander with the text in a `pre`), and the Version history panel. When `user` owns the setup, render a Revert action on each prior version that posts to `/api/setups/{slug}/revert`. All content rendered through autoescape.

Test: GET /s/{slug} renders 200, shows a hook command verbatim, shows a plugin source repo, shows file contents, and a script tag in file content is escaped (not executed). The revert control appears only for the owner.

Steps: failing test, implement route and template from the mockup, run, commit `feat: Setup detail with contents, plugins, revert`.

## Task 8 (parallel): History timeline

Files: implement `app/web/history.py` and create `app/templates/history.html`. Test `tests/test_page_history.py`.

Route: `GET /history` requires login. Build a merged reverse chronological list: push entries from the user's SetupVersion rows (through owned setups) and pull entries from the user's PullEvent rows. Read `filter` query (`all`, `pushed`, `pulled`). Render the timeline from the mockup History screen, each entry with kind chip, setup, version, time, file count, and the View contents and Revert (push) or Re-pull (pull) actions. Revert posts to the revert endpoint.

Test: a user who published and pulled sees both entry kinds; the pulled filter shows only pulls.

Steps: failing test, implement, run, commit `feat: History timeline`.

## Task 9 (parallel): Account and Profile

Files: implement `app/web/account.py` and create `app/templates/account.html` and `app/templates/profile.html`. Test `tests/test_page_account.py`.

Routes: `GET /account` (login) renders the profile hero, the edit form (display name, bio, github, linkedin, x), the API key rows, and the user's setups, from the mockup Account screen. `POST /account` posts to `/api/account` or handles the form directly and redirects back. `GET /u/{username}` renders `profile.html`: hero with counts (followers, following, setups), social links with `rel="noopener noreferrer nofollow"`, the public setups, and a Follow or Unfollow button when logged in (state from a Follow lookup), posting to the follow endpoints.

Test: `/account` requires login and shows the user's setups and keys; `/u/{username}` shows the follower count and the setups; posting a profile update persists; the follow button reflects state.

Steps: failing test, implement, run, commit `feat: Account and public Profile`.

## Task 10 (parallel): Web auth pages

Files: implement `app/web/auth.py` and create `app/templates/login.html` and `app/templates/signup.html`. Test `tests/test_page_auth.py`.

Routes: `GET /login` and `GET /signup` render forms styled from the design system (cards on the grey surface, Fraunces heading, the primary button). `POST /login` verifies email and password, sets `request.session["uid"]`, redirects to `/`. `POST /signup` creates the user (reuse the signup logic), logs in, redirects. `POST /logout` clears the session and redirects to `/`. On bad credentials, re-render with an inline error, no stack trace.

Test: signing up then logging out then logging in round trips the session; a logged-in request to `/account` succeeds, a logged-out one redirects to `/login`; bad credentials re-render with an error and status 200 or 401, not 500.

Steps: failing test, implement, run, commit `feat: web login, signup, logout`.

## Task 11: Whole branch review and finish

- [ ] Run the full suite, confirm green.
- [ ] Dispatch the final whole branch Opus review against the spec, the design constraints, and the trust model (plugins provenance, content autoescape, install auth, revert append only).
- [ ] Action Critical and Important findings with one consolidated fix subagent.
- [ ] Use superpowers:finishing-a-development-branch.

## Self Review

- Spec coverage: design system (T1), data model (T2), plugins (T3), install auth and pulls and preview contents and revert and trending (T4), API and MCP (T5), Discover and Following (T6), detail with contents and plugins and revert (T7), History (T8), Account and Profile and follow (T9), web auth (T10), review and finish (T11). Every spec section maps to a task.
- Placeholder scan: foundation tasks carry complete code; page tasks carry complete route contracts and bind against the committed mockup markup, which is concrete, not a placeholder.
- Type consistency: `install(db, slug, user)`, `preview(db, slug, include_files)`, `revert(db, user, slug, target_version)`, `list_setups(db, query, window, following_of)` are referenced identically in T4, T5, T6, T7, T8.
- Parallel safety: T6 to T10 each own one `app/web/<area>.py` plus their templates and tests, and never edit `main.py`, `app/web/__init__.py`, `models.py`, `bundle.py`, `setups.py`, `api.py`, `base.html`, or `app.css`, which are frozen after T5.
