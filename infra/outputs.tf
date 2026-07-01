output "site_ip" {
  description = "Point your domain A record here."
  value       = aws_eip.app.public_ip
}

output "rds_endpoint" {
  description = "RDS Postgres endpoint (host:port). Reachable only from the app security group."
  value       = aws_db_instance.main.endpoint
}

output "s3_bucket" {
  description = "Name of the S3 bucket that stores setup bundles."
  value       = local.bucket_name
}

output "ssh" {
  description = "SSH command to reach the instance."
  value       = "ssh ubuntu@${aws_eip.app.public_ip}"
}

output "next_steps" {
  description = "What to do after apply."
  value       = <<-EOT
    1. Create a DNS A record for ${var.domain} pointing at ${aws_eip.app.public_ip}.
    2. SSH in and provision TLS: ssh ubuntu@${aws_eip.app.public_ip} then run: sudo certbot --nginx -d ${var.domain}
    3. Open https://${var.domain}
  EOT
}
