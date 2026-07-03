# dothub Lean AWS Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy dothub to a single lean AWS EC2 box (SQLite on disk, bundles on disk, Caddy auto-TLS), and shed the previous VPC+RDS+S3+nginx+certbot Terraform stack.

**Architecture:** The app is already env-var driven and supports SQLite (`db.py`) and local-disk storage (`storage.py`). Prod config points those at `/var/lib/dothub/`. Two small correctness edits make the file-SQLite and local-disk paths production-safe. Provisioning becomes a transparent shell script; the old `infra/` Terraform module is deleted.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite/WAL), gunicorn+uvicorn, systemd, Caddy, Ubuntu 24.04 on EC2.

## Global Constraints

- Python target on the box: Ubuntu 24.04 system `python3` (3.12); no version pin needed.
- App must keep working unchanged on the in-memory test DB (`sqlite+pysqlite:///:memory:`) and on the S3/moto test backend — these edits must not regress the existing test suite.
- No new runtime dependencies. `presign_get` is *removed*, nothing added.
- Prod config is HTTPS + real `SESSION_SECRET` (the `config.assert_prod_secret` gate must pass).
- Secrets never committed: `SESSION_SECRET`, `.env`, `*.tfvars` stay gitignored.
- All work on a `deploy-lean-aws` branch, not `main`.

---

### Task 0: Branch and commit the approved spec

**Files:**
- Commit: `docs/superpowers/specs/2026-07-03-deploy-lean-aws-design.md` (already written)

- [ ] **Step 1: Create the work branch**

```bash
git checkout -b deploy-lean-aws
```

- [ ] **Step 2: Commit the spec and this plan**

```bash
git add docs/superpowers/specs/2026-07-03-deploy-lean-aws-design.md \
        docs/superpowers/plans/2026-07-03-deploy-lean-aws.md
git commit -m "docs: lean AWS deploy design + implementation plan"
```

---

### Task 1: File-SQLite pooling + WAL in `db.py`

**Files:**
- Modify: `app/db.py`
- Test: `tests/test_db_engine.py` (create)

**Interfaces:**
- Produces: `app.db.make_engine(url: str) -> sqlalchemy.Engine` — builds the engine for a given URL. In-memory SQLite keeps `StaticPool`; file SQLite gets `check_same_thread=False` plus a connect-time `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`; Postgres uses `pool_pre_ping=True`. Module-level `engine = make_engine(settings.database_url)` unchanged for consumers.

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_engine.py`:

```python
from sqlalchemy import text


def test_file_sqlite_enables_wal_and_busy_timeout(tmp_path):
    from app.db import make_engine
    eng = make_engine(f"sqlite+pysqlite:///{tmp_path}/t.db")
    with eng.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert c.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_memory_sqlite_still_works():
    from app.db import make_engine
    eng = make_engine("sqlite+pysqlite:///:memory:")
    with eng.connect() as c:
        assert c.execute(text("select 1")).scalar() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db_engine.py -v`
Expected: FAIL with `ImportError: cannot import name 'make_engine'`.

- [ ] **Step 3: Write the implementation**

Replace the engine-construction block in `app/db.py` with:

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    if url.startswith("sqlite"):
        if ":memory:" in url:
            # in-memory (tests): one shared connection across threads
            eng = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # file-backed (prod): normal pooling so workers don't serialise on
            # one connection
            eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            # WAL + busy_timeout so multiple gunicorn workers don't raise
            # "database is locked". WAL is a no-op on :memory: (stays "memory").
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

        return eng
    return create_engine(url, pool_pre_ping=True)


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
```

Keep the existing `init_db()` and `get_session()` functions below unchanged.

- [ ] **Step 4: Run the new test and the full suite**

Run: `.venv/bin/python -m pytest tests/test_db_engine.py -v && .venv/bin/python -m pytest -q`
Expected: new tests PASS; full suite still green.

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db_engine.py
git commit -m "feat: file-SQLite WAL + busy_timeout for multi-worker prod"
```

---

### Task 2: Storage-agnostic download; delete `presign_get`

**Files:**
- Modify: `app/api.py` (endpoint `api_download`, lines ~107-115)
- Modify: `app/storage.py` (remove `presign_get`)
- Modify: `tests/test_storage.py`, `tests/test_api.py`, `tests/test_api_v2.py`, `tests/test_install_visibility.py`

**Interfaces:**
- Consumes: `setups.install(db, slug, user) -> {"slug", "version", "files", "effects"}` (unchanged).
- Produces: `POST /api/setups/{slug}/download` now returns the full install dict (`files` inline), matching the MCP `install_setup` tool. `storage.presign_get` no longer exists.

- [ ] **Step 1: Update the tests to the new response shape (failing)**

In `tests/test_api.py` change the download assertion (line ~116):

```python
    r = client.post("/api/setups/plain-flow/download")
    assert r.status_code == 200
    assert "files" in r.json()
