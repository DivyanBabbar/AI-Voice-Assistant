# modules/storage/outputs.tf

output "recordings_bucket_name" {
  description = "Name of the recordings S3 bucket."
  value       = aws_s3_bucket.recordings.bucket
}

output "recordings_bucket_arn" {
  description = "ARN of the recordings S3 bucket."
  value       = aws_s3_bucket.recordings.arn
}

output "exports_bucket_name" {
  description = "Name of the exports S3 bucket."
  value       = aws_s3_bucket.exports.bucket
}

output "exports_bucket_arn" {
  description = "ARN of the exports S3 bucket."
  value       = aws_s3_bucket.exports.arn
}
