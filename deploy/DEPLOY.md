# dothub deployment runbook (lean single-box)

This deploys dothub to **one** AWS EC2 instance: the app runs directly under
systemd, SQLite and bundle archives live on the instance disk, and Caddy
provides the reverse proxy with automatic HTTPS. No RDS, no S3, no custom VPC,
no nginx/certbot. Design rationale: `docs/superpowers/specs/2026-07-03-deploy-lean-aws-design.md`.

## 1. What gets created

- One EC2 instance (Ubuntu 24.04, ARM `t4g.small`) in your account's **default
  VPC**.
- One security group: SSH (22) from your IP only; HTTP (80) and HTTPS (443)
  from anywhere.
- One Elastic IP for a stable address.

Cost on the credit-based Free Plan: `t4g.small` ≈ $12/mo (`t4g.micro` ≈ $6/mo);
EBS, snapshots, and the attached EIP are cents. ~$100 credits last roughly
8–16 months, longer if you tear down between sessions.

## 2. Prerequisites

- **AWS credentials** configured locally (`aws configure`) for an **IAM user**
  with an access key — not the root account. Verify with
  `aws sts get-caller-identity`.
- **AWS CLI** and an **SSH key** (`~/.ssh/dothub_ed25519` / `.pub`).
- A **domain** you control (`dothub.nl`); you will add one A record.

## 3. Launch the instance

All from your laptop. The AMI is resolved via Canonical's SSM alias, so it is
never a stale hardcoded ID.

```bash
REGION=eu-north-1
MY_IP=$(curl -s https://checkip.amazonaws.com)

# SSH public key → EC2
aws ec2 import-key-pair --region $REGION --key-name dothub \
  --public-key-material fileb://~/.ssh/dothub_ed25519.pub

# security group in the default VPC
SG_ID=$(aws ec2 create-security-group --region $REGION \
  --group-name dothub --description "dothub web" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --region $REGION --group-id "$SG_ID" \
  --ip-permissions \
    IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges="[{CidrIp=$MY_IP/32}]" \
    IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges="[{CidrIp=0.0.0.0/0}]" \
    IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges="[{CidrIp=0.0.0.0/0}]"

# launch t4g.small on Ubuntu 24.04 arm64
AMI="resolve:ssm:/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id"
IID=$(aws ec2 run-instances --region $REGION \
  --image-id "$AMI" --instance-type t4g.small \
  --key-name dothub --security-group-ids "$SG_ID" \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=20,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=dothub}]' \
  --query 'Instances[0].InstanceId' --output text)

# Elastic IP
ALLOC=$(aws ec2 allocate-address --region $REGION --query AllocationId --output text)
aws ec2 wait instance-running --region $REGION --instance-ids "$IID"
aws ec2 associate-address --region $REGION --instance-id "$IID" --allocation-id "$ALLOC"
EIP=$(aws ec2 describe-addresses --region $REGION --allocation-ids "$ALLOC" \
  --query 'Addresses[0].PublicIp' --output text)
echo "Instance $IID at $EIP"
```

## 4. Provision the box

SSH in and run `setup.sh`. It installs Python + Caddy, clones the repo to
`/opt/dothub`, creates the venv, writes `/etc/dothub.env` (generating a strong
`SESSION_SECRET`), initializes the SQLite schema, stamps the Alembic baseline,
and starts the `dothub` and `caddy` services. It is idempotent.

```bash
ssh -i ~/.ssh/dothub_ed25519 ubuntu@$EIP

# on the box — fetch the bootstrap script; it clones the rest of the repo:
curl -fsSL https://raw.githubusercontent.com/catancs/dothub/main/deploy/setup.sh -o setup.sh
sudo DOMAIN=dothub.nl bash setup.sh
```

