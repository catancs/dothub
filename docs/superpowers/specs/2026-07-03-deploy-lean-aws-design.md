# dothub deploy — lean AWS design

Date: 2026-07-03
Status: approved (design review), pending implementation plan
Scope: production deployment of the dothub v2 app to AWS on a single box.
Replaces the previous `infra/` Terraform stack (VPC + EC2 + RDS + S3 + IAM +
nginx + certbot), which is deleted.

## Context

dothub is a FastAPI app that serves both a server-rendered web feed and a
remote MCP server, so an agent can publish and pull whole Claude Code setups
itself. It is a personal side project (unrelated to LongevAI) on a fresh AWS
account with a credit-based Free Plan: ~$100 in credits expiring when depleted
or ~2027-01-03, whichever comes first. Access to services stops when credits
run out — the plan does not surprise-bill — so the deploy is optimised for low
monthly burn and clean teardown, not for scale.

The app is already fully env-var driven and ships two escape hatches that make
a minimal deploy possible with no architectural change:

- `db.py` branches on the `DATABASE_URL` scheme and already supports SQLite as
  well as Postgres.
- `storage.py` has a local-disk backend (`STORAGE_DIR`) that bypasses S3/boto3
  entirely. `put_archive`/`get_archive` work identically on either backend.
- `config.py` fails closed: it refuses to boot on HTTPS with the dev session
  secret, so a real `SESSION_SECRET` is mandatory in prod.

The core product loop confirms local disk is sufficient: MCP `install_setup` →
`setups.install()` reads the archive bytes server-side and returns the `files`
inline. It never uses presigned URLs. Only the HTTP `POST
/api/setups/{slug}/download` endpoint assumes S3 (it returns a presigned URL,
which degrades to a useless `file://` on local disk), and nothing in the web UI
calls that endpoint.

## Goals

- Run dothub in production on the smallest AWS footprint that is correct: one
  EC2 instance, app on local disk, automatic HTTPS.
- Keep the app code backend-agnostic (no code coupling to SQLite/local-disk;
  the same code can later flip back to Postgres/S3 via env vars).
- Make provisioning transparent and re-runnable — a shell script the operator
  can read and edit, not opaque declarative state that assumes AWS is already
  wired.
- Guard against data loss (nightly SQLite backup + EBS snapshot).
- Keep the credit burn low and teardown a one-liner.

## Non-goals

- RDS / managed Postgres. A single low-traffic box uses SQLite on disk. Flip to
  Postgres via `DATABASE_URL` if concurrency ever demands it.
- S3 / object storage. Bundles live on the instance disk via `STORAGE_DIR`.
- Custom VPC, NAT gateway, IAM instance roles. The instance runs in the
  account's default VPC and needs no AWS API access at runtime.
- nginx + certbot. Caddy provides the reverse proxy and automatic TLS.
- Terraform. Provisioning is a shell script. (Tiny Terraform for one-command
  `destroy` is noted as an alternative but not chosen.)
- Docker. The app runs directly under systemd in a venv; no image build/push.
- Horizontal scale, autoscaling, multi-AZ, load balancer. Out of scope for a
  personal deploy.

## Architecture

One EC2 instance, everything on it:

```
                 Internet
                    |
             :443 / :80  (security group: 80,443 from world; 22 from admin IP)
                    |
                 Caddy  ── automatic Let's Encrypt TLS, reverse_proxy → :8000
                    |
         gunicorn (2 uvicorn workers)  ── systemd unit `dothub`, env /etc/dothub.env
                    |
              FastAPI app (app.main:app)
                    |
        /var/lib/dothub/            (EBS root volume)
          dothub.db                 SQLite, WAL mode
          bundles/<key>.tar.gz      setup archives (STORAGE_DIR)
          backups/                  nightly .backup + bundle tarballs (keep 7)
```

- **Instance:** Ubuntu 24.04, ARM `t4g.small` (2 GB) in the default VPC, with
  an Elastic IP for a stable address.
- **Security group:** 22 from the operator's `/32` only; 80 and 443 from
  anywhere.
- **No runtime AWS dependency:** the app talks only to its local disk. AWS CLI
  creds are needed only for provisioning/backup snapshots from the operator
  side, not by the running app.

## Code changes

Two small edits, both correctness improvements rather than deploy glue.

### 1. `db.py` — SQLite pooling + WAL for a file database

Current code applies `StaticPool` (a single shared connection) to *all* SQLite
URLs. That is correct for the in-memory test DB but serialises every request
against a file DB and does not enable WAL, so concurrent gunicorn workers can
raise `database is locked`.

