# hack/

Small scripts CI uses to validate things that have no off-the-shelf validator.

| Script | Purpose |
|---|---|
| `crd-schemas.py` | Convert CRDs (files or URLs) to strict JSON schemas for kubeconform. Used for Tekton, the Crossplane XRD (after `crossplane xrd convert`), and the Upbound provider CRDs. |
| `render-composition.py` | Approximate the composed resources a Composition produces for an XR, using only the patch types this repo's compositions use. Output is validated against the provider CRD schemas. Not a substitute for `crossplane composition render`. |
| `render-skeleton.py` | Render the Backstage template skeleton with placeholder values so the resulting workflow, chart and Go code can be linted and compiled. |
| `validate-backstage.py` | Validate catalog entities and the template against the upstream Backstage JSON schemas. |
