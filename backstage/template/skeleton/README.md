# ${{ values.name }}

${{ values.description }}

Owned by ${{ values.owner }}. Scaffolded from the `go-service-github-actions` template.

## CI/CD

`.github/workflows/ci.yml` calls the platform's reusable workflows:

| Job | What it does |
|---|---|
| build | `go build`, uploads the binary |
| test | unit tests and golangci-lint in parallel |
| image | builds and pushes `ghcr.io/<owner>/${{ values.name }}:<sha>` (not on pull requests) |
| deploy-staging | Helm upgrade into `${{ values.name }}-staging` on every push to `main` |
| deploy-production | same, gated by the `production` environment's required reviewers; run via *Run workflow* |

Before the first deploy, create the `staging` and `production` environments in the repository
settings, add a `KUBECONFIG_B64` secret to each, and add required reviewers to `production`.

## Run locally

```
go run ./cmd/${{ values.name }}
curl localhost:8080/healthz
```
