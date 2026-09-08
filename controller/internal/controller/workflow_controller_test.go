package controller

import (
	"context"
	"errors"
	"testing"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/client/fake"
	"sigs.k8s.io/controller-runtime/pkg/event"

	argov1alpha1 "github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/api/v1alpha1"
	"github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/internal/notify"
)

type recorder struct {
	events []notify.Event
	err    error
}

func (r *recorder) Notify(_ context.Context, ev notify.Event) error {
	if r.err != nil {
		return r.err
	}
	r.events = append(r.events, ev)
	return nil
}

func newScheme(t *testing.T) *runtime.Scheme {
	t.Helper()
	s := runtime.NewScheme()
	if err := argov1alpha1.AddToScheme(s); err != nil {
		t.Fatal(err)
	}
	return s
}

func workflow(phase argov1alpha1.WorkflowPhase) *argov1alpha1.Workflow {
	started := metav1.NewTime(time.Date(2026, 9, 8, 12, 0, 0, 0, time.UTC))
	wf := &argov1alpha1.Workflow{
		ObjectMeta: metav1.ObjectMeta{
			Name: "build-x", Namespace: "ci", UID: "uid-1",
			Labels: map[string]string{"app": "orders-api"},
		},
		Status: argov1alpha1.WorkflowStatus{Phase: phase, StartedAt: started},
	}
	if phase.Completed() {
		wf.Status.FinishedAt = metav1.NewTime(started.Add(2 * time.Minute))
		wf.Status.Message = "done"
	}
	return wf
}

func reconcileOnce(t *testing.T, c client.Client, n notify.Notifier, wf *argov1alpha1.Workflow) error {
	t.Helper()
	r := &WorkflowReconciler{Client: c, Notifier: n}
	_, err := r.Reconcile(context.Background(), ctrl.Request{
		NamespacedName: types.NamespacedName{Name: wf.Name, Namespace: wf.Namespace},
	})
	return err
}

func TestNotifiesOnceOnCompletion(t *testing.T) {
	wf := workflow(argov1alpha1.WorkflowSucceeded)
	c := fake.NewClientBuilder().WithScheme(newScheme(t)).WithObjects(wf).Build()
	rec := &recorder{}

	if err := reconcileOnce(t, c, rec, wf); err != nil {
		t.Fatal(err)
	}
	if len(rec.events) != 1 {
		t.Fatalf("events = %d, want 1", len(rec.events))
	}
	ev := rec.events[0]
	if ev.Phase != "Succeeded" || ev.Name != "build-x" || ev.Namespace != "ci" || ev.UID != "uid-1" {
		t.Errorf("event = %+v", ev)
	}
	if ev.DurationSeconds != 120 {
		t.Errorf("duration = %v, want 120", ev.DurationSeconds)
	}
	if ev.Labels["app"] != "orders-api" || ev.Message != "done" {
		t.Errorf("labels/message not propagated: %+v", ev)
	}

	var got argov1alpha1.Workflow
	if err := c.Get(context.Background(), client.ObjectKeyFromObject(wf), &got); err != nil {
		t.Fatal(err)
	}
	if got.Annotations[NotifiedPhaseAnnotation] != "Succeeded" {
		t.Errorf("annotation = %q", got.Annotations[NotifiedPhaseAnnotation])
	}

	// Second reconcile (resync, restart) must not notify again.
	if err := reconcileOnce(t, c, rec, wf); err != nil {
		t.Fatal(err)
	}
	if len(rec.events) != 1 {
		t.Fatalf("events after resync = %d, want 1", len(rec.events))
	}
}

func TestIgnoresRunningWorkflows(t *testing.T) {
	for _, phase := range []argov1alpha1.WorkflowPhase{
		argov1alpha1.WorkflowUnknown, argov1alpha1.WorkflowPending, argov1alpha1.WorkflowRunning,
	} {
		wf := workflow(phase)
		c := fake.NewClientBuilder().WithScheme(newScheme(t)).WithObjects(wf).Build()
		rec := &recorder{}
		if err := reconcileOnce(t, c, rec, wf); err != nil {
			t.Fatal(err)
		}
		if len(rec.events) != 0 {
			t.Errorf("phase %q: notified %d times", phase, len(rec.events))
		}
	}
}

