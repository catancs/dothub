#!/usr/bin/env bash
# Pull latest and restart. Run as root on the box: sudo bash deploy/redeploy.sh
set -euo pipefail
APP_DIR=/opt/dothub
ENV_FILE=/etc/dothub.env
git -C "$APP_DIR" pull --ff-only
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
cd "$APP_DIR"
DB_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
sudo -u dothub env DATABASE_URL="$DB_URL" \
  "$APP_DIR/.venv/bin/alembic" -c "$APP_DIR/alembic.ini" upgrade head
chown -R dothub:dothub "$APP_DIR"
systemctl restart dothub
echo "Redeployed."
