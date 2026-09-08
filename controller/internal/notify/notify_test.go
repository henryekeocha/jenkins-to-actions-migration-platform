package notify

import (
	"context"
	"crypto/hmac"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestNotifyPostsSignedJSON(t *testing.T) {
	secret := []byte("s3cret")
	var got Event
	var sig, phaseHeader string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		sig = r.Header.Get("X-Signature-256")
		phaseHeader = r.Header.Get("X-Workflow-Phase")
		if r.Header.Get("Content-Type") != "application/json" {
			t.Errorf("content-type = %q", r.Header.Get("Content-Type"))
		}
		if !hmac.Equal([]byte(sig), []byte("sha256="+Sign(secret, body))) {
			t.Errorf("bad signature %q", sig)
		}
		if err := json.Unmarshal(body, &got); err != nil {
			t.Errorf("decode: %v", err)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()

	started := time.Date(2026, 9, 8, 10, 0, 0, 0, time.UTC)
	finished := started.Add(90 * time.Second)
	ev := Event{
		Name: "build-abc", Namespace: "ci", UID: "u1", Phase: "Succeeded",
		StartedAt: &started, FinishedAt: &finished, DurationSeconds: 90,
		Labels: map[string]string{"app": "orders-api"},
	}
	wh := &Webhook{URL: srv.URL, Secret: secret}
	if err := wh.Notify(context.Background(), ev); err != nil {
		t.Fatalf("Notify: %v", err)
	}
	if got.Name != "build-abc" || got.Phase != "Succeeded" || got.DurationSeconds != 90 {
		t.Errorf("got event %+v", got)
	}
	if got.Labels["app"] != "orders-api" {
		t.Errorf("labels not delivered: %v", got.Labels)
	}
	if phaseHeader != "Succeeded" {
		t.Errorf("phase header = %q", phaseHeader)
	}
	if sig == "" {
		t.Error("no signature header")
	}
}

func TestNotifyOmitsSignatureWithoutSecret(t *testing.T) {
	var sig string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sig = r.Header.Get("X-Signature-256")
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	if err := (&Webhook{URL: srv.URL}).Notify(context.Background(), Event{Phase: "Failed"}); err != nil {
		t.Fatal(err)
	}
	if sig != "" {
		t.Errorf("unexpected signature %q", sig)
	}
}

func TestNotifyRetriesOn5xx(t *testing.T) {
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if atomic.AddInt32(&calls, 1) < 3 {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	wh := &Webhook{URL: srv.URL, MaxRetries: 3, Backoff: time.Millisecond}
	if err := wh.Notify(context.Background(), Event{}); err != nil {
		t.Fatalf("expected success after retries, got %v", err)
	}
	if calls != 3 {
		t.Errorf("calls = %d, want 3", calls)
	}
}

func TestNotifyGivesUpAfterRetries(t *testing.T) {
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()
	wh := &Webhook{URL: srv.URL, MaxRetries: 2, Backoff: time.Millisecond}
	err := wh.Notify(context.Background(), Event{})
	if err == nil {
		t.Fatal("expected error")
	}
	if calls != 3 {
		t.Errorf("calls = %d, want 3", calls)
	}
}

func TestNotifyDoesNotRetry4xx(t *testing.T) {
	var calls int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		http.Error(w, "bad payload", http.StatusBadRequest)
	}))
	defer srv.Close()
	wh := &Webhook{URL: srv.URL, MaxRetries: 3, Backoff: time.Millisecond}
	err := wh.Notify(context.Background(), Event{})
	var perm *PermanentError
	if !errors.As(err, &perm) || perm.Status != 400 {
		t.Fatalf("expected PermanentError 400, got %v", err)
	}
	if calls != 1 {
		t.Errorf("calls = %d, want 1", calls)
	}
}

func TestNotifyHonoursContextCancel(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	wh := &Webhook{URL: srv.URL, MaxRetries: 5, Backoff: time.Second}
	if err := wh.Notify(ctx, Event{}); !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context.Canceled, got %v", err)
	}
}