Change: keep `StaticPool` only for in-memory URLs (`:memory:`). For a file
SQLite URL, use the default pool with `check_same_thread=False`, and on connect
set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` (via a SQLAlchemy
`connect` event or `create_engine(..., connect_args=...)` plus an event
listener). Postgres path is unchanged.

Runnable check: a small `test_sqlite_wal.py` asserting that a file-backed engine
reports `journal_mode == "wal"` and that two concurrent writers do not raise
`OperationalError: database is locked`.

### 2. `api.py` — storage-agnostic download; delete `presign_get`

`POST /api/setups/{slug}/download` currently returns `presign_get(...)`.
`setups.install()` already returns the unpacked `files` in its result dict.

Change: return the files inline, e.g. `{"files": res["files"], "version":
res["version"]}` — matching what the MCP `install_setup` tool already does.
Remove `presign_get` from `storage.py` (now unused) and its import in `api.py`.
Update `tests/` for the new response shape. Bundles are capped at
`MAX_BUNDLE_BYTES` (5 MB), so inline JSON is bounded.

No other app code changes. Postgres and S3 remain reachable purely by setting
`DATABASE_URL` / unsetting `STORAGE_DIR`; nothing is hard-removed from the code
paths beyond the dead presign helper.

## Configuration

`/etc/dothub.env`, read by the systemd unit:

```
DATABASE_URL=sqlite+pysqlite:////var/lib/dothub/dothub.db
STORAGE_DIR=/var/lib/dothub/bundles
BASE_URL=https://dothub.nl
SESSION_SECRET=<64+ random chars, generated at first setup>
AWS_REGION=eu-north-1        # unused at runtime; harmless default
```

The four-slash SQLite URL is an absolute path. `SESSION_SECRET` is generated
once by `setup.sh` (`openssl rand -hex 32`) and never committed.

## Provisioning

Replaces the whole `infra/` directory. New files under `deploy/`:

- **`deploy/setup.sh`** — idempotent, run once on a fresh instance (or via EC2
  user-data on first boot). Steps: apt install `python3-venv`, `caddy` (from the
  Caddy apt repo), and `git`; create a `dothub` system user; clone the repo to
  `/opt/dothub`; create a venv and `pip install -r requirements.txt`; create
  `/var/lib/dothub/{bundles,backups}`; write `/etc/dothub.env` (generating
  `SESSION_SECRET` if absent); install the systemd unit and Caddyfile; run
  `alembic upgrade head`; enable + start `dothub` and `caddy`.
- **`deploy/redeploy.sh`** — `git pull`, `pip install -r requirements.txt`,
  `alembic upgrade head`, `systemctl restart dothub`.
- **`deploy/dothub.service`** — systemd unit (adapt the existing one):
  `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8000`,
  `EnvironmentFile=/etc/dothub.env`, `User=dothub`, `WorkingDirectory=/opt/dothub`,
  `Restart=always`.
- **`deploy/Caddyfile`** — two lines:
  ```
  dothub.nl {
      reverse_proxy localhost:8000
  }
  ```
  Caddy fetches and auto-renews the Let's Encrypt certificate. It retries until
  DNS resolves, so there is no ordering dependency between provisioning and the
  A-record.

Instance launch is a single documented `aws ec2 run-instances` command (default
VPC, the security group above, the Elastic IP, an SSH key) — or the console.
No Terraform state to manage.

Deleted: `infra/` (all Terraform), `deploy/nginx.conf`.

## TLS and DNS

1. After launch, associate the Elastic IP with the instance.
2. Point `dothub.nl` A record → Elastic IP at the DNS host.
3. Caddy obtains the cert automatically once DNS resolves.

If the domain is not ready at deploy time, the app can run on the raw IP over
HTTP first (set `BASE_URL=http://<ip>` — note this relaxes the secure-cookie and
prod-secret gate) and switch to the domain + HTTPS by editing `/etc/dothub.env`
and the Caddyfile later.

## Backups (data-loss guard)

- **Nightly cron** on the box: `sqlite3 /var/lib/dothub/dothub.db ".backup
  /var/lib/dothub/backups/dothub-$(date +%F).db"` (date stamped by cron's shell,
  not committed), plus a tar of `bundles/`. Keep the last 7; delete older. This
  guards against app-level corruption and accidental deletion.
- **Daily EBS snapshot** via an AWS Data Lifecycle Manager policy for offsite
  durability against instance/volume loss. DLM is configured once from the
  operator side and runs in AWS's control plane, so it needs **no AWS
  credentials or IAM role on the instance** — keeping the "no runtime AWS
  dependency" property intact.

Kept deliberately minimal; revisit only when there is data worth more.

## Teardown

Terminate the instance and release the Elastic IP (release matters — AWS bills
for an unattached EIP). `setup.sh` rebuilds the box in minutes from the repo.
Tear down between demo sessions to stretch the credits.

## Cost

- `t4g.small` ≈ $12/mo on-demand (or `t4g.micro` ≈ $6/mo). EBS 8–20 GB,
  snapshots, and the attached EIP are cents.
- $100 credits ≈ 8 months at `t4g.small`, ~16 at `t4g.micro`, longer with
  teardown between sessions.

## Prerequisites and open items

- **AWS credentials** configured locally (`aws configure` with an IAM user's
  access key, not root) so provisioning/launch commands run.
- **Domain:** `dothub.nl` — registration status and DNS host still to be
  confirmed. Does not affect the architecture; only the DNS + TLS step. If not
  registered, deploy to the raw IP first and add the domain later.
- **SSH key** for the instance (`~/.ssh/dothub_ed25519.pub` already generated on
  2026-07-01).

## Verification

Adapt the existing smoke test in `deploy/DEPLOY.md` (rewritten for this design):

1. `https://dothub.nl/` renders the Discover feed.
2. Sign up, mint a `dh_` API key on `/account`.
3. Publish a setup via `POST /api/setups` with the Bearer key; response has a
   `slug`.
4. The setup appears on the feed and `/s/<slug>` renders with the effects panel.
5. `claude mcp add --transport http dothub https://dothub.nl/mcp/ --header
   "Authorization: Bearer dh_..."`; `install_setup(slug)` returns `{files}`.
6. `POST /api/setups/<slug>/download` returns files inline (regression for the
   storage-agnostic change).

## Files touched (summary)

- Edit: `app/db.py`, `app/api.py`, `app/storage.py` (delete `presign_get`),
  `tests/` (download response shape, SQLite WAL check).
- Add: `deploy/setup.sh`, `deploy/redeploy.sh`, `deploy/Caddyfile`; rewrite
  `deploy/dothub.service`, `deploy/DEPLOY.md`.
- Delete: `infra/` (Terraform module), `deploy/nginx.conf`.
