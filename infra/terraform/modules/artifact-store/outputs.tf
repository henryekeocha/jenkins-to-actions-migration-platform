output "bucket_name" {
  description = "Name of the artifact bucket."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_arn" {
  description = "ARN of the artifact bucket."
  value       = aws_s3_bucket.this.arn
}

output "role_arn" {
  description = "ARN of the role that can read and write the bucket."
  value       = aws_iam_role.access.arn
}
