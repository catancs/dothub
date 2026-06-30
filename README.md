# dothub — agent setup hub

Publish your whole Claude Code setup, browse a public feed, pull setups in.
Remote MCP server + web feed in one FastAPI app.

## Run locally
```bash
pip install -r requirements.txt
export $(grep -v '^#' .env.example | xargs)   # or set real values
uvicorn app.main:app --reload
```
- Feed: http://localhost:8000/
- MCP:  http://localhost:8000/mcp/
- Health: http://localhost:8000/healthz

## Test
```bash
pytest -v          # uses in-memory SQLite + mocked S3, no infra needed
```

## Add to Claude Code (agent self-push)
Add the remote MCP server with your API key (minted at `POST /api/keys`):
```
claude mcp add --transport http dothub https://your-domain.example/mcp/ \
  --header "Authorization: Bearer dh_your_key"
```
Then: "publish my setup as my-flow" / "preview some-user/their-slug before installing".
