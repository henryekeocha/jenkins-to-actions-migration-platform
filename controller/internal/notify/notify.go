// Package notify delivers workflow completion events to an HTTP webhook.
package notify

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Event is the JSON body posted to the webhook.
type Event struct {
	Name            string            `json:"name"`
	Namespace       string            `json:"namespace"`
	UID             string            `json:"uid"`
	Phase           string            `json:"phase"`
	Message         string            `json:"message,omitempty"`
	StartedAt       *time.Time        `json:"startedAt,omitempty"`
	FinishedAt      *time.Time        `json:"finishedAt,omitempty"`
	DurationSeconds float64           `json:"durationSeconds"`
	Labels          map[string]string `json:"labels,omitempty"`
}

// Notifier sends events somewhere.
type Notifier interface {
	Notify(ctx context.Context, ev Event) error
}

// Webhook posts events as JSON to a URL, optionally signing them with an HMAC-SHA256 secret.
type Webhook struct {
	URL        string
	Secret     []byte
	Client     *http.Client
	MaxRetries int           // attempts beyond the first; default 2
	Backoff    time.Duration // base backoff between attempts; default 500ms
}

// PermanentError marks a delivery failure that will not succeed on retry (4xx).
type PermanentError struct {
	Status int
	Body   string
}

func (e *PermanentError) Error() string {
	return fmt.Sprintf("webhook rejected event: status %d: %s", e.Status, e.Body)
}

// Notify posts the event, retrying on network errors and 5xx responses.
func (w *Webhook) Notify(ctx context.Context, ev Event) error {
	body, err := json.Marshal(ev)
	if err != nil {
		return fmt.Errorf("encode event: %w", err)
	}
	retries := w.MaxRetries
	if retries == 0 {
		retries = 2
	}
	backoff := w.Backoff
	if backoff == 0 {
		backoff = 500 * time.Millisecond
	}

	var last error
	for attempt := 0; attempt <= retries; attempt++ {
		if attempt > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff * time.Duration(1<<(attempt-1))):
			}
		}
		last = w.post(ctx, body, ev.Phase)
		if last == nil {
			return nil
		}
		var perm *PermanentError
		if errors.As(last, &perm) {
			return last
		}
	}
	return fmt.Errorf("after %d attempt(s): %w", retries+1, last)
}

func (w *Webhook) post(ctx context.Context, body []byte, phase string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, w.URL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "argo-workflow-notifier")
	req.Header.Set("X-Workflow-Phase", phase)
	if len(w.Secret) > 0 {
		req.Header.Set("X-Signature-256", "sha256="+Sign(w.Secret, body))
	}

	client := w.Client
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))

	switch {
	case resp.StatusCode >= 200 && resp.StatusCode < 300:
		return nil
	case resp.StatusCode >= 400 && resp.StatusCode < 500 && resp.StatusCode != http.StatusTooManyRequests:
		return &PermanentError{Status: resp.StatusCode, Body: string(respBody)}
	default:
		return fmt.Errorf("webhook returned status %d", resp.StatusCode)
	}
}

// Sign returns the hex HMAC-SHA256 of body under secret.
func Sign(secret, body []byte) string {
	mac := hmac.New(sha256.New, secret)
	mac.Write(body)
	return hex.EncodeToString(mac.Sum(nil))
}
