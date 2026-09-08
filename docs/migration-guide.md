# Migration guide: Jenkins and Tekton to GitHub Actions

This guide is written against the pipelines in this repo: `legacy/jenkins/Jenkinsfile`,
`legacy/tekton/pipeline.yaml`, and the migrated result in `.github/workflows/orders-api-pipeline.yml`
plus the reusable workflows and composite actions it calls. Run
`tools/migration-analyzer` on any Jenkinsfile to get the checklist of constructs below that
apply to it.

## 1. Concept mapping

| Concept | Jenkins (declarative) | Tekton | GitHub Actions |
|---|---|---|---|
| Pipeline definition | `Jenkinsfile` in repo | `Pipeline` + `Task` CRs in cluster | `.github/workflows/*.yml` in repo |
| Unit of execution | `stage` | `PipelineTask` (task in `spec.tasks`) | `job` |
| Ordered steps inside a unit | `steps { sh ... }` | `steps[]` in a `Task` | `steps[]` in a job |
| Parallelism | `parallel { ... }` | tasks with the same `runAfter` | jobs without a `needs` edge between them; `strategy.matrix` for fan-out |
| Ordering | implicit (stage order) | `runAfter` | `needs` |
| Execution environment | `agent { docker { image } }`, node labels | `steps[].image`, pod templates | `runs-on` + optional `container:`; self-hosted runner labels |
| Reusable logic | shared library (`vars/*.groovy`, `src/`) | `Task` referenced by `taskRef`, Tekton Hub | reusable workflow (`workflow_call`) or composite action (`action.yml`) |
| Parameters | `parameters { choice / booleanParam / string }` | `spec.params` | `workflow_dispatch.inputs`, `workflow_call.inputs` |
| Environment variables | `environment { }` | `steps[].env` | `env:` at workflow, job, or step level |
| Secrets | `credentials('id')`, `withCredentials([...])` | `workspaces` bound to Secrets, `env.valueFrom.secretKeyRef` | `${{ secrets.NAME }}`, environment-scoped secrets, OIDC to cloud providers |
| Conditions | `when { branch / expression / allOf }` | `when` expressions | `if:` with `github.*`, `inputs.*`, `needs.*.result` |
| Manual approval | `input` (with `submitter`) | none; separate `PipelineRun` | `environment:` with required reviewers |
| Mutual exclusion | `lock(resource:)`, `disableConcurrentBuilds()` | none in core | `concurrency:` group |
| Ordering guarantee | `milestone` | none | none; `concurrency` queues, does not skip older runs |
| Artifacts between units | `stash`/`unstash`, `archiveArtifacts` | shared `workspace` (PVC) | `actions/upload-artifact` / `download-artifact` |
| Test reports | `junit` | none in core (results via sidecars/artifacts) | upload the XML; job summaries; third-party reporters |
| Timeouts | `options { timeout }`, `timeout { }` block | `PipelineRun.spec.timeouts` | `timeout-minutes` on job or step |
| Retry | `retry(n) { }` | `retries` on a PipelineTask | no built-in; shell loop or a retry action |
| Triggers | `triggers { cron / pollSCM }`, webhooks | Tekton Triggers (EventListener, TriggerBinding) | `on: push / pull_request / schedule / workflow_dispatch / repository_dispatch` |
| Post-build actions | `post { always / success / failure / unstable }` | `finally` tasks with `$(tasks.status)` | a job with `if: always()` inspecting `needs.*.result` |
| Build retention | `buildDiscarder(logRotator)` | none | repo settings (log retention), `retention-days` on artifacts |
| Console options | `timestamps()`, `ansiColor()` | none needed | timestamps and colour are always on |

## 2. Stage-by-stage walkthrough of the orders-api pipeline

### Checkout and Build

Jenkins `checkout scm` + `stash` + `go build` + `archiveArtifacts` becomes `reusable-build.yml`:
`actions/checkout`, a `go-build` composite action, `actions/upload-artifact`. There is no stash;
every job checks out the repo itself, and anything a later job needs is an uploaded artifact
or a job output (`short-sha` here).

The `agent { docker { image 'golang:1.22' ... } }` block goes away. `actions/setup-go` installs
the toolchain on the runner. If you really need to run inside an image, use `container:` on the
job, but you lose the `-v /var/run/docker.sock` mount either way; see "Docker socket" below.

### Test

`parallel { Unit; Lint; SAST }` becomes two jobs in `reusable-test.yml` with no `needs` between
them. The `SKIP_TESTS` parameter becomes a `skip-tests` boolean input applied with `if:` on each
job. The SAST stage's `withSonarQubeEnv` plugin wrapper has no direct port; it would become the
SonarSource action with `SONAR_TOKEN` as a secret, and is left out of the reusable workflow on
purpose because it is vendor-specific.

`junit` has no built-in equivalent. Upload the reports as an artifact. If you want results in
the UI, use a reporter action or write a job summary. Note Jenkins' `UNSTABLE` result (tests
failed, build otherwise fine) does not exist; a failing test fails the job.

### Image

