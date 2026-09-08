# Backstage integration

Two things live under `backstage/`:

- `catalog-info.yaml` registers this repository as a `Component` and, through a `Location`,
  registers the software template.
- `template/` is a Scaffolder template (`scaffolder.backstage.io/v1beta3`) that creates a Go
  service already wired to the reusable GitHub Actions workflows in `.github/workflows`.

## What the template produces

A new GitHub repository containing:

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | build, test, image, deploy-staging, deploy-production jobs calling this repo's reusable workflows by `@main` reference |
| `cmd/<name>/main.go`, `go.mod` | a minimal HTTP service with `/healthz` so the pipeline has something to build, test and smoke-test |
| `charts/<name>/` | a small Helm chart with `values-staging.yaml` and `values-production.yaml`, which is the layout the `helm-deploy` composite action expects |
| `Dockerfile` | multi-stage, distroless |
| `catalog-info.yaml` | the service's catalog entry with owner and GitHub annotations |

The repo is created private with branch protection on `main`, and the service is registered
in the catalog at the end of the run.

## What it deliberately does not do

- It does not create the `staging` and `production` GitHub environments, their `KUBECONFIG_B64`
  secrets, or the required reviewers on `production`. Those need cluster credentials and a
  human decision about who approves; the template's final step logs the instruction.
- It does not create Jenkins jobs or Tekton resources. New services start on the migrated path.
- It does not create cloud resources. The intended pairing is a second template step, or a
  follow-up PR, that adds an `ArtifactStore` XR (see `infra/crossplane`) to a GitOps repo.

## Template mechanics worth knowing

- `${{ values.x }}` in skeleton files is substituted by the Nunjucks renderer. The skeleton's own
  workflow file needs literal `${{ github.ref }}` expressions for GitHub, so those are written as
  `${{ '${{ github.ref }}' }}`, which renders to the GitHub expression. Path segments are
  substituted too, which is how `cmd/${{values.name}}/` becomes `cmd/orders-api/`.
- `parseRepoUrl` is used to expose the destination owner and repo to the skeleton for the
  `github.com/project-slug` annotation and the image path.
- Parameters use `ui:field: OwnerPicker` (filtered to Groups) and `RepoUrlPicker`
  (`allowedHosts: github.com`); actions are `fetch:template`, `publish:github`,
  `catalog:register` and `debug:log`, all built in.

## Validation

`hack/validate-backstage.py` downloads the upstream JSON schemas for `Entity`, `Component`,
`Location` and `Template` from the `backstage/backstage` repository and validates
`catalog-info.yaml`, `template/template.yaml`, and the skeleton's `catalog-info.yaml` (with
placeholder values substituted). CI also renders the skeleton workflow with placeholders and
runs it through actionlint. The template has not been executed in a running Backstage instance
as part of this repo.
