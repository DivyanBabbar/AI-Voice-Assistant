# infra/terraform/main/outputs.tf

output "vpc_id" {
  description = "ID of the main VPC."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the two public subnets (one per AZ)."
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the two private subnets (one per AZ)."
  value       = module.network.private_subnet_ids
}

output "recordings_bucket_name" {
  description = "Name of the recordings S3 bucket."
  value       = module.storage.recordings_bucket_name
}

output "exports_bucket_name" {
  description = "Name of the exports S3 bucket."
  value       = module.storage.exports_bucket_name
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions Terraform CI IAM role."
  value       = module.iam.github_actions_role_arn
}