```

In `tests/test_api_v2.py` `test_authenticated_download_records_pull` (line ~47):

```python
    body = r.json()
    assert "files" in body
```

In `tests/test_install_visibility.py` both success assertions (lines ~100 and ~114):

```python
    assert "files" in r.json()
```

In `tests/test_storage.py`: delete `test_presign_returns_url` entirely, and remove the final `presign_get` assertion (line 19) from `test_local_disk_backend_roundtrip` so it ends at the `get_archive` check:

```python
def test_local_disk_backend_roundtrip(tmp_path, monkeypatch):
    # No S3/moto: with STORAGE_DIR set, bundles round-trip through the local dir.
    from app import storage
    monkeypatch.setattr(storage.settings, "storage_dir", str(tmp_path))
    storage.put_archive("b/v1.tar.gz", b"local-bytes")
    assert (tmp_path / "b" / "v1.tar.gz").read_bytes() == b"local-bytes"
    assert storage.get_archive("b/v1.tar.gz") == b"local-bytes"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_api.py tests/test_api_v2.py tests/test_install_visibility.py tests/test_storage.py -q`
Expected: FAIL — download tests still see `{"url": ...}` (no `files`), and `test_presign_returns_url`/import references break.

- [ ] **Step 3: Implement the endpoint change**

In `app/api.py`, replace `api_download`:

```python
@router.post("/api/setups/{slug}/download")
def api_download(slug: str, user: User = Depends(current_user), db: Session = Depends(get_session)):
    try:
        # increments downloads + records a pull; returns {slug, version, files, effects}
        return setups.install(db, slug, user)
    except setups.NotFound:
        raise HTTPException(status_code=404, detail="not found")
```

Remove the now-unused `from .storage import presign_get` line inside the old function body.

- [ ] **Step 4: Delete `presign_get` from `app/storage.py`**

Remove the entire `presign_get` function (lines ~32-41). `put_archive`/`get_archive` and `_client`/`_local_path` stay.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_api.py tests/test_api_v2.py tests/test_install_visibility.py tests/test_storage.py -q && .venv/bin/python -m pytest -q`
Expected: PASS; full suite green.

- [ ] **Step 6: Commit**

```bash
git add app/api.py app/storage.py tests/test_api.py tests/test_api_v2.py tests/test_install_visibility.py tests/test_storage.py
git commit -m "feat: storage-agnostic download (inline files); drop presign_get"
```

---

### Task 3: Provisioning scripts (setup, redeploy, Caddy, systemd)

**Files:**
- Create: `deploy/setup.sh`
- Create: `deploy/redeploy.sh`
- Create: `deploy/Caddyfile`
- Modify: `deploy/dothub.service`

**Interfaces:**
- `setup.sh` is run once as root on a fresh Ubuntu 24.04 box; idempotent.
- Env file lives at `/etc/dothub.env`; repo at `/opt/dothub`; venv at `/opt/dothub/.venv`; data at `/var/lib/dothub`.

- [ ] **Step 1: Write `deploy/dothub.service`**

```ini
[Unit]
Description=dothub
After=network.target

[Service]
User=dothub
WorkingDirectory=/opt/dothub
EnvironmentFile=/etc/dothub.env
ExecStart=/opt/dothub/.venv/bin/gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write `deploy/Caddyfile`**

```
# Replace dothub.nl with your domain. Caddy fetches + auto-renews the TLS cert
# once DNS points at this box; it retries until DNS resolves.
dothub.nl {
    reverse_proxy localhost:8000
}
```

- [ ] **Step 3: Write `deploy/setup.sh`**

```bash
#!/usr/bin/env bash
# One-time provisioning for a fresh Ubuntu 24.04 EC2 box. Idempotent: safe to
# re-run. Run as root:  sudo DOMAIN=dothub.nl bash deploy/setup.sh
# For a private repo, also pass GITHUB_TOKEN=... (read-only fine-grained token).
set -euo pipefail

DOMAIN="${DOMAIN:-dothub.nl}"
REPO_URL="${REPO_URL:-https://github.com/catancs/dothub.git}"
if [ -n "${GITHUB_TOKEN:-}" ]; then
  REPO_URL="https://${GITHUB_TOKEN}@github.com/catancs/dothub.git"
fi
APP_DIR=/opt/dothub
DATA_DIR=/var/lib/dothub
ENV_FILE=/etc/dothub.env

# --- system packages ---
apt-get update -y
apt-get install -y python3-venv python3-pip git curl \
  debian-keyring debian-archive-keyring apt-transport-https

# --- Caddy (official apt repo) ---
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

# --- app user + dirs ---
id -u dothub >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin dothub
mkdir -p "$DATA_DIR/bundles" "$DATA_DIR/backups"

# --- code ---
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

# --- venv + deps ---
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# --- env file (generate secret once) ---
if [ ! -f "$ENV_FILE" ]; then
  SECRET="$(openssl rand -hex 32)"
  cat > "$ENV_FILE" <<EOF
