# syntax=docker/dockerfile:1
FROM golang:1.26-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags='-s -w' -o /out/controller ./cmd/controller

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/controller /controller
USER 65532:65532
ENTRYPOINT ["/controller"]
