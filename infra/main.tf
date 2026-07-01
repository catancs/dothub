provider "aws" {
  region = var.region
}

# ---------------------------------------------------------------------------
# Generated secrets. These are consumed by user_data only and are never
# exposed as outputs.
# ---------------------------------------------------------------------------
resource "random_password" "db" {
  length  = 32
  special = false # alphanumeric only, so the DATABASE_URL needs no escaping
}

resource "random_password" "session_secret" {
  length  = 48
  special = false
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  bucket_name = "${var.bucket_prefix}-${random_id.bucket_suffix.hex}"
}

# ---------------------------------------------------------------------------
# Networking: VPC, two public subnets, internet gateway, one route table.
# No NAT gateway (cost); the instance sits directly on a public subnet.
# ---------------------------------------------------------------------------
data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "dothub-vpc"
  }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.20.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "dothub-public-${count.index + 1}"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "dothub-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "dothub-public"
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Security groups.
# ---------------------------------------------------------------------------
resource "aws_security_group" "app" {
  name        = "dothub-app"
  description = "dothub app host: SSH from admin, HTTP and HTTPS from anywhere."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from admin"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "dothub-app"
  }
}

resource "aws_security_group" "rds" {
  name        = "dothub-rds"
  description = "dothub database: Postgres only from the app security group."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from app security group"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "dothub-rds"
  }
}

# ---------------------------------------------------------------------------
# RDS Postgres. Not publicly accessible; reachable only from the app SG.
# ---------------------------------------------------------------------------
resource "aws_db_subnet_group" "main" {
  name       = "dothub-db-subnet"
  subnet_ids = aws_subnet.public[*].id

  tags = {
    Name = "dothub-db-subnet"
  }
}

resource "aws_db_instance" "main" {
  identifier             = "dothub"
  engine                 = "postgres"
  engine_version         = "16" # major only; AWS selects the latest minor
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  storage_type           = "gp3"
  storage_encrypted      = true
  db_name                = "dothub"
  username               = "dothub"
  password               = random_password.db.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # Learning project: teardown friendly. skip_final_snapshot means destroy
  # deletes the data with no final backup. See deploy/DEPLOY.md caveats.
  skip_final_snapshot     = true
  apply_immediately       = true
  backup_retention_period = 1

  tags = {
    Name = "dothub"
  }
}

# ---------------------------------------------------------------------------
# S3 bucket for setup bundles. Public access fully blocked; access is only
# via the EC2 instance role below.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "bundles" {
  bucket = local.bucket_name

  tags = {
    Name = "dothub-bundles"
  }
}

resource "aws_s3_bucket_public_access_block" "bundles" {
  bucket = aws_s3_bucket.bundles.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# IAM: EC2 instance role with least privilege on the bucket objects only.
# app/storage.py does get_object and put_object by exact key, so no
# ListBucket and no bucket-level actions are needed.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "dothub-app"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "s3" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.bundles.arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3" {
  name   = "dothub-s3"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.s3.json
}

resource "aws_iam_instance_profile" "app" {
  name = "dothub-app"
  role = aws_iam_role.app.name
}

# ---------------------------------------------------------------------------
# SSH key pair.
# ---------------------------------------------------------------------------
resource "aws_key_pair" "app" {
  key_name   = "dothub"
  public_key = var.ssh_public_key
}

# ---------------------------------------------------------------------------
# EC2 instance and its elastic IP.
# ---------------------------------------------------------------------------
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name
  key_name               = aws_key_pair.app.key_name

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    db_url         = "postgresql+psycopg://dothub:${random_password.db.result}@${aws_db_instance.main.endpoint}/dothub"
    bucket         = local.bucket_name
    region         = var.region
    domain         = var.domain
    session_secret = random_password.session_secret.result
  })

  user_data_replace_on_change = true

  root_block_device {
    volume_size = 16
    volume_type = "gp3"
  }

  tags = {
    Name = "dothub-app"
  }
}

resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id

  tags = {
    Name = "dothub-app"
  }
}
