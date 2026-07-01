# dothub deployment runbook

This deploys dothub (the v2 app: server-rendered web pages plus a remote MCP
server) to AWS with one command using the Terraform module in `infra/`, and
tears it down with one command.

## 1. What gets created

`terraform apply` stands up a self-contained stack: a VPC with two public
subnets and an internet gateway (no NAT gateway), a single EC2 instance
(Ubuntu 24.04) that runs gunicorn behind nginx, an RDS Postgres 16 database
that is not publicly accessible and only reachable from the app security group,
an S3 bucket (all public access blocked) for setup bundles, and an IAM instance
role scoped to `s3:GetObject` and `s3:PutObject` on that bucket only. An elastic
IP is attached so the address is stable across reboots.

Rough cost: near zero for the first year on a new AWS account (t3.micro EC2,
db.t4g.micro RDS, and 20 GB storage are within the free tier). After the free
tier it is roughly USD 23 per month, dominated by the always-on EC2 and RDS
instances. `terraform destroy` stops all of it.

## 2. Prerequisites

- An AWS account with credentials configured locally. Run `aws configure` (from
  the AWS CLI) or export `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Install
  the CLI with `brew install awscli` on macOS or follow the AWS docs.
- Terraform >= 1.6.
- A domain you control (you will point an A record at the instance).
- Your public IP, used to lock down SSH. Find it with
  `curl -s https://checkip.amazonaws.com`.
- An SSH public key, for example `~/.ssh/id_ed25519.pub`. If you do not have one,
  create it with `ssh-keygen -t ed25519`.

## 3. Deploy

```bash
cd infra
terraform init
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set domain, admin_cidr (your IP as /32), and
# ssh_public_key (the contents of your .pub file)
terraform apply
```

Apply takes roughly 10 minutes; RDS is the slow part. When it finishes,
Terraform prints the outputs, including `site_ip` and `next_steps`.

## 4. Point DNS

Create an A record for your domain pointing at the `site_ip` output value. Wait
for it to resolve (`dig +short <your-domain>` should return that IP) before the
next step, since certbot validates over the domain.

## 5. TLS

```bash
ssh ubuntu@<site_ip>
sudo certbot --nginx -d <your-domain>
```

certbot edits the nginx site to serve HTTPS and sets up automatic renewal. It is
run here, after DNS is pointed, rather than during provisioning.

## 6. Smoke test (v2)

1. Open `https://<your-domain>/`. The Discover feed page renders.
2. Sign up at `https://<your-domain>/signup`.
3. Mint an API key on `https://<your-domain>/account` (the key is shown once and
   starts with `dh_`).
4. Publish a setup through the API with your Bearer key:

   ```bash
   curl -s -X POST https://<your-domain>/api/setups \
     -H "Authorization: Bearer dh_your_key_here" \
     -H "content-type: application/json" \
     -d '{"title":"Smoke test","description":"hello","files":{"CLAUDE.md":"# hi"}}'
   ```

   The response includes a `slug`.
5. Confirm it appears on the feed (`https://<your-domain>/` or
   `GET https://<your-domain>/api/setups`) and that `https://<your-domain>/s/<slug>`
   renders, including the effects panel.
6. Add the remote MCP server to Claude Code:

   ```bash
   claude mcp add --transport http dothub https://<your-domain>/mcp/ \
     --header "Authorization: Bearer dh_your_key_here"
   ```

## 7. Operate

- App logs: `journalctl -u dothub -f`.
- Provisioning log (first boot): `/var/log/cloud-init-output.log`.
- Redeploy the app after pushing to GitHub:

  ```bash
  ssh ubuntu@<site_ip>
  cd /opt/dothub
  sudo -u dothub git pull
  sudo systemctl restart dothub
  ```

## 8. Teardown

```bash
cd infra
terraform destroy
```

This removes every resource above and stops billing.

## 9. Caveats

- `terraform.tfstate` and the EC2 user data both contain the generated database
  password and session secret. Keep the state file local and never commit it.
  The `.gitignore` in this repo already excludes `*.tfstate*` and `*.tfvars`.
- RDS is created with `skip_final_snapshot = true`, so `terraform destroy`
  deletes the database and its data permanently with no final backup. This is
  intentional for a learning project that should tear down cleanly. Change it
  before storing anything you care about.
- The session cookie is not yet marked `https_only`. A future hardening pass
  should set that once the app always runs behind TLS.
