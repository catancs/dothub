<div align="center">

# dothub

**The agent setup hub.** Publish your whole coding-agent setup. Browse a feed of other people's. Pull one in with a single approval.

<img src="marketing/hero/out/hero.gif" alt="dothub: publish from your agent, lands private, you choose to publish, live on the feed" width="640">

<p>
  <a href="https://dothub.nl"><img alt="live" src="https://img.shields.io/badge/live-dothub.nl-2536c9"></a>
  <img alt="python" src="https://img.shields.io/badge/python-3.12+-blue">
  <img alt="fastapi" src="https://img.shields.io/badge/FastAPI-0.115-009688">
  <img alt="tests" src="https://img.shields.io/badge/tests-182%20passing-137333">
  <img alt="license" src="https://img.shields.io/badge/license-personal-ff5230">
</p>

</div>

---

dothub is one FastAPI app that does two things: a **web feed** you read in the browser, and a **remote MCP server** your coding agent talks to. Your agent publishes your setup. You browse and install other people's. No upload forms, no export scripts.

It started for Claude Code, but it records provenance for any coding agent (Codex, Cursor, Windsurf, Gemini CLI, and more).

## ✨ Why dothub

- **🤖 Agent-native publishing.** You tell your agent "publish my setup." It gathers your `CLAUDE.md`, skills, commands, agents, hooks, and MCP config. No form, no manual export.
- **🔒 Private by default.** When your agent publishes, the setup lands **private**. It is hidden from the feed, search, and every other user. Only you can see it. Nothing goes public until you explicitly click *Publish to everyone*.
- **🛡️ Encrypted at rest.** Your setup files are encrypted on the server's disk. They stay invisible to everyone but you until you publish.
- **📖 Effects manifest, always.** Before you install anyone's setup, dothub shows you exactly what it does: every hook command verbatim, the MCP servers and plugins it adds, a `runs_code` flag, and any secret-looking strings it caught. You review, then you approve.
- **🏠 Self-hostable on one box.** SQLite and local disk by default. Runs with nothing but Python locally, and deploys to a single small server with automatic HTTPS.

## 🚀 Quick start (local, zero infra)

```bash
git clone https://github.com/catancs/dothub.git
cd dothub
pip install -r requirements.txt

DATABASE_URL='sqlite+pysqlite:///./dothub.db' \
STORAGE_DIR='./dev-bundles' \
SESSION_SECRET='dev-secret' \
uvicorn app.main:app --reload
```

Then open:

- 🌐 Feed: http://localhost:8000/
- 🔌 MCP server: http://localhost:8000/mcp/
- 💚 Health: http://localhost:8000/healthz

## 🤝 Add it to Claude Code

Sign up at http://localhost:8000/signup and mint an API key on your account page (it starts with `dh_` and is shown once). Then:

```bash
claude mcp add --transport http dothub http://localhost:8000/mcp/ \
  --header "Authorization: Bearer dh_your_key_here"
```

Once it's live, swap in `https://dothub.nl/mcp/`.

## 📤 Publishing your setup

The server never reads your disk. Your agent does. In a Claude Code session, say something like *"publish my Claude Code setup to dothub as my-flow."* The agent reads your `~/.claude/` (and the project `.claude/` if you want), builds a `{path: content}` map, shows you a preview, and publishes when you approve.

| Captured by default | You can tell the agent to |
|---|---|
| `CLAUDE.md`, `skills/`, `commands/`, `agents/` | skip a folder (`"skip notes/"`) |
| `hooks/hooks.json`, `.mcp.json` | add a file (`"include a README.md"`) |
| `output-styles/`, `settings.json`, `plugins.json` | leave out anything with secrets |

**Never upload secrets.** The effects manifest flags patterns like `sk-...`, `AKIA...`, and PRIVATE KEY blocks under `secret_flags`, but you are responsible for leaving tokens and `.env` files out. Don't publish `~/.claude.json` (it holds private state), memory files, or conversation history.

### What happens to a setup you publish

1. Your agent sends it to dothub. It is **encrypted** and stored.
2. It lands **private**. Hidden from the feed and from your public profile. Only you can preview or install it.
3. You review it on its page. When you are ready, you click **Publish to everyone**.
4. It joins the public feed. Others can preview the effects and install it.

## 📥 Installing someone else's setup

Always preview first. In a Claude Code session: *"preview their-slug"* to see the effects manifest, review it, then *"install their-slug."* The agent writes the files to your `~/.claude/` (or project `.claude/`) only after you approve.

Installing code that runs on your machine (hooks, MCP servers, plugins) is your responsibility. Read the manifest before you say yes.

## 🧪 Tests

```bash
pytest -v          # in-memory SQLite + mocked S3, no infra needed
```

## 🚢 Deploy

The default production deploy runs the same SQLite + local-disk config on a single AWS EC2 box, with Caddy providing automatic HTTPS. See [`deploy/DEPLOY.md`](deploy/DEPLOY.md) for the full runbook.

S3 and Postgres are still supported if you ever outgrow one box. Set the values from [`.env.example`](.env.example) and the app switches backends with no code change.

## 🗂️ Project layout

```
app/            FastAPI app: api.py, web/, mcp_server.py, setups.py, bundle.py
deploy/         setup.sh, redeploy.sh, Caddyfile, systemd unit, runbook
alembic/        schema migrations
tests/          pytest suite (in-memory SQLite + moto for S3)
marketing/hero/ standalone Remotion project that renders the README hero GIF
```

## 📝 License

Personal project of the author. Not currently licensed for redistribution.
