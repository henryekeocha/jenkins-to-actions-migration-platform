// Package v1alpha1 holds a minimal, read-only view of the Argo Workflows API
// (argoproj.io/v1alpha1) sufficient for watching workflow completion.
//
// The full github.com/argoproj/argo-workflows/v3 module is not imported on purpose: it pulls
// in a very large dependency graph (Argo server, executors, cloud SDKs) for a controller that
// only reads status.phase and writes one annotation. Field names, JSON tags and phase constants
// below are copied from pkg/apis/workflow/v1alpha1 in argo-workflows and are checked against
// upstream in the README.
//
// Because this struct is partial, the controller never Updates a Workflow (that would drop
// unknown fields). It only issues merge patches against metadata.annotations.
package v1alpha1
