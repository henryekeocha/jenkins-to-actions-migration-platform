provider "aws" {
  region = var.region

  # Credentials come from the environment (OIDC in CI, a profile locally). None are assumed or
  # stored in this repository.

  default_tags {
    tags = {
      project = "jenkins-to-actions-migration-platform"
    }
  }
}
