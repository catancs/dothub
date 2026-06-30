# dothub — agent setup hub

Publish your whole Claude Code setup, browse a public feed, pull setups in.
Remote MCP server + web feed in one FastAPI app.

## Run locally (zero-infra, no AWS)

`STORAGE_DIR` makes bundles go to a local folder instead of S3, and a SQLite
file replaces Postgres — so it runs with nothing but Python:

```bash
pip install -r requirements.txt
DATABASE_URL='sqlite+pysqlite:///./dothub.db' STORAGE_DIR='./dev-bundles' \
  SESSION_SECRET='dev-secret' uvicorn app.main:app --reload
```
- Feed: http://localhost:8000/
- MCP:  http://localhost:8000/mcp/
- Health: http://localhost:8000/healthz

For production, leave `STORAGE_DIR` unset and set the real S3/RDS values from
`.env.example` (the app then uses S3 + Postgres). See `deploy/DEPLOY.md`.

## Test
```bash
pytest -v          # in-memory SQLite + mocked S3, no infra needed
```

## Add to Claude Code (agent self-push)
Mint a key at `POST /api/keys` (sign up first), then:
```bash
claude mcp add --transport http dothub http://localhost:8000/mcp/ \
  --header "Authorization: Bearer dh_your_key"
```
(Use your real `https://your-domain.example/mcp/` once deployed.)

## Publishing your setup (capture / omit / add)

The server never reads your disk — your agent does. After adding the MCP
server, in a Claude Code session say e.g. *"publish my Claude Code setup to
dothub as my-flow"*. The agent reads your `~/.claude/` (and/or project
`.claude/`), builds a `{path: content}` map, and calls the `publish_setup`
tool.

- **Captured:** `CLAUDE.md`, `skills/`, `commands/`, `agents/`,
  `hooks/hooks.json`, `.mcp.json`.
- **Never upload secrets.** The effects manifest flags `sk-…`, `AKIA…`, and
  PRIVATE KEY blocks under `secret_flags`, but **you** are responsible for
  leaving them out. Don't publish `.env` or anything with live tokens.
- **Omit:** *"…but skip `notes/` and anything with secrets."*
- **Add:** *"…and include a `README.md` describing the setup."* (a file that
  isn't in `.claude/` — the agent just adds it to the map).

## Installing someone else's setup

Always preview before installing — the preview shows the **effects manifest**:
every hook command verbatim, the MCP servers it adds, `runs_code`, and any
`secret_flags`. *"preview their-slug"* → review → *"install their-slug"*. The
agent writes the files locally only after you approve. Installing code that
runs on your machine is your responsibility.
