# Agent Setup Hub — v1 Design Spec

- **Working name:** `dothub` (placeholder — naming deferred, don't bikeshed)
- **Date:** 2026-06-30 (rev 2 — incorporates review feedback)
- **Status:** approved, scope adjusted

## 1. What this is

**One-liner:** GitHub-for-dotfiles meets Product Hunt for Claude Code setups. Users publish their whole Claude Code environment (skills, commands, agents, hooks, MCP config) as a versioned "setup," browse a public feed of others' setups, and pull any setup into their own `.claude/`. The agent itself publishes and installs setups via a hosted remote MCP server.

**Gap it fills:** Component registries (skills-only like Open Agent Skills, MCP-only like Smithery, rules-only like cursor.directory) and private dotfile-sync tools (ai-dotfiles-manager, Microsoft APM, MCP Market Hub) both exist — but nobody hosts **whole-environment bundles behind a public social feed with agent-native push/pull**. That intersection is unbuilt (validated in research, 2026-06-29).

**Primary purpose for the builder:** a small, modern, agent-oriented **backend + database** service to deploy as a robust AWS cloud-native stack. The app is the vehicle; the deployment is the lesson.

## 2. Scope

**In (v1):**
- Accounts with **password authentication** (humans) + issued **API keys** (agents)
- Publish a setup as a versioned whole-environment bundle
- **Object storage (S3)** for bundle archives; metadata in Postgres
- Public browseable feed + setup detail page (server-rendered HTML)
- Pull/install a setup, with a **transparency-first effects preview** before anything is written
- Agent self-push **and** self-install via a hosted remote MCP server
- Claude Code bundle format only

**Out (deferred, with the trigger that should pull each one in):**
- Follows / likes / trending ranking — *add when recency-sort stops surfacing good setups*
- Multi-tool (Cursor/Codex/Gemini) — *add after Claude-only validates; this is the moat vs Anthropic's official marketplace*
- OAuth / social login — *password auth covers v1; add when users ask*
- Full-text search — *when the feed outgrows one page*
- Teams / orgs / private setups — *when someone actually asks*
- Forking-with-lineage, partial install, compatibility floors — *fast-follows once the core loop is real (see §11)*

## 3. Architecture

Single FastAPI app — one process, one deploy artifact:

```
client (Claude Code agent + browser)
  → Nginx (TLS termination, reverse proxy)
    → gunicorn/uvicorn (systemd) → FastAPI
       ├─ GET  /            HTML feed
       ├─ GET  /s/{slug}    HTML setup detail (renders the effects manifest prominently)
       ├─ /api/...          JSON REST  (password login → session cookie; API key for programmatic)
       └─ /mcp              remote MCP server (FastMCP, Streamable HTTP)
    → Postgres (RDS)   — users, setups, setup_versions  (metadata only)
    → S3               — bundle archives (the bytes)
```

- Stack: **FastAPI + Postgres (RDS) + S3**. HTML via Jinja2. MCP via FastMCP mounted in the same app if straightforward; otherwise a sibling systemd unit sharing the same DB/bucket. `# ponytail: one process if FastMCP mounts cleanly, split only if it fights the ASGI lifespan`.
- **Auth model (GitHub-style split):** humans sign up + log in with email/password (hashed with bcrypt/argon2) → signed session cookie for the web app. Agents/programmatic clients use an **API key** the user generates from their account → `Authorization` header / MCP server config. `# ponytail: session cookie + API key, skip OAuth in v1`.
- **Storage:** archive bytes live in S3; Postgres stores only the S3 object key + metadata. Thin `boto3` wrapper (`put_object`/`get_object`/`presign`); no hand-rolled storage abstraction. AWS access via the EC2 instance's **IAM role** (no static keys on the box).
- 12-factor config via env only: `DATABASE_URL`, `S3_BUCKET`, `BASE_URL`, `SESSION_SECRET`, `MAX_BUNDLE_BYTES`.

**Key boundary:** the hosted server is **only the registry**. The agent (local) does all filesystem I/O — it reads its own `.claude/` to publish, and writes files on install (after the user approves). The server never touches a user's disk.

## 4. Data model

```
user(id, username UNIQUE, email UNIQUE, password_hash, created_at)

api_key(id, user_id FK→user, key_hash, label, created_at, last_used_at)
  -- a user can mint/revoke keys; agents authenticate with these

setup(id, owner_id FK→user, slug UNIQUE, title, description,
      latest_version INT, downloads INT DEFAULT 0,
      is_public BOOL DEFAULT true, created_at, updated_at)

setup_version(id, setup_id FK→setup, version INT,
              manifest_json JSONB,      -- includes the effects manifest (§5)
              archive_key TEXT,         -- S3 object key (bytes live in S3)
              size_bytes INT, created_at,
              UNIQUE(setup_id, version))
```

Feed query: `SELECT * FROM setup WHERE is_public ORDER BY downloads DESC, created_at DESC LIMIT n`.

## 5. Bundle format, validation & the effects manifest

A setup bundle = a map `{ relative_path: file_content_text }` mirroring a Claude Code plugin / `.claude/` layout, e.g. `.claude-plugin/plugin.json`, `skills/<x>/SKILL.md`, `commands/*.md`, `agents/*.md`, `hooks/hooks.json`, `.mcp.json`. Reusing the existing plugin format means we host/socialize an existing standard rather than invent a schema.

- Server stores a deterministic archive (tar of path-sorted entries) in S3, and extracts `manifest_json` into Postgres.
- **Validation — trust boundary, NOT simplified away:**
  - reject any path that is absolute, contains `..`, or escapes the bundle root (path-traversal guard, enforced on store and on return)
  - reject total size > `MAX_BUNDLE_BYTES` (default 5 MB)
  - reject > 500 files
  - text only in v1 (UTF-8); reject non-decodable → binary support deferred
- **Effects manifest (the safety feature — computed at publish, stored in `manifest_json`):**
  - `hooks`: list of `{event, command}` parsed verbatim from `hooks/hooks.json` — the *exact* shell commands
  - `mcp_servers`: list of `{name, command, args}` parsed from `.mcp.json`
  - `counts`: `{skills, commands, agents, rules}`
  - `runs_code`: `true` if any hooks or MCP servers are present
  - This is what powers the transparency-first install (§7) and the detail page.
- **Secret hygiene:** server-side regex scan for obvious secrets (`sk-`, `AKIA`, `-----BEGIN`). v1 flags matches in `manifest_json`; does not block. `# ponytail: regex flag now, real secret-scanning later`.

## 6. API surface

**REST (browser + curl):**
- `POST /api/signup {username, email, password}` → creates account, starts session
- `POST /api/login {email, password}` → session cookie
- `POST /api/keys` *(session)* `{label}` → `{api_key}` (shown once) · `DELETE /api/keys/{id}` revokes
- `GET  /api/setups?limit=` → public setups
- `GET  /api/setups/{slug}` → setup + versions + effects manifest
- `POST /api/setups` *(auth: session or API key)* `{title, description, slug?, files}` → create or bump version. **Publish semantics:** new slug → create (owned by caller); your existing slug → bump `version`; someone else's slug → `403`. (Slug globally unique in v1; `# ponytail: global slug now, scope as {username}/{slug} if squatting becomes real`.)
- `GET  /api/setups/{slug}/download` → presigned S3 URL (increments `downloads`)

**MCP tools (agent-native — same underlying logic):**
- `publish_setup(title, description, files, slug?)` → `{slug, version, url}`
- `preview_setup(slug)` → **effects manifest + file list** (no download count bump) — the agent calls this *before* installing to show the user what it does
- `install_setup(slug)` → `{files, effects}` (agent shows effects, gets approval, writes locally)
- `list_setups(query?)` → `[{slug, title, description, downloads, runs_code}]`

Auth: API key via `Authorization` header (REST/MCP) or session cookie (web). Feed is public read — no login to browse.

**HTML:**
- `GET /` → feed (cards: title, author, downloads, component summary, a ⚠ marker if `runs_code`)
- `GET /s/{slug}` → detail: description, versions, **effects manifest rendered prominently** (exact hook commands, MCP servers), file tree, pull instructions, and a plain-language responsibility notice.

## 7. Flows

**Publish — agent self-push:** user says "publish my setup as `my-python-flow`" → agent reads its own `~/.claude/`, builds the files map, calls `publish_setup` → server validates, computes the effects manifest, stores bytes in S3 + metadata in RDS, returns the URL.

**Install — transparency-first (the safety model):**
1. User: "install `some-user/claude-setup`."
2. Agent calls `preview_setup(slug)` → gets the **effects manifest** + a file list.
3. Agent shows the user: a **diff vs their current `.claude/`**, the **exact hook commands**, the **MCP servers** that would be added, and the skills/commands counts. If `runs_code`, it says so loudly.
4. **User explicitly approves.** Only then the agent calls `install_setup`, writes files, and reloads.
5. **Trust model = caveat emptor.** The platform's job is to make effects *maximally visible*; verifying safety is the user's responsibility. A responsibility notice is shown on the web detail page and at the approval step. No server-side sandboxing or verification in v1.

## 8. Deployment — AWS cloud-native (the only target for v1)

The user has already done CI/CD elsewhere and is skipping the bare-metal VPS; v1 ships **one robust AWS stack**.

- **Compute:** EC2 (Ubuntu) running gunicorn + uvicorn workers under **systemd**.
- **Edge:** **Nginx** reverse proxy + **certbot** TLS on the instance.
- **Database:** **RDS** Postgres (managed).
- **Storage:** **S3** bucket for bundle archives; EC2 reaches it via an **IAM instance role** (no static credentials on the box).
- **Networking / security groups:** 80/443 from anywhere; 22 from your IP only; RDS 5432 reachable **only** from the EC2 security group; S3 access scoped by the IAM role/bucket policy.
- **Config:** all via env vars; nothing AWS-specific hardcoded, so the same artifact stays portable if a second environment is ever added.

## 9. Testing

One runnable check (ponytail rule — the smallest thing that fails if the logic breaks): `tests/test_roundtrip.py`, assert-based, S3 mocked with `moto`, DB via a `DATABASE_URL` override:

- publish a setup with 3 files (incl. a `hooks/hooks.json`) → effects manifest reports `runs_code=true` and captures the exact command
- preview → install → files identical to what was published
- re-publish same slug → `version` increments, `latest_version` updated
- download/install increments `downloads`
- file key `../x` → rejected (path-traversal guard); oversize bundle → rejected
- publish to a slug owned by another user → `403`

No framework beyond pytest; no fixtures factory; no per-endpoint suite.

## 10. Open questions / risks

- **Moat vs Anthropic** adding a social tab to the official (git-based) marketplace → answer is multi-tool support, deferred to v2.
- **Username/slug squatting** with open signup → acceptable at demo scale; revisit `{username}/{slug}` scoping if it bites.
- **Install safety is social, not technical** by design — if abuse appears, the next lever is verified authors / signed setups (not sandboxing).

## 11. Fast-follows (post-v1, not in scope but designed-for)

The effects manifest and versioned bundles leave clean room for: **fork-with-lineage** (attribution graph), **partial install** (pick skills but skip hooks), **diff-against-current as a first-class feature**, and **dependency surfacing** (a setup's `.mcp.json` needs servers + keys the user must still provide).
