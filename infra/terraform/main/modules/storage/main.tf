# modules/storage/main.tf
#
# Two S3 buckets:
#   recordings-<account-id>  versioned, lifecycle to Glacier IR after 30 days, SSE-S3.
#   exports-<account-id>     private, SSE-S3 only.
#
# KMS encryption is deferred to week 3; SSE-S3 (AES-256) is used now.

# ─── recordings bucket ────────────────────────────────────────────────────────

resource "aws_s3_bucket" "recordings" {
  bucket = "recordings-${var.account_id}"

  tags = merge(var.common_tags, {
    Name    = "recordings-${var.account_id}"
    Purpose = "call-recordings"
  })
}

resource "aws_s3_bucket_versioning" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = false
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  rule {
    id     = "glacier-ir-after-30-days"
    status = "Enabled"

    # Empty prefix = apply to all objects in the bucket.
    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "GLACIER_IR"
    }

    # Permanently delete expired delete markers to keep the bucket tidy.
    expiration {
      expired_object_delete_marker = true
    }

    # Clean up incomplete multipart uploads to avoid orphaned storage charges.
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ─── exports bucket ───────────────────────────────────────────────────────────

resource "aws_s3_bucket" "exports" {
  bucket = "exports-${var.account_id}"

  tags = merge(var.common_tags, {
    Name    = "exports-${var.account_id}"
    Purpose = "report-exports"
    CiTest  = "day-2-plan-smoke"
  })
}

resource "aws_s3_bucket_public_access_block" "exports" {
  bucket = aws_s3_bucket.exports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = false
  }
}
