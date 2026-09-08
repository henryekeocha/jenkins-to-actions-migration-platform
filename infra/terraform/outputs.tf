output "bucket_name" {
  value = module.artifact_store.bucket_name
}

output "role_arn" {
  description = "Set this as AWS_ROLE_ARN in the GitHub environment; aws-actions/configure-aws-credentials assumes it."
  value       = module.artifact_store.role_arn
}
