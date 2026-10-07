# infra/terraform/bootstrap/main.tf
#
# Bootstraps the Terraform remote state backend.
#
# IMPORTANT: This project uses LOCAL state (terraform.tfstate committed to nothing,
# kept on disk only). That is intentional — see the chicken-and-egg explanation in
# README.md. Run this project exactly once, then never run it again.
#
# Resources created here:
#   - S3 bucket  : holds .tfstate files for all other Terraform projects
#   - DynamoDB   : provides state-locking so concurrent applies cannot corrupt state

terraform {
  required_version = ">= 1.7.5"

  # Local state: the whole point of this project is to create the backend that
  # every other project will reference. We cannot store bootstrap state remotely
  # because the remote bucket does not exist yet.
  backend "local" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "hindi-voice-ai"
      ManagedBy   = "terraform-bootstrap"
      Environment = "global"
    }
  }
}

# ─── data sources ─────────────────────────────────────────────────────────────

# Fetch the current AWS account ID at plan time so bucket names are unique globally.
data "aws_caller_identity" "current" {}

# ─── S3 state bucket ──────────────────────────────────────────────────────────

# The central bucket where every Terraform workspace stores its .tfstate file.
resource "aws_s3_bucket" "tfstate" {
  bucket = "tfstate-hindi-voice-ai-${data.aws_caller_identity.current.account_id}"

  # Prevent accidental deletion — Terraform will refuse to destroy this bucket
  # unless you explicitly set lifecycle { prevent_destroy = false } first.
  lifecycle {
    prevent_destroy = true
  }
}

# Enable versioning so that every state write is kept as a recoverable object version.
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block all forms of public access — state files contain sensitive ARNs and resource IDs.
resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encrypt state at rest with SSE-S3 (free, uses AWS-managed keys).
# We use SSE-S3 rather than SSE-KMS to avoid KMS key costs (~$1/month/key).
resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ─── DynamoDB lock table ───────────────────────────────────────────────────────

# Terraform uses this table to acquire a distributed lock before modifying state,
# preventing two simultaneous `terraform apply` runs from corrupting the state file.
resource "aws_dynamodb_table" "tfstate_locks" {
  name         = "tfstate-locks-hindi-voice-ai"
  billing_mode = "PAY_PER_REQUEST" # Free for our volume; no capacity planning needed.
  hash_key     = "LockID"          # Required attribute name — Terraform expects exactly "LockID".

  attribute {
    name = "LockID"
    type = "S"
  }
}
