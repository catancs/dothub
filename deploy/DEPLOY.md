# AWS deployment runbook

## 1. S3
- Create bucket `dothub-bundles` (block public access ON — access only via the app's IAM role).

## 2. RDS
- Postgres instance, db `dothub`. Note the endpoint.
- Security group `sg-rds`: inbound 5432 **only** from `sg-app` (below).

## 3. EC2
- Ubuntu instance. Security group `sg-app`: inbound 22 from *your IP only*, 80+443 from anywhere.
- Attach an **IAM instance role** with `s3:GetObject`/`s3:PutObject` on `arn:aws:s3:::dothub-bundles/*`.

## 4. App
```bash
sudo useradd -m -d /opt/dothub dothub
sudo -u dothub git clone <repo> /opt/dothub && cd /opt/dothub
sudo -u dothub python3 -m venv venv && sudo -u dothub venv/bin/pip install -r requirements.txt
# write /opt/dothub/.env from .env.example (DATABASE_URL → RDS, S3_BUCKET, BASE_URL=https://your-domain, SESSION_SECRET)
sudo cp deploy/dothub.service /etc/systemd/system/ && sudo systemctl enable --now dothub
```

## 5. Nginx + TLS
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/dothub
sudo ln -s /etc/nginx/sites-available/dothub /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.example   # provisions + auto-renews TLS
```

## 6. Smoke test (the deliverable)
```bash
curl https://your-domain.example/healthz          # → {"status":"ok"}
# signup, mint a key, publish, confirm it appears on the feed:
curl -s -X POST https://your-domain.example/api/signup -H 'content-type: application/json' \
  -d '{"username":"me","email":"me@x.com","password":"pw"}' -c jar
KEY=$(curl -s -X POST https://your-domain.example/api/keys -b jar -H 'content-type: application/json' -d '{"label":"cli"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["api_key"])')
curl -s -X POST https://your-domain.example/api/setups -H "Authorization: Bearer $KEY" \
  -H 'content-type: application/json' -d '{"title":"Smoke","description":"","files":{"CLAUDE.md":"hi"}}'
curl -s https://your-domain.example/api/setups   # → includes "smoke"
```
Expected: health ok; publish returns a slug; feed lists it; `https://your-domain.example/s/smoke` renders with the responsibility notice.
