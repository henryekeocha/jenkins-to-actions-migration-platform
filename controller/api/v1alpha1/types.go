package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
)

const (
	// Group is the Argo Workflows API group.
	Group = "argoproj.io"
	// Version is the Argo Workflows API version.
	Version = "v1alpha1"
	// WorkflowKind is the kind of a Workflow resource.
	WorkflowKind = "Workflow"
)

// GroupVersion is the Argo Workflows GroupVersion.
var GroupVersion = schema.GroupVersion{Group: Group, Version: Version}

// AddToScheme registers the Workflow types with a scheme.
func AddToScheme(s *runtime.Scheme) error {
	s.AddKnownTypes(GroupVersion, &Workflow{}, &WorkflowList{})
	metav1.AddToGroupVersion(s, GroupVersion)
	return nil
}

// WorkflowPhase is the phase of a workflow. Values match upstream Argo exactly.
type WorkflowPhase string

const (
	WorkflowUnknown   WorkflowPhase = ""
	WorkflowPending   WorkflowPhase = "Pending"
	WorkflowRunning   WorkflowPhase = "Running"
	WorkflowSucceeded WorkflowPhase = "Succeeded"
	WorkflowFailed    WorkflowPhase = "Failed"
	WorkflowError     WorkflowPhase = "Error"
)

// Completed reports whether the phase is terminal. Mirrors WorkflowPhase.Completed upstream.
func (p WorkflowPhase) Completed() bool {
	switch p {
	case WorkflowSucceeded, WorkflowFailed, WorkflowError:
		return true
	default:
		return false
	}
}

// WorkflowStatus is the subset of Argo's WorkflowStatus this controller reads.
type WorkflowStatus struct {
	Phase      WorkflowPhase `json:"phase,omitempty"`
	StartedAt  metav1.Time   `json:"startedAt,omitempty"`
	FinishedAt metav1.Time   `json:"finishedAt,omitempty"`
	Message    string        `json:"message,omitempty"`
	Progress   string        `json:"progress,omitempty"`
}

// Workflow is an Argo Workflow with its spec left opaque.
type Workflow struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata"`
	Status            WorkflowStatus `json:"status,omitempty"`
}

// WorkflowList is a list of Workflows.
type WorkflowList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata"`
	Items           []Workflow `json:"items"`
}

// DeepCopyObject implements runtime.Object.
func (w *Workflow) DeepCopyObject() runtime.Object { return w.DeepCopy() }

// DeepCopy returns a deep copy.
func (w *Workflow) DeepCopy() *Workflow {
	if w == nil {
		return nil
	}
	out := new(Workflow)
	out.TypeMeta = w.TypeMeta
	w.ObjectMeta.DeepCopyInto(&out.ObjectMeta)
	out.Status = w.Status
	out.Status.StartedAt = *w.Status.StartedAt.DeepCopy()
	out.Status.FinishedAt = *w.Status.FinishedAt.DeepCopy()
	return out
}

// DeepCopyObject implements runtime.Object.
func (l *WorkflowList) DeepCopyObject() runtime.Object { return l.DeepCopy() }

// DeepCopy returns a deep copy.
func (l *WorkflowList) DeepCopy() *WorkflowList {
	if l == nil {
		return nil
	}
	out := new(WorkflowList)
	out.TypeMeta = l.TypeMeta
	l.ListMeta.DeepCopyInto(&out.ListMeta)
	if l.Items != nil {
		out.Items = make([]Workflow, len(l.Items))
		for i := range l.Items {
			out.Items[i] = *l.Items[i].DeepCopy()
		}
	}
	return out
}
