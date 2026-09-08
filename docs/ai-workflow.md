# How this repository was built with Claude Code

An honest account, because the way a thing was made is part of judging it.

## Setup

The repo was built in Claude Code sessions with commit attribution enabled, so every commit
carries a `Claude-Session:` trailer linking the session that produced it. The human wrote the
spec (the phase plan, the hard rules) and reviewed output; the model wrote the code, ran the
tools, and made the routine decisions.

The hard rules that shaped the work: never apply infrastructure, assume no cloud credentials,
and check the real APIs (Argo Workflow status fields, controller-runtime version,
Backstage template schema, Crossplane v2, Upbound provider CRDs) against current docs rather
than memory, reporting where they differ from the spec.

## Where it helped

- **Breadth.** Groovy, Tekton, GitHub Actions expressions, Go with controller-runtime,
  Crossplane function pipelines, Terraform, Backstage scaffolder syntax. A person fluent in all
  of these is rare; a person who can review all of these with a good draft in front of them is
  common.
- **Validation discipline.** Every phase was checked by a tool before commit: kubeconform,
  actionlint, yamllint, ruff, pytest, go vet, golangci-lint, go test -race, terraform validate,
  JSON-schema validation of the Backstage template. When a tool was missing (kubeconform's
  Tekton schemas, Backstage schemas with cross-file refs, offline Crossplane validation), the
  model wrote a small script under `hack/` rather than skipping the check.
- **Catching its own mistakes.** The analyzer initially reported `bod` as a shared-library
  step (a regex matching `body:` badly) and the docker agent block's `image` and `args` as
  library steps. The example pipeline deployed the full SHA while the image was tagged with the
  short SHA. The skeleton workflow referenced a job it did not depend on. All were found by the
  tests or actionlint, not by a reviewer.

## Where it needed correction or judgment

- **One commit landed with a failing test.** A `pytest | tail` pipeline hid the exit code, so
  the Phase 3 commit was pushed red and amended a few minutes later. Lesson recorded: never
  put a test runner behind a pipe in a commit chain.
- **The spec assumed APIs that had moved.** Crossplane v2 removed claims and the legacy
  Composition mode; the XRD was rewritten as namespaced. The Crossplane CLI dropped `beta
  validate` between versions, so the offline check became a renderer plus schema validation.
  controller-runtime v0.25 requires Go 1.26. Each was reported in the relevant README rather
  than silently adjusted.
- **Disk pressure on the dev machine.** Two copies of the AWS Terraform provider filled the
  disk; the fix was a shared plugin cache, which CI also uses.
- **Scope restraint.** The controller could have imported Argo's types; the template could have
  created environments and secrets; the Composition could have used a templating function. In
  each case the smaller, explainable option was chosen and the trade-off written down.

## What was not done

- Nothing was run against a real cluster, Jenkins, Backstage instance, or AWS account. Every
  README says so. The controller's reconcile loop is tested with a fake client; the Argo and
  Crossplane manifests are schema-validated; the Backstage template is validated against the
  upstream schema and its skeleton is rendered and linted. That is a strong static story and a
  non-existent runtime story, and it should be read that way.
- No load, soak, or chaos testing of the controller.
- The analyzer is a regex tool, not a Groovy parser, and its README lists the consequences.

## Reproducing the workflow

Each phase is one commit. `git log --reverse` reads as the build order; every commit message
says what was verified and how. The CI workflow in `.github/workflows/ci.yml` runs the same
checks that were run locally.
