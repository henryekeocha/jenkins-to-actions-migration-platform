# Terraform: S3 + IAM artifact store

The same S3 bucket and IAM role baseline as `../crossplane`, as a Terraform module
(`modules/artifact-store`) with a root configuration that instantiates it for `orders-api` and
trusts GitHub Actions via OIDC.

**Validate-only.** CI runs `terraform fmt -check` and `terraform validate` with
`-backend=false`. There is no backend, no state, no credentials, and nothing here has been
applied. See `docs/terraform-vs-crossplane.md` for when you would pick this over the
Composition.

```
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform/modules/artifact-store init -backend=false && terraform -chdir=infra/terraform/modules/artifact-store validate
```

Resources: `aws_s3_bucket`, versioning, SSE-S3 encryption, public access block, ownership
controls, an IAM role whose trust policy is built from `trusted_principal_arns` and/or a GitHub
OIDC provider, a least-privilege bucket policy, and the attachment.
