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

# --- app user + data dirs ---
id -u dothub >/dev/null 2>&1 || \
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin dothub
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

# --- env file (generate the session secret once) ---
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

# --- initialize schema + stamp the alembic baseline ---
# The app uses create_all (init_db) as its schema source of truth; the alembic
# baseline is a stamp, not a from-scratch migration (its one revision adds a
# column to an already-existing table). So a fresh DB is created via init_db and
# then stamped to head -- never `upgrade head`, which would fail on the empty DB.
cd "$APP_DIR"
DB_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
sudo -u dothub env DATABASE_URL="$DB_URL" \
  "$APP_DIR/.venv/bin/python" -c "from app.db import init_db; init_db()"
sudo -u dothub env DATABASE_URL="$DB_URL" \
  "$APP_DIR/.venv/bin/alembic" -c "$APP_DIR/alembic.ini" stamp head

# --- services ---
install -m 644 "$APP_DIR/deploy/dothub.service" /etc/systemd/system/dothub.service
sed "s/dothub\.nl/$DOMAIN/" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now dothub
systemctl reload caddy || systemctl restart caddy

echo "Done. App on :8000 behind Caddy for https://$DOMAIN"
