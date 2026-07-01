variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-central-1"
}

variable "domain" {
  description = "The domain that will point at the instance. Used for the nginx server_name and BASE_URL, for example dothub.example.com."
  type        = string
}

variable "admin_cidr" {
  description = "Your IP as a /32 for SSH access, for example 1.2.3.4/32."
  type        = string
}

variable "ssh_public_key" {
  description = "Contents of your SSH public key (for example the text of ~/.ssh/id_ed25519.pub). Used to create the key pair for the ubuntu user."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type. Default t3.micro is free tier eligible. The AMI filter is amd64, so switching to an ARM type (for example t4g.micro) also requires changing the AMI name filter in main.tf to arm64."
  type        = string
  default     = "t3.micro"
}

variable "db_instance_class" {
  description = "RDS instance class for the Postgres database."
  type        = string
  default     = "db.t4g.micro"
}

variable "bucket_prefix" {
  description = "Prefix for the S3 bucket that stores setup bundles. A random suffix is appended to keep the bucket name globally unique."
  type        = string
  default     = "dothub-bundles"
}
