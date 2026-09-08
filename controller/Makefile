BIN      ?= bin/controller
IMG      ?= ghcr.io/henryekeocha/workflow-notifier:dev
GOFLAGS  ?= -mod=readonly

.PHONY: all build test vet lint fmt tidy docker-build manifests-validate clean

all: fmt vet lint test build

build:
	CGO_ENABLED=0 go build $(GOFLAGS) -trimpath -ldflags='-s -w' -o $(BIN) ./cmd/controller

test:
	go test $(GOFLAGS) -race -coverprofile=cover.out ./...

vet:
	go vet $(GOFLAGS) ./...

lint:
	golangci-lint run ./...

fmt:
	gofmt -l -w .

tidy:
	go mod tidy

docker-build:
	docker build -t $(IMG) .

# Validates the deployment manifests against Kubernetes schemas. Never applies them.
manifests-validate:
	kubeconform -strict -summary config/

clean:
	rm -rf bin cover.out
