# Terraform vs Crossplane for the resources a pipeline needs

This repo builds the same thing twice: an S3 bucket and an IAM role that can use it, as a
Terraform module (`infra/terraform/modules/artifact-store`) and as a Crossplane Composition
(`infra/crossplane`). Having both side by side makes the trade-off concrete. This is a point of
view, not a survey.

## The short version

Use **Terraform** for the account-level, slow-changing, blast-radius-heavy things: VPCs,
clusters, IAM foundations, the OIDC provider, the Crossplane installation itself. Use
**Crossplane** for the per-team, per-service resources that application teams should be able to
request without a platform ticket: buckets, queues, databases, roles scoped to one workload.
The line is "who changes it and how often", not "which tool is better".

## Where the two differ in practice

**Who can request a resource.** With Crossplane, a team writes a 10-line `ArtifactStore` in its
own namespace and gets a bucket and a role. RBAC on the XR kind is the whole access-control
story, and the Backstage template can create the YAML. With Terraform, someone with state access
runs a plan and an apply, usually through a pipeline, usually with a review. Both are fine; they
suit different resources.

**Drift.** Crossplane reconciles continuously: delete the bucket policy by hand and it comes
back within a minute. Terraform detects drift at the next plan and does nothing until someone
applies. For per-service resources continuous reconciliation is what you want. For foundations,
the pause is a feature.

**Reviewability.** A Terraform plan shows exactly what will change before it changes. A
Crossplane change is a Kubernetes object update; you review the manifest, not the diff of cloud
state. `crossplane beta render` narrows the gap but is not a plan.

**Expressiveness.** Compare the IAM trust policy in the two implementations. Terraform's
`aws_iam_policy_document` with `dynamic` blocks is readable. The Composition assembles the same
JSON with `CombineFromComposite` and `string` transforms, and it is not readable. Anything with
real logic (conditionals, loops, lookups) is where patch-and-transform stops being pleasant; the
answer is `function-go-templating`, `function-kcl` or a custom function, at which point you are
writing code that runs inside the cluster. Terraform's HCL handles that logic in-line.

**Dependencies between resources.** Terraform resolves them from references. In the
Composition, the bucket policy needs the bucket ARN, which only exists after the bucket is
created, so the policy is patched from XR status with a `Required` policy and stays unready
until then. It works, and the `auto-ready` function makes the XR reflect it, but it is one more
thing to know.

**State.** Terraform has state to protect, lock and migrate. Crossplane's state is the cluster.
That removes a class of operational problems and adds another: the cluster running Crossplane
is now critical infrastructure with cloud credentials, and resources with `deletionPolicy:
Delete` disappear if the XR does.

**Cost of the control plane.** Crossplane needs a cluster, the providers (each with CRDs in the
hundreds; the family split in provider-aws v1+ helps), and someone watching them. Terraform
needs a place to run and somewhere to keep state.

## Applied to this repo

- The GitHub OIDC provider, the cluster Argo and the notifier run in, and the Crossplane install:
  Terraform. They change a few times a year and a wrong apply hurts everyone.
- Per-service artifact buckets, roles for GitHub Actions to assume, queues and databases for
  the services being migrated: Crossplane, exposed through the Backstage template so a new
  service gets its bucket and role on day one without a ticket.
- Both live in Git and both are validated in CI without being applied. The Terraform module is
  `terraform validate`d; the Composition is schema-checked and can be rendered offline.

## What would change this view

If the platform team is small and the cluster is not already a well-run place, skip Crossplane:
a Terraform module per resource type behind a `workflow_dispatch` workflow with an environment
approval gets most of the self-service benefit with none of the control-plane burden. If teams
are already fluent in Kubernetes and the resources are numerous and homogeneous, lean further
into Crossplane and keep Terraform for bootstrap only.
