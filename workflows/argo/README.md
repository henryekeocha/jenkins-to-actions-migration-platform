# Argo Workflows DAG

`build-test-deploy.yaml` is the orders-api pipeline as a reusable `WorkflowTemplate`
(`argoproj.io/v1alpha1`): a DAG entrypoint with `depends` edges, container templates for each
task sharing a `volumeClaimTemplates` workspace, and a `suspend` template as the production
approval gate. `example-workflow.yaml` shows a `Workflow` submitting it through
`workflowTemplateRef`.

Why keep an in-cluster DAG at all after moving to GitHub Actions: some steps are better run with
pod identity and cluster-internal network access (deploys, integration tests against in-cluster
dependencies, jobs with big caches). The pattern this repo proposes is GitHub Actions as the
front door and Argo for those steps, with `controller/` posting completion back so the Actions
job does not have to poll.

Mapping from the other two pipelines:

| Jenkins | Tekton | Argo |
|---|---|---|
| `stage` | `PipelineTask` | `dag.tasks[]` |
| `parallel` | same `runAfter` | same `depends` |
| `when { }` | `when` expressions | `when:` on the task |
| `input` | none | `suspend: {}` template + `argo resume` |
| `stash` | shared workspace PVC | `volumeClaimTemplates` |
| `post { }` | `finally` | `onExit` handler (not used here; the notifier controller covers it) |
| `options { timeout }` | `timeouts.pipeline` | `activeDeadlineSeconds` |
| `parameters { }` | `spec.params` | `arguments.parameters` with `enum` |

Validated in CI with kubeconform against the Argo CRD schemas. Not applied to any cluster.
