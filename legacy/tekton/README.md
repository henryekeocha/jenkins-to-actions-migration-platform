# Legacy Tekton pipeline

The same orders-api build-test-deploy flow as `../jenkins/Jenkinsfile`, expressed as a Tekton
`Pipeline` (`tekton.dev/v1`) plus the `Task`s it references and a sample `PipelineRun`.

Mapping from the Jenkins pipeline:

| Jenkins | Tekton |
|---|---|
| `stage` | `tasks[]` entry with `taskRef` |
| `parallel` | tasks sharing the same `runAfter` |
| `when { branch / expression }` | `when` expressions on the task |
| `agent { docker { image } }` | `steps[].image` on each Task |
| shared-library step (`deployHelm`) | reusable `Task` (`tasks/helm-deploy.yaml`) |
| `withCredentials` / `credentials()` | `workspaces` bound to Secrets, or `env.valueFrom.secretKeyRef` |
| `stash` / `unstash` | shared `workspace` backed by a PVC |
| `post { ... }` | `finally` tasks reading `$(tasks.status)` |
| `input` approval | no equivalent; production run is a separate PipelineRun or a `when` gate |
| `options { timeout }` | `PipelineRun.spec.timeouts.pipeline` |

These manifests are schema-valid and are validated in CI with kubeconform, but nothing in this repo
applies them to a cluster.
