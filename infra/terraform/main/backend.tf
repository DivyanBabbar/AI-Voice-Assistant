# infra/terraform/main/backend.tf
#
# Remote state backend. This config intentionally hard-codes the bucket name and
# account ID: Terraform backend blocks are evaluated before any provider or data
# source, so variables and data sources are not available here. This is the only
# place in the codebase where the account ID is hard-coded; everywhere else it is
# derived from data.aws_caller_identity.current.

terraform {
  required_version = ">= 1.7.5"

  backend "s3" {
    bucket         = "tfstate-hindi-voice-ai-106281192428"
    key            = "main/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "tfstate-locks-hindi-voice-ai"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
