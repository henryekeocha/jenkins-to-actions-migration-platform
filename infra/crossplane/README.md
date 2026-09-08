# Crossplane: S3 + IAM artifact store

An `ArtifactStore` composite resource (XRD, Crossplane v2, namespaced) composed into an S3
bucket with versioning, SSE-S3 encryption and a public access block, plus an IAM role, a
least-privilege policy and the attachment. It is the Crossplane version of
`../terraform/modules/artifact-store`; the two are kept resource-for-resource identical so
`docs/terraform-vs-crossplane.md` can compare like with like.

| File | What |
|---|---|
| `xrd.yaml` | `CompositeResourceDefinition` (`apiextensions.crossplane.io/v2`, `scope: Namespaced`) |
| `composition.yaml` | `Composition` in `Pipeline` mode: `function-patch-and-transform`, then `function-auto-ready` |
| `functions.yaml` | the two `Function` packages, pinned |
| `providers.yaml` | `provider-aws-s3` and `provider-aws-iam` v2.7.2 (family v2, namespaced MRs) |
| `example-xr.yaml` | what a team creates in its namespace |

## What was checked against current docs and CRDs

- Crossplane v2.4: Compositions are `apiextensions.crossplane.io/v1` with `mode: Pipeline`; the
  legacy `Resources` mode is gone. XRDs are `v2` with `scope: Namespaced` as the default and no
  `claimNames`. The spec's assumption of a claim-based XRD was therefore dropped: teams create
  the XR directly in their namespace.
- Managed resources use the namespaced API groups `s3.aws.m.upbound.io/v1beta1` and
  `iam.aws.m.upbound.io/v1beta1` (checked against the CRDs in `crossplane-contrib/provider-upjet-aws`).
  Their `providerConfigRef` defaults to `kind: ClusterProviderConfig, name: default`, which the
  composition sets explicitly.
- `function-patch-and-transform` input is `pt.fn.crossplane.io/v1beta1 Resources`.

## Validation

CI runs kubeconform against the Crossplane CRD schemas for the XRD, Composition, Provider and
Function objects. The example XR has no published schema and is checked for YAML validity only.

CI also converts the XRD to a CRD (`crossplane xrd convert`) and validates `example-xr.yaml`
against it, then approximates the composed resources with `hack/render-composition.py` and
validates them against the seven Upbound provider CRDs (`hack/crd-schemas.py`). That renderer
covers only the patch types used here; `crossplane composition render` (needs Docker to run the
functions) is the real thing and is the next step before applying. Nothing in this directory has
been applied to a cluster.