The Jenkins stage does `docker login`, `docker build`, `docker push` against a mounted socket
with a stored username/password credential. `reusable-image.yml` uses `docker/login-action`
with `GITHUB_TOKEN` (`packages: write`), `docker/metadata-action` for tags and labels, and
`docker/build-push-action` with GitHub Actions layer cache. No socket mount, no stored
registry password when pushing to GHCR.

Tekton's version of this is the kaniko task, which already avoided the socket; the Actions
version is closer to that than to the Jenkins one.

### Deploy staging

`deployHelm(...)` and `smokeTest(...)` from the shared library become the `helm-deploy` and
`smoke-test` composite actions, called from `reusable-deploy.yml`. The kubeconfig moves from a
Jenkins file credential to an environment-scoped secret (`KUBECONFIG_B64`), so staging and
production each get their own and a workflow running for staging cannot read production's.

### Approve production, Deploy production

Three Jenkins constructs collapse into two GitHub features:

- `input message: 'Promote to production?', submitter: 'release-managers'` becomes the
  `production` environment with required reviewers. The reviewer list is configured in repo
  settings, not the workflow file, so it is not visible in code review; that is the main
  behavioural difference.
- `timeout(time: 24, unit: 'HOURS') { input ... }` has no direct equivalent. A pending
  deployment waits up to 30 days; use the environment's wait timer if you want a delay, or
  cancel the run.
- `lock(resource: 'production-deploy')` becomes `concurrency: { group: deploy-orders-api-production }`
  with `cancel-in-progress: false`. `milestone` (skip older queued runs when a newer one passes
  the milestone) does not exist. `concurrency` queues at most one pending run and cancels the
  rest, which is the opposite behaviour, so document that when migrating.

### post { }

`post { success / failure / unstable }` becomes the `notify` job: `needs` on every other job,
`if: always()`, and a step that derives an overall status from `needs.*.result`. `emailext`
has no built-in port; GitHub sends its own failure emails, and anything richer is a
marketplace action.

## 3. Things that need a human decision

These are the items `migration-analyzer` reports as `manual`. None of them can be translated
mechanically.

**Docker socket.** `-v /var/run/docker.sock:/var/run/docker.sock` is a security decision as much
as a technical one. On GitHub-hosted runners Docker is available directly, so most uses of the
socket (building images) just work without it. Anything that needed the socket for other reasons
(testcontainers, DinD sidecars) needs an explicit look.

**Shared library classes under `src/`.** `vars/` steps map to composite actions or reusable
workflows one to one. Classes under `src/` (`org.example.ImageName` here) have no place to go;
either inline the logic in a step or turn it into a small CLI the actions call.

**`credentials()` IDs.** Every Jenkins credential ID needs an equivalent secret created in the
right scope (repository, environment, or organisation) and the workflow needs the matching
`${{ secrets.NAME }}` reference. The analyzer lists every ID it finds. Prefer OIDC federation
for cloud providers over long-lived keys.

**`input` with `submitter`.** Decide which GitHub environment models each gate and who the
required reviewers are. Two gates in one pipeline means two environments.

**`lock` and `milestone`.** Decide whether "queue and run in order" (what `concurrency` gives
you) or "run only the latest" (`cancel-in-progress: true`) matches what the lock was for.

**`cron` with `H`.** Actions has no hash-based scheduling; pick a fixed minute. Scheduled
workflows only run on the default branch.

**`pollSCM`.** Delete it. Push events replace polling.

**Plugin steps.** `slackSend`, `emailext`, `withSonarQubeEnv`, `junit` and similar plugin steps
each need a marketplace action or a curl. The analyzer lists them.

## 4. Migrating from Tekton instead

Tekton pipelines are already structured as a DAG of container steps, so the mapping is
shorter:

- `Task` with one image per step becomes a composite action (steps run on the runner) or a job
  with `container:` (steps run in the image).
- `workspaces` shared across tasks become artifacts, or a single job when the sharing is
  tight.
- `params` become inputs; `results` become step or job outputs.
- `when` expressions become `if:`.
- `finally` becomes an `if: always()` job.
- Tekton Triggers (`EventListener`, `TriggerBinding`, `TriggerTemplate`) are replaced entirely
  by the `on:` block.
- The kaniko task becomes `docker/build-push-action`.

What you lose: running inside the cluster with pod-level identity (workload identity, network
policy, in-cluster service access). For steps that genuinely need that, keep them in-cluster
as an Argo Workflow (see `workflows/argo/`) and have the GitHub workflow submit it.

## 5. Migration order that has worked

1. Run the analyzer, get the checklist, and create the secrets and environments it names.
2. Port the shared library to composite actions first, since everything depends on them.
3. Wire `build` and `test` reusable workflows and run them on pull requests alongside Jenkins.
4. Add `image` once you trust the tests; push to a separate tag prefix while Jenkins still
   deploys.
5. Move `deploy` to staging, then production, then turn the Jenkins job off.
6. Delete `pollSCM`, the Jenkins webhook, and the Jenkins credentials last.
