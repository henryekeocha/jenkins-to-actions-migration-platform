# Success metrics for the migration

Metrics a platform team would agree with stakeholders before starting, with how to measure
each from this repo's tooling. Targets are illustrative; the point is that each one is
measurable without a survey.

## Migration progress

| Metric | Source | Target |
|---|---|---|
| Pipelines migrated / total | count of repos whose `ci.yml` calls the reusable workflows vs. Jenkins job count | 100% of active services in two quarters; archive the rest |
| Open `manual` checklist items per pipeline | `migration-analyzer --format json` summary, tracked per repo over time | 0 before the Jenkins job is disabled |
| Shared-library steps without a composite action | analyzer `shared_library_steps` across all Jenkinsfiles, minus `.github/actions/*` | 0 |
| Jenkins credentials with no GitHub secret equivalent | analyzer `credential_ids` reconciled against org and repo secrets | 0 |
| Jenkins controllers still running | infra inventory | 0, then delete the ASG |

## Pipeline health after migration

| Metric | Source | Target |
|---|---|---|
| Median pipeline duration, push to staging deployed | workflow run timestamps via the GitHub API; compare with Jenkins build history for the same repos | no worse than Jenkins in month 1, 30% better by month 3 (parallel jobs, GHA cache) |
| Success rate on `main` | workflow run conclusions | above 95% excluding cancelled |
| Time from approval to production rollout complete | environment deployment timestamps | under 15 minutes |
| Flaky reruns per week | re-run events on failed jobs | trending down |
| Queue time | `queued` to `in_progress` per job | under 1 minute on hosted runners |

## Platform adoption and reliability

| Metric | Source | Target |
|---|---|---|
| New services created through the Backstage template | scaffolder task history | 100% of new services after launch |
| Time to first green pipeline for a new service | template completion to first successful `ci.yml` run | under 30 minutes |
| Argo workflow completion notifications delivered | `workflow_notifications_total{result="success"}` vs `{result="error"}` from the controller | above 99.9% delivered |
| Notification latency | webhook receipt time minus `finishedAt` in the event | p95 under 30 seconds |
| Self-service resources provisioned | `ArtifactStore` XRs created, time from XR creation to `Ready` | Ready within 5 minutes |

## Cost and risk

| Metric | Source | Target |
|---|---|---|
| CI compute cost per month | Actions minutes billing vs. Jenkins agent fleet cost | at or below Jenkins by month 3 |
| Long-lived cloud credentials in CI | secrets audit; count of AWS keys in GitHub secrets | 0 (OIDC only) |
| Production deploys without an approval record | deployments to `production` environment lacking a reviewer | 0 |
| Pipelines with Docker socket access | analyzer `docker-socket` findings; self-hosted runner config | 0 |

## How the repo supports these

- The analyzer's JSON output is designed to be collected per repo into a dashboard; the
  `summary` block and `credential_ids` list are the inputs to the first table.
- The controller exposes the notification counter on its metrics endpoint for Prometheus.
- The reusable workflows keep job names stable (`build`, `unit`, `lint`, `image`, `deploy`)
  so duration and success-rate queries against the Actions API work across services.
