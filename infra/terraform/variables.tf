variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-west-1"
}

variable "service_name" {
  description = "Service the artifact store belongs to."
  type        = string
  default     = "orders-api"
}

variable "github_oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC provider in the account, if one exists."
  type        = string
  default     = null
}

variable "github_repository" {
  description = "owner/repo whose workflows may assume the artifact-store role."
  type        = string
  default     = "example-org/orders-api"
}
