#!/usr/bin/env bash
set -euxo pipefail

# dothub provisioning. Output is captured in /var/log/cloud-init-output.log.
export DEBIAN_FRONTEND=noninteractive

# 1. System packages.
apt-get update
apt-get install -y python3-venv python3-pip git nginx certbot python3-certbot-nginx

# 2. Application user. Home is /opt/dothub but the directory is created by the
#    git clone below, so we do not pass --create-home (that would pre-populate
#    the directory and make the clone fail).
if ! id dothub >/dev/null 2>&1; then
  useradd --system --home-dir /opt/dothub --shell /usr/sbin/nologin dothub
fi

# 3. Clone the app and build the virtualenv. Everything is done as root, then
#    ownership is handed to the dothub user at the end.
git clone https://github.com/catancs/dothub /opt/dothub
python3 -m venv /opt/dothub/venv
/opt/dothub/venv/bin/pip install --upgrade pip
/opt/dothub/venv/bin/pip install -r /opt/dothub/requirements.txt

# 4. Environment file. These keys mirror app/config.py exactly. STORAGE_DIR is
#    intentionally NOT set: unset means the app uses real S3 (the v2 switch).
cat > /opt/dothub/.env <<'ENVEOF'
DATABASE_URL=${db_url}
S3_BUCKET=${bucket}
AWS_REGION=${region}
BASE_URL=https://${domain}
SESSION_SECRET=${session_secret}
MAX_BUNDLE_BYTES=5242880
ENVEOF

# Ownership and permissions after all files exist.
chown -R dothub:dothub /opt/dothub
chmod 600 /opt/dothub/.env

# 5. systemd service (reused from the repo, not rewritten).
cp /opt/dothub/deploy/dothub.service /etc/systemd/system/dothub.service
systemctl daemon-reload
systemctl enable --now dothub

# 6. nginx site. Substitute the real domain into the reused nginx.conf, enable
#    it, and drop the default site. TLS is added later by certbot (see the
#    runbook); we do not run certbot here because DNS is not pointed yet.
sed "s/your-domain.example/${domain}/" /opt/dothub/deploy/nginx.conf > /etc/nginx/sites-available/dothub
ln -sf /etc/nginx/sites-available/dothub /etc/nginx/sites-enabled/dothub
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
