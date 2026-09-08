FROM golang:${{ values.goVersion }}-bookworm AS build
WORKDIR /src
COPY go.mod ./
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /out/${{ values.name }} ./cmd/${{ values.name }}

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/${{ values.name }} /${{ values.name }}
EXPOSE 8080
ENTRYPOINT ["/${{ values.name }}"]
