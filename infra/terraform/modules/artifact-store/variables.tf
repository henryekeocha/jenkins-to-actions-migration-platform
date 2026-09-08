variable "name" {
  description = "Base name for the bucket and role. The bucket gets a random suffix for global uniqueness."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,40}[a-z0-9]$", var.name))
    error_message = "name must be 3-42 lowercase alphanumeric characters or hyphens."
  }
}

variable "versioning" {
  description = "Enable bucket versioning."
  type        = bool
  default     = true
}

variable "trusted_principal_arns" {
  description = "IAM principals allowed to assume the access role (for example a CI role or an EKS pod identity role)."
  type        = list(string)
  default     = []
}

variable "oidc_provider_arn" {
  description = "Optional GitHub Actions OIDC provider ARN. When set, workflows from `github_repository` can assume the role via web identity."
  type        = string
  default     = null
}

variable "github_repository" {
  description = "owner/repo allowed to assume the role via GitHub OIDC. Required when oidc_provider_arn is set."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
