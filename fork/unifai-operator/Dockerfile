# Build the manager binary (the UnifAI Helm charts are embedded from internal/stack/assets).
FROM docker.io/library/golang:1.26 AS builder
ARG TARGETOS
ARG TARGETARCH
# Default tag of the UnifAI images deployed by UnifaiStack when spec.version is empty.
ARG UNIFAI_VERSION=devel
ARG VERSION=0.0.0

WORKDIR /workspace
COPY go.mod go.mod
COPY go.sum go.sum
RUN go mod download

COPY cmd/main.go cmd/main.go
COPY api/ api/
COPY internal/ internal/

RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -a -trimpath \
    -ldflags "-s -w -X github.com/startxfr/unifai-operator/internal/stack.DefaultVersion=${UNIFAI_VERSION} -X github.com/startxfr/unifai-operator/internal/controller.OperatorVersion=${VERSION}" \
    -o manager cmd/main.go

FROM gcr.io/distroless/static:nonroot
ARG VERSION=0.0.0
LABEL name="unifai-operator" vendor="startx" version="${VERSION}" \
      summary="UnifAI operator" description="Deploys UnifAI stacks and manages UnifAI objects declaratively"
WORKDIR /
COPY --from=builder /workspace/manager .
ENV HOME=/tmp
USER 65532:65532

ENTRYPOINT ["/manager"]
