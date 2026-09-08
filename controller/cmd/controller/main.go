// Command controller watches Argo Workflows and posts a webhook when each one completes.
package main

import (
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"

	"k8s.io/apimachinery/pkg/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/cache"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"

	argov1alpha1 "github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/api/v1alpha1"
	"github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/internal/controller"
	"github.com/henryekeocha/jenkins-to-actions-migration-platform/controller/internal/notify"
)

func main() {
	var (
		webhookURL           string
		namespace            string
		metricsAddr          string
		probeAddr            string
		leaderElect          bool
		webhookTimeout       time.Duration
		webhookRetries       int
		leaderElectionID     = "workflow-notifier.migration-platform.io"
		webhookSecretEnvName = "WEBHOOK_SECRET"
	)
	flag.StringVar(&webhookURL, "webhook-url", os.Getenv("WEBHOOK_URL"), "URL to POST completion events to (env WEBHOOK_URL)")
	flag.StringVar(&namespace, "namespace", os.Getenv("WATCH_NAMESPACE"), "namespace to watch; empty for all (env WATCH_NAMESPACE)")
	flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "metrics endpoint address; 0 to disable")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "health probe endpoint address")
	flag.BoolVar(&leaderElect, "leader-elect", false, "enable leader election")
	flag.DurationVar(&webhookTimeout, "webhook-timeout", 10*time.Second, "per-request webhook timeout")
	flag.IntVar(&webhookRetries, "webhook-retries", 2, "retries after the first webhook attempt on 5xx/network errors")
	opts := zap.Options{Development: false}
	opts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&opts)))
	log := ctrl.Log.WithName("setup")

	if webhookURL == "" {
		fmt.Fprintln(os.Stderr, "--webhook-url (or WEBHOOK_URL) is required")
		os.Exit(2)
	}

	scheme := runtime.NewScheme()
	if err := clientgoscheme.AddToScheme(scheme); err != nil {
		log.Error(err, "add client-go scheme")
		os.Exit(1)
	}
	if err := argov1alpha1.AddToScheme(scheme); err != nil {
		log.Error(err, "add argo scheme")
		os.Exit(1)
	}

	mgrOpts := ctrl.Options{
		Scheme:                 scheme,
		Metrics:                metricsserver.Options{BindAddress: metricsAddr},
		HealthProbeBindAddress: probeAddr,
		LeaderElection:         leaderElect,
		LeaderElectionID:       leaderElectionID,
	}
	if namespace != "" {
		mgrOpts.Cache = cache.Options{DefaultNamespaces: map[string]cache.Config{namespace: {}}}
	}

	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), mgrOpts)
	if err != nil {
		log.Error(err, "create manager")
		os.Exit(1)
	}

	notifier := &notify.Webhook{
		URL:        webhookURL,
		Secret:     []byte(os.Getenv(webhookSecretEnvName)),
		Client:     &http.Client{Timeout: webhookTimeout},
		MaxRetries: webhookRetries,
	}
	r := &controller.WorkflowReconciler{Client: mgr.GetClient(), Notifier: notifier}
	if err := r.SetupWithManager(mgr); err != nil {
		log.Error(err, "set up reconciler")
		os.Exit(1)
	}

	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		log.Error(err, "add healthz")
		os.Exit(1)
	}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		log.Error(err, "add readyz")
		os.Exit(1)
	}

	log.Info("starting", "webhook", webhookURL, "namespace", namespace, "signed", os.Getenv(webhookSecretEnvName) != "")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {
		log.Error(err, "manager exited")
		os.Exit(1)
	}
}
