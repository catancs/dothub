#!/usr/bin/env bash
# Pull latest and restart. Run as root on the box: sudo bash deploy/redeploy.sh
set -euo pipefail
APP_DIR=/opt/dothub
ENV_FILE=/etc/dothub.env
cd "$APP_DIR"
# Run git/pip/alembic AS the dothub user (owner of the repo + venv) so Git does
# not reject the pull with "dubious ownership" and files stay dothub-owned.
sudo -u dothub git -C "$APP_DIR" pull --ff-only
sudo -u dothub "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
DB_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
sudo -u dothub env DATABASE_URL="$DB_URL" \
  "$APP_DIR/.venv/bin/alembic" -c "$APP_DIR/alembic.ini" upgrade head
systemctl restart dothub
echo "Redeployed."