DATABASE_URL=sqlite+pysqlite:///$DATA_DIR/dothub.db
STORAGE_DIR=$DATA_DIR/bundles
BASE_URL=https://$DOMAIN
SESSION_SECRET=$SECRET
AWS_REGION=eu-north-1
EOF
  chmod 600 "$ENV_FILE"
fi

chown -R dothub:dothub "$APP_DIR" "$DATA_DIR"

# --- migrations ---
sudo -u dothub env $(grep -v '^#' "$ENV_FILE" | xargs) \
  "$APP_DIR/.venv/bin/alembic" -c "$APP_DIR/alembic.ini" upgrade head

# --- services ---
install -m 644 "$APP_DIR/deploy/dothub.service" /etc/systemd/system/dothub.service
sed "s/dothub\\.nl/$DOMAIN/" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now dothub
systemctl reload caddy || systemctl restart caddy

echo "Done. App on :8000 behind Caddy for https://$DOMAIN"
```

- [ ] **Step 4: Write `deploy/redeploy.sh`**

```bash
#!/usr/bin/env bash
# Pull latest and restart. Run as root on the box: sudo bash deploy/redeploy.sh
set -euo pipefail
APP_DIR=/opt/dothub
ENV_FILE=/etc/dothub.env
git -C "$APP_DIR" pull --ff-only
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo -u dothub env $(grep -v '^#' "$ENV_FILE" | xargs) \
  "$APP_DIR/.venv/bin/alembic" -c "$APP_DIR/alembic.ini" upgrade head
chown -R dothub:dothub "$APP_DIR"
systemctl restart dothub
echo "Redeployed."
```

- [ ] **Step 5: Syntax-check the scripts**

Run: `bash -n deploy/setup.sh && bash -n deploy/redeploy.sh && echo OK`
Expected: `OK` (no syntax errors).

- [ ] **Step 6: Commit**

```bash
chmod +x deploy/setup.sh deploy/redeploy.sh
git add deploy/setup.sh deploy/redeploy.sh deploy/Caddyfile deploy/dothub.service
git commit -m "feat: lean single-box provisioning (setup/redeploy/Caddy/systemd)"
```

---

### Task 4: Remove old infra and rewrite the runbook

**Files:**
- Delete: `infra/` (entire Terraform module), `deploy/nginx.conf`
- Modify: `deploy/DEPLOY.md`

- [ ] **Step 1: Remove the old stack**

```bash
git rm -r infra
git rm deploy/nginx.conf
```

- [ ] **Step 2: Rewrite `deploy/DEPLOY.md`**

Replace the file contents with a lean runbook covering: launching one EC2 `t4g.small` in the default VPC (documented `aws ec2 run-instances` with a security group opening 22-from-your-IP and 80/443, plus an Elastic IP), running `sudo DOMAIN=dothub.nl bash deploy/setup.sh` on the box (after `git clone` or rsync), pointing the `dothub.nl` A record at the Elastic IP, the smoke test (feed renders, signup, mint `dh_` key, publish via API, `/s/<slug>` renders, `claude mcp add … /mcp/`, `install_setup` returns files, `POST /download` returns files inline), operating (`journalctl -u dothub -f`, `redeploy.sh`), backups (nightly `sqlite3 .backup` cron + a daily EBS snapshot via a DLM policy), and teardown (terminate instance + release EIP). Carry over the CSRF known-limitation caveat from the old runbook.

- [ ] **Step 3: Verify no dangling references**

Run: `grep -rn "infra/\|nginx\|certbot\|RDS\|terraform" deploy/DEPLOY.md README.md || echo "no stale refs"`
Expected: no references to the removed stack remain (or only intentional historical mentions).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: rewrite deploy runbook for lean single-box; remove Terraform+nginx"
```

---

## Self-Review

**Spec coverage:**
- SQLite WAL/pooling → Task 1. ✓
- Storage-agnostic download + delete `presign_get` → Task 2. ✓
- Config env file → Task 3 (`setup.sh` writes `/etc/dothub.env`). ✓
- Provisioning scripts / Caddy / systemd → Task 3. ✓
- Delete `infra/` + `nginx.conf`, rewrite runbook → Task 4. ✓
- Backups (nightly `.backup` + DLM snapshot) → documented in Task 4 runbook. ✓
- Teardown → Task 4 runbook. ✓

**Type consistency:** `make_engine` used consistently (Task 1). Download returns the `setups.install` dict everywhere (Task 2 endpoint + all updated tests assert `"files"`). ✓

**Note on backups:** the nightly cron + DLM policy are documented in the runbook rather than codified as a task deliverable, because both are box-side/AWS-console operations, not repo code. If a repo-committed `deploy/backup.sh` is wanted, add it as a follow-up.

**Deferred (YAGNI):** a deterministic "two concurrent writers don't lock" test is flaky to write; the WAL-mode assertion in Task 1 is the guard that fails if the PRAGMA wiring breaks.
