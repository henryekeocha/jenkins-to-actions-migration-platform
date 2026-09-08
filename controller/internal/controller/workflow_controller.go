// Package controller reconciles Argo Workflows and notifies a webhook when they complete.
package controller

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/builder"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/event"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/metrics"
	"sigs.k8s.io/controller-runtime/pkg/predicate"

	argov1alpha1 "github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/api/v1alpha1"
	"github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/internal/notify"
)

// NotifiedPhaseAnnotation records the phase that has already been delivered to the webhook,
// so a restart or resync does not send the same completion twice.
const NotifiedPhaseAnnotation = "migration-platform.io/notified-phase"

var notificationsTotal = prometheus.NewCounterVec(
	prometheus.CounterOpts{
		Name: "workflow_notifications_total",
		Help: "Workflow completion notifications attempted, by phase and result.",
	},
	[]string{"phase", "result"},
)

func init() {
	metrics.Registry.MustRegister(notificationsTotal)
}

// WorkflowReconciler watches Workflows and calls Notifier once per terminal phase.
type WorkflowReconciler struct {
	client.Client
	Notifier notify.Notifier
}

// Reconcile handles one Workflow. It is safe to call repeatedly: the annotation makes
// notification idempotent per phase.
func (r *WorkflowReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	log := logf.FromContext(ctx)

	var wf argov1alpha1.Workflow
	if err := r.Get(ctx, req.NamespacedName, &wf); err != nil {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, fmt.Errorf("get workflow: %w", err)
	}

	phase := wf.Status.Phase
	if !phase.Completed() {
		return ctrl.Result{}, nil
	}
	if wf.Annotations[NotifiedPhaseAnnotation] == string(phase) {
		return ctrl.Result{}, nil
	}

	ev := eventFor(&wf)
	if err := r.Notifier.Notify(ctx, ev); err != nil {
		notificationsTotal.WithLabelValues(string(phase), "error").Inc()
		log.Error(err, "webhook delivery failed", "phase", phase)
		return ctrl.Result{}, fmt.Errorf("notify: %w", err)
	}
	notificationsTotal.WithLabelValues(string(phase), "success").Inc()
	log.Info("workflow completion delivered", "phase", phase, "durationSeconds", ev.DurationSeconds)

	// Argo's Workflow CRD has no status subresource and this type is partial, so never Update:
	// a JSON merge patch on metadata.annotations is the only write the controller makes.
	patch, err := json.Marshal(map[string]any{
		"metadata": map[string]any{
			"annotations": map[string]string{NotifiedPhaseAnnotation: string(phase)},
		},
	})
	if err != nil {
		return ctrl.Result{}, err
	}
	if err := r.Patch(ctx, &wf, client.RawPatch(types.MergePatchType, patch)); err != nil {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, fmt.Errorf("record notified phase: %w", err)
	}
	return ctrl.Result{}, nil
}

func eventFor(wf *argov1alpha1.Workflow) notify.Event {
	ev := notify.Event{
		Name:      wf.Name,
		Namespace: wf.Namespace,
		UID:       string(wf.UID),
		Phase:     string(wf.Status.Phase),
		Message:   wf.Status.Message,
		Labels:    wf.Labels,
	}
	if !wf.Status.StartedAt.IsZero() {
		t := wf.Status.StartedAt.Time
		ev.StartedAt = &t
	}
	if !wf.Status.FinishedAt.IsZero() {
		t := wf.Status.FinishedAt.Time
		ev.FinishedAt = &t
	}
	if ev.StartedAt != nil && ev.FinishedAt != nil {
		ev.DurationSeconds = ev.FinishedAt.Sub(*ev.StartedAt).Round(time.Millisecond).Seconds()
	}
	return ev
}

// PhaseChanged only lets events through when status.phase changes (or on initial listing), so
// the busy stream of node-status updates on a running workflow does not trigger reconciles.
func PhaseChanged() predicate.Predicate {
	return predicate.Funcs{
		CreateFunc: func(e event.CreateEvent) bool { return true },
		DeleteFunc: func(e event.DeleteEvent) bool { return false },
		GenericFunc: func(e event.GenericEvent) bool {
			return false
		},
		UpdateFunc: func(e event.UpdateEvent) bool {
			oldWf, ok1 := e.ObjectOld.(*argov1alpha1.Workflow)
			newWf, ok2 := e.ObjectNew.(*argov1alpha1.Workflow)
			if !ok1 || !ok2 {
				return false
			}
			return oldWf.Status.Phase != newWf.Status.Phase
		},
	}
}

// SetupWithManager registers the reconciler.
func (r *WorkflowReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		Named("workflow-notifier").
		For(&argov1alpha1.Workflow{}, builder.WithPredicates(PhaseChanged())).
		Complete(r)
}
