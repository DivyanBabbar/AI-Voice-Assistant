# infra/terraform/bootstrap/variables.tf
#
# Input variables for the bootstrap project.
# Keep this minimal — bootstrap has no business logic.

variable "aws_region" {
  description = "AWS region for the state backend resources."
  type        = string
  default     = "ap-south-1"
}