func TestNotifiesFailedAndError(t *testing.T) {
	for _, phase := range []argov1alpha1.WorkflowPhase{argov1alpha1.WorkflowFailed, argov1alpha1.WorkflowError} {
		wf := workflow(phase)
		c := fake.NewClientBuilder().WithScheme(newScheme(t)).WithObjects(wf).Build()
		rec := &recorder{}
		if err := reconcileOnce(t, c, rec, wf); err != nil {
			t.Fatal(err)
		}
		if len(rec.events) != 1 || rec.events[0].Phase != string(phase) {
			t.Errorf("phase %q: events %+v", phase, rec.events)
		}
	}
}

func TestNotFoundIsNotAnError(t *testing.T) {
	c := fake.NewClientBuilder().WithScheme(newScheme(t)).Build()
	rec := &recorder{}
	if err := reconcileOnce(t, c, rec, workflow(argov1alpha1.WorkflowSucceeded)); err != nil {
		t.Fatalf("expected nil for missing workflow, got %v", err)
	}
	if len(rec.events) != 0 {
		t.Error("notified for a missing workflow")
	}
}

func TestNotifierFailureRequeuesWithoutAnnotating(t *testing.T) {
	wf := workflow(argov1alpha1.WorkflowSucceeded)
	c := fake.NewClientBuilder().WithScheme(newScheme(t)).WithObjects(wf).Build()
	rec := &recorder{err: errors.New("boom")}

	if err := reconcileOnce(t, c, rec, wf); err == nil {
		t.Fatal("expected error so controller-runtime requeues")
	}
	var got argov1alpha1.Workflow
	if err := c.Get(context.Background(), client.ObjectKeyFromObject(wf), &got); err != nil {
		t.Fatal(err)
	}
	if _, ok := got.Annotations[NotifiedPhaseAnnotation]; ok {
		t.Error("annotation written despite failed delivery")
	}

	// Once the webhook recovers, the next reconcile delivers and annotates.
	rec.err = nil
	if err := reconcileOnce(t, c, rec, wf); err != nil {
		t.Fatal(err)
	}
	if len(rec.events) != 1 {
		t.Fatalf("events = %d, want 1", len(rec.events))
	}
}

func TestPreviouslyNotifiedPhaseIsSkipped(t *testing.T) {
	wf := workflow(argov1alpha1.WorkflowFailed)
	wf.Annotations = map[string]string{NotifiedPhaseAnnotation: "Failed"}
	c := fake.NewClientBuilder().WithScheme(newScheme(t)).WithObjects(wf).Build()
	rec := &recorder{}
	if err := reconcileOnce(t, c, rec, wf); err != nil {
		t.Fatal(err)
	}
	if len(rec.events) != 0 {
		t.Error("re-notified an already-notified phase")
	}
}

func TestPhaseChangedPredicate(t *testing.T) {
	p := PhaseChanged()
	running := workflow(argov1alpha1.WorkflowRunning)
	stillRunning := workflow(argov1alpha1.WorkflowRunning)
	stillRunning.Status.Progress = "3/5"
	done := workflow(argov1alpha1.WorkflowSucceeded)

	if p.Update(event.UpdateEvent{ObjectOld: running, ObjectNew: stillRunning}) {
		t.Error("node progress update should be filtered")
	}
	if !p.Update(event.UpdateEvent{ObjectOld: running, ObjectNew: done}) {
		t.Error("phase change should pass")
	}
	if !p.Create(event.CreateEvent{Object: done}) {
		t.Error("create should pass (initial list of completed workflows)")
	}
	if p.Delete(event.DeleteEvent{Object: done}) {
		t.Error("delete should be filtered")
	}
}
