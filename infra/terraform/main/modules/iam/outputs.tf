# modules/iam/outputs.tf

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions Terraform CI role. Set as AWS_ROLE_ARN in GitHub secrets."
  value       = aws_iam_role.github_actions_terraform.arn
}

output "github_actions_role_name" {
  description = "Name of the GitHub Actions Terraform CI role."
  value       = aws_iam_role.github_actions_terraform.name
}
