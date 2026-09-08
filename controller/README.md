# workflow-notifier controller

A small [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) controller
that watches Argo `Workflow` resources and POSTs a JSON event to a webhook the first time each
workflow reaches a terminal phase (`Succeeded`, `Failed`, `Error`).

It is the piece that lets a GitHub Actions job that submitted an in-cluster Argo Workflow find
out how it ended without polling: the webhook can be a `repository_dispatch` call, a Slack hook,
or anything else that accepts JSON.

## Behaviour

- Reconciles on create and on `status.phase` change only. Node-level progress updates on a
  running workflow are filtered by a predicate, so the reconcile queue stays quiet.
- Sends one event per terminal phase and records it in the
  `migration-platform.io/notified-phase` annotation. Restarts and resyncs do not resend.
- On webhook failure the reconcile returns an error and controller-runtime requeues with
  backoff; the annotation is only written after a successful delivery.
- Retries 5xx and network errors (2 retries by default); 4xx is treated as permanent for
  that attempt but the reconcile still requeues.
- Optional HMAC-SHA256 signing (`X-Signature-256: sha256=<hex>`) when `WEBHOOK_SECRET` is set.
- Exposes `workflow_notifications_total{phase,result}` on the metrics endpoint.

Event body:

```json
{
  "name": "orders-api-abc12",
  "namespace": "ci",
  "uid": "…",
  "phase": "Succeeded",
  "message": "",
  "startedAt": "2026-09-08T12:00:00Z",
  "finishedAt": "2026-09-08T12:02:00Z",
  "durationSeconds": 120,
  "labels": {"app": "orders-api"}
}
```

## Why there is no Argo dependency

`api/v1alpha1` is a hand-written, partial copy of Argo's `Workflow` type: `metadata`, and the
`phase`, `startedAt`, `finishedAt`, `message`, `progress` fields of `status`. Importing
`github.com/argoproj/argo-workflows/v3` would pull in the whole Argo server dependency tree for
a controller that reads five fields. The cost is that the type is lossy, so the controller must
never `Update` a workflow; it only issues a JSON merge patch on `metadata.annotations`.

Checked against upstream (`pkg/apis/workflow/v1alpha1/workflow_phase.go`, `register.go`) at
Argo Workflows v4.1.2: phase constants, `Completed()`, group/version/kind all match. Note that
Argo's Workflow CRD does not enable the `status` subresource, so patching metadata is the same
call path Argo itself uses.

## Build and test

```
make test    # go test -race ./...
make lint    # golangci-lint (v2 config)
make build   # bin/controller
```

Tests use controller-runtime's fake client and `httptest`; no cluster or envtest binaries are
needed. The controller has not been run against a real cluster as part of this repo.

## Deploy (not done here)

`config/rbac` and `config/manager` are validate-only manifests: a ServiceAccount with
`get/list/watch/patch` on workflows, a leader-election Role, and a two-replica Deployment
reading `WEBHOOK_URL` and `WEBHOOK_SECRET` from a Secret. Build the image with `make
docker-build`, push it, adjust the image reference, and apply the manifests to a cluster that
already runs Argo Workflows.

## Flags

| Flag | Env | Default | Meaning |
|---|---|---|---|
| `--webhook-url` | `WEBHOOK_URL` | required | Where to POST |
| `--namespace` | `WATCH_NAMESPACE` | all | Restrict the watch to one namespace |
| `--webhook-timeout` | | 10s | Per-request timeout |
| `--webhook-retries` | | 2 | Retries after the first attempt |
| `--leader-elect` | | false | Enable leader election |
| `--metrics-bind-address` | | :8080 | Prometheus endpoint |
| `--health-probe-bind-address` | | :8081 | `/healthz`, `/readyz` |
| | `WEBHOOK_SECRET` | | HMAC key; signing is off when empty |
