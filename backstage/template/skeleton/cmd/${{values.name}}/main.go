// Command ${{ values.name }} is a minimal HTTP service with a health endpoint.
package main

import (
	"log"
	"net/http"
	"os"
)

func main() {
	addr := ":" + envOr("PORT", "8080")
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	log.Printf("${{ values.name }} listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
