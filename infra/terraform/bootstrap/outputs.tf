# infra/terraform/bootstrap/outputs.tf
#
# Outputs produced by the bootstrap project.
# These values are needed when configuring the `backend "s3"` block in other projects.

output "state_bucket_name" {
  description = "S3 bucket name for Terraform remote state. Use in backend config."
  value       = aws_s3_bucket.tfstate.id
}

output "state_bucket_region" {
  description = "Region of the state bucket."
  value       = var.aws_region
}

output "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking. Use in backend config."
  value       = aws_dynamodb_table.tfstate_locks.name
}