Private repo: create a read-only fine-grained GitHub token, pass it to both the
`curl` (`-H "Authorization: token <tok>"`) and `setup.sh`
(`sudo DOMAIN=dothub.nl GITHUB_TOKEN=<tok> bash setup.sh`). Or skip GitHub
entirely and `rsync` your working tree to `/opt/dothub`, then run
`sudo DOMAIN=dothub.nl bash /opt/dothub/deploy/setup.sh`.

## 5. Point DNS

Create an A record for `dothub.nl` → the Elastic IP. Caddy retries certificate
issuance until DNS resolves, so there is no ordering requirement — but HTTPS
goes live only once `dig +short dothub.nl` returns the EIP.

## 6. Smoke test

1. `https://dothub.nl/` renders the Discover feed.
2. Sign up at `/signup`; mint an API key on `/account` (shown once, starts `dh_`).
3. Publish via the API:
   ```bash
   curl -s -X POST https://dothub.nl/api/setups \
     -H "Authorization: Bearer dh_your_key" -H "content-type: application/json" \
     -d '{"title":"Smoke test","description":"hello","files":{"CLAUDE.md":"# hi"}}'
   ```
   The response includes a `slug`.
4. The setup appears on the feed and `https://dothub.nl/s/<slug>` renders with
   the effects panel.
5. Add the remote MCP server and install:
   ```bash
   claude mcp add --transport http dothub https://dothub.nl/mcp/ \
     --header "Authorization: Bearer dh_your_key"
   ```
   `install_setup(<slug>)` returns `{files}`.
6. `POST https://dothub.nl/api/setups/<slug>/download` returns the files inline
   (regression check for the storage-agnostic download).

## 7. Operate

- Logs: `journalctl -u dothub -f` (app), `journalctl -u caddy -f` (TLS/proxy).
- Cloud-init (first boot): `/var/log/cloud-init-output.log`.
- Redeploy after pushing to GitHub:
  ```bash
  ssh -i ~/.ssh/dothub_ed25519 ubuntu@$EIP
  sudo bash /opt/dothub/deploy/redeploy.sh
  ```

## 8. Backups

Data lives in `/var/lib/dothub/` (SQLite `dothub.db` + `bundles/`).

- **Nightly local backup** — add a root cron on the box (guards against
  app-level corruption / accidental deletion):
  ```cron
  15 3 * * * sqlite3 /var/lib/dothub/dothub.db ".backup /var/lib/dothub/backups/dothub-$(date +\%F).db" && \
             tar czf /var/lib/dothub/backups/bundles-$(date +\%F).tgz -C /var/lib/dothub bundles && \
             find /var/lib/dothub/backups -mtime +7 -delete
  ```
- **Daily EBS snapshot** — create an AWS **Data Lifecycle Manager** policy
  targeting the instance's volume (tag `Name=dothub`). DLM runs in AWS's control
  plane, so **no AWS credentials live on the box**. This is the offsite guard
  against instance/volume loss.

## 9. Teardown

Stops all billing; `setup.sh` rebuilds the box in minutes.

```bash
aws ec2 terminate-instances --region $REGION --instance-ids "$IID"
aws ec2 wait instance-terminated --region $REGION --instance-ids "$IID"
aws ec2 release-address --region $REGION --allocation-id "$ALLOC"   # unattached EIPs bill
```

## 10. Caveats

- **Data is on one EBS volume.** The nightly backup + EBS snapshots are the only
  copies. This is intentional for a low-traffic personal deploy; add real
  offsite backups before storing anything you can't lose.
- **SQLite single-box ceiling.** WAL + `busy_timeout` handle the app's low write
  concurrency. If write load ever grows, flip `DATABASE_URL` to Postgres and
  `STORAGE_DIR`→S3 (both still supported in code) — no app rewrite.
- **CSRF (partial).** Session cookies use `SameSite=Lax`, which mitigates
  form-post CSRF. The JSON `/api/*` mutation routes (follow, revert, key mint,
  account) are a residual surface without full CSRF tokens. No mutation moves
  money or deletes data. Full CSRF protection is a planned fast-follow.
