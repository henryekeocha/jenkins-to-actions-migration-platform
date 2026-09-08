# Root configuration: the artifact store for one service, wired for GitHub Actions OIDC.
#
# Equivalent to the XArtifactStore composite resource in infra/crossplane/example-xr.yaml.

module "artifact_store" {
  source = "./modules/artifact-store"

  name              = "${var.service_name}-ci"
  versioning        = true
  oidc_provider_arn = var.github_oidc_provider_arn
  github_repository = var.github_repository

  tags = {
    service     = var.service_name
    environment = "ci"
  }
}
