# VERSION defines the project version for the bundle.
# Update this value when you upgrade the version of your project.
# To re-generate a bundle for another specific version without changing the standard setup, you can:
# - use the VERSION as arg of the bundle target (e.g make bundle VERSION=0.0.2)
# - use environment variables to overwrite this value (e.g export VERSION=0.0.2)
VERSION ?= 0.1.29
# Tag of the UnifAI images a stack deploys by default (spec.version overrides it).
UNIFAI_VERSION ?= devel
CHANNELS ?= alpha,stable
DEFAULT_CHANNEL ?= alpha

# CHANNELS define the bundle channels used in the bundle.
# Add a new line here if you would like to change its default config. (E.g CHANNELS = "candidate,fast,stable")
# To re-generate a bundle for other specific channels without changing the standard setup, you can:
# - use the CHANNELS as arg of the bundle target (e.g make bundle CHANNELS=candidate,fast,stable)
# - use environment variables to overwrite this value (e.g export CHANNELS="candidate,fast,stable")
ifneq ($(origin CHANNELS), undefined)
BUNDLE_CHANNELS := --channels=$(CHANNELS)
endif

# DEFAULT_CHANNEL defines the default channel used in the bundle.
# Add a new line here if you would like to change its default config. (E.g DEFAULT_CHANNEL = "stable")
# To re-generate a bundle for any other default channel without changing the default setup, you can:
# - use the DEFAULT_CHANNEL as arg of the bundle target (e.g make bundle DEFAULT_CHANNEL=stable)
# - use environment variables to overwrite this value (e.g export DEFAULT_CHANNEL="stable")
ifneq ($(origin DEFAULT_CHANNEL), undefined)
BUNDLE_DEFAULT_CHANNEL := --default-channel=$(DEFAULT_CHANNEL)
endif
BUNDLE_METADATA_OPTS ?= $(BUNDLE_CHANNELS) $(BUNDLE_DEFAULT_CHANNEL)

# IMAGE_TAG_BASE defines the docker.io namespace and part of the image name for remote images.
# This variable is used to construct full image tags for bundle and catalog images.
#
# For example, running 'make bundle-build bundle-push catalog-build catalog-push' will build and push both
# startx.fr/unifai-operator-bundle:$VERSION and startx.fr/unifai-operator-catalog:$VERSION.
IMAGE_TAG_BASE ?= quay.io/zuno/unifai-operator

# BUNDLE_IMG defines the image:tag used for the bundle.
# You can use it as an arg. (E.g make bundle-build BUNDLE_IMG=<some-registry>/<project-name-bundle>:<tag>)
BUNDLE_IMG ?= $(IMAGE_TAG_BASE)-bundle:v$(VERSION)

# BUNDLE_GEN_FLAGS are the flags passed to the operator-sdk generate bundle command
BUNDLE_GEN_FLAGS ?= -q --overwrite --version $(VERSION) $(BUNDLE_METADATA_OPTS)

# USE_IMAGE_DIGESTS defines if images are resolved via tags or digests
# You can enable this value if you would like to use SHA Based Digests
# To enable set flag to true
USE_IMAGE_DIGESTS ?= false
ifeq ($(USE_IMAGE_DIGESTS), true)
	BUNDLE_GEN_FLAGS += --use-image-digests
endif

# Set the Operator SDK version to use. By default, what is installed on the system is used.
# This is useful for CI or a project to utilize a specific version of the operator-sdk toolkit.
OPERATOR_SDK_VERSION ?= v1.41.1
# Image URL to use all building/pushing image targets
IMG ?= $(IMAGE_TAG_BASE):v$(VERSION)

# Get the currently used golang install path (in GOPATH/bin, unless GOBIN is set)
ifeq (,$(shell go env GOBIN))
GOBIN=$(shell go env GOPATH)/bin
else
GOBIN=$(shell go env GOBIN)
endif

# CONTAINER_TOOL defines the container tool to be used for building images.
# Be aware that the target commands are only tested with Docker which is
# scaffolded by default. However, you might want to replace it to use other
# tools. (i.e. podman)
CONTAINER_TOOL ?= podman

# Setting SHELL to bash allows bash commands to be executed by recipes.
# Options are set to exit when a recipe line exits non-zero or a piped command fails.
SHELL = /usr/bin/env bash -o pipefail
.SHELLFLAGS = -ec

.PHONY: all
all: build

##@ General

# The help target prints out all targets with their descriptions organized
# beneath their categories. The categories are represented by '##@' and the
# target descriptions by '##'. The awk command is responsible for reading the
# entire set of makefiles included in this invocation, looking for lines of the
# file as xyz: ## something, and then pretty-format the target and help. Then,
# if there's a line with ##@ something, that gets pretty-printed as a category.
# More info on the usage of ANSI control characters for terminal formatting:
# https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_parameters
# More info on the awk command:
# http://linuxcommand.org/lc3_adv_awk.php

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

.PHONY: manifests
manifests: controller-gen ## Generate WebhookConfiguration, ClusterRole and CustomResourceDefinition objects.
	$(CONTROLLER_GEN) rbac:roleName=manager-role crd webhook paths="./..." output:crd:artifacts:config=config/crd/bases

.PHONY: generate
generate: controller-gen ## Generate code containing DeepCopy, DeepCopyInto, and DeepCopyObject method implementations.
	$(CONTROLLER_GEN) object:headerFile="hack/boilerplate.go.txt" paths="./..."

.PHONY: fmt
fmt: ## Run go fmt against code.
	go fmt ./...

.PHONY: vet
vet: ## Run go vet against code.
	go vet ./...

.PHONY: test
test: manifests generate fmt vet setup-envtest ## Run tests.
	KUBEBUILDER_ASSETS="$(shell $(ENVTEST) use $(ENVTEST_K8S_VERSION) --bin-dir $(LOCALBIN) -p path)" go test $$(go list ./... | grep -v /e2e) -coverprofile cover.out

# End-to-end test against the operator installed on the current kubeconfig context (OLM or `make deploy`):
# deploys an UnifaiStack in a throwaway namespace unifai-e2e-*, checks it and deletes it (E2E_KEEP=1 keeps it).
E2E_TIMEOUT ?= 30m
E2E_STORAGE_CLASS ?= gp3-csi
E2E_SHARED_STORAGE_CLASS ?= nfs
E2E_NODE_SELECTOR ?= workload=unifai

.PHONY: test-e2e
test-e2e: ## Run the e2e tests on the current cluster (E2E_STORAGE_CLASS, E2E_SHARED_STORAGE_CLASS, E2E_NODE_SELECTOR, E2E_VERSION, E2E_FULL=1, E2E_KEYCLOAK=1, E2E_INTERNAL_AUTH=0, E2E_KEEP=1).
	E2E_STORAGE_CLASS=$(E2E_STORAGE_CLASS) E2E_SHARED_STORAGE_CLASS=$(E2E_SHARED_STORAGE_CLASS) \
	E2E_NODE_SELECTOR=$(E2E_NODE_SELECTOR) E2E_TIMEOUT=$(E2E_TIMEOUT) \
	E2E_OPERATOR_INSTANCE=$(E2E_OPERATOR_INSTANCE) E2E_OPERATOR_NAMESPACE=$(E2E_OPERATOR_NAMESPACE) \
	E2E_UPGRADE=$(E2E_UPGRADE) E2E_CANDIDATE_VERSION=$(E2E_CANDIDATE_VERSION) E2E_KEYCLOAK=$(E2E_KEYCLOAK) \
	E2E_VERSION=$(E2E_VERSION) E2E_INTERNAL_AUTH=$(E2E_INTERNAL_AUTH) \
	go test -tags e2e -count=1 -timeout 90m -v ./test/e2e/

.PHONY: lint
lint: golangci-lint ## Run golangci-lint linter
	$(GOLANGCI_LINT) run

.PHONY: lint-fix
lint-fix: golangci-lint ## Run golangci-lint linter and perform fixes
	$(GOLANGCI_LINT) run --fix

.PHONY: lint-config
lint-config: golangci-lint ## Verify golangci-lint linter configuration
	$(GOLANGCI_LINT) config verify

##@ Build

.PHONY: build
build: manifests generate fmt vet ## Build manager binary.
	go build -o bin/manager cmd/main.go

.PHONY: run
run: manifests generate fmt vet ## Run a controller from your host.
	go run ./cmd/main.go

# If you wish to build the manager image targeting other platforms you can use the --platform flag.
# (i.e. docker build --platform linux/arm64). However, you must enable docker buildKit for it.
# More info: https://docs.docker.com/develop/develop-images/build_enhancements/
.PHONY: docker-build
docker-build: ## Build docker image with the manager.
	chmod -R a+rX api cmd internal
	$(CONTAINER_TOOL) build --platform linux/amd64 --build-arg UNIFAI_VERSION=$(UNIFAI_VERSION) --build-arg VERSION=$(VERSION) -t ${IMG} .

.PHONY: docker-build-local
docker-build-local: ## Build the manager on the host, then package it (no Go toolchain in the image build).
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath \
		-ldflags "-s -w -X github.com/startxfr/unifai-operator/internal/stack.DefaultVersion=$(UNIFAI_VERSION) -X github.com/startxfr/unifai-operator/internal/controller.OperatorVersion=$(VERSION)" \
		-o bin/manager-linux-amd64 cmd/main.go
	$(CONTAINER_TOOL) build --platform linux/amd64 -f Dockerfile.local --build-arg VERSION=$(VERSION) -t ${IMG} .

.PHONY: docker-push
docker-push: ## Push docker image with the manager.
	$(CONTAINER_TOOL) push ${IMG}

# PLATFORMS defines the target platforms for the manager image be built to provide support to multiple
# architectures. (i.e. make docker-buildx IMG=myregistry/mypoperator:0.0.1). To use this option you need to:
# - be able to use docker buildx. More info: https://docs.docker.com/build/buildx/
# - have enabled BuildKit. More info: https://docs.docker.com/develop/develop-images/build_enhancements/
# - be able to push the image to your registry (i.e. if you do not set a valid value via IMG=<myregistry/image:<tag>> then the export will fail)
# To adequately provide solutions that are compatible with multiple platforms, you should consider using this option.
PLATFORMS ?= linux/arm64,linux/amd64,linux/s390x,linux/ppc64le
.PHONY: docker-buildx
docker-buildx: ## Build and push docker image for the manager for cross-platform support
	# copy existing Dockerfile and insert --platform=${BUILDPLATFORM} into Dockerfile.cross, and preserve the original Dockerfile
	sed -e '1 s/\(^FROM\)/FROM --platform=\$$\{BUILDPLATFORM\}/; t' -e ' 1,// s//FROM --platform=\$$\{BUILDPLATFORM\}/' Dockerfile > Dockerfile.cross
	- $(CONTAINER_TOOL) buildx create --name unifai-operator-builder
	$(CONTAINER_TOOL) buildx use unifai-operator-builder
	- $(CONTAINER_TOOL) buildx build --push --platform=$(PLATFORMS) --tag ${IMG} -f Dockerfile.cross .
	- $(CONTAINER_TOOL) buildx rm unifai-operator-builder
	rm Dockerfile.cross

.PHONY: build-installer
build-installer: manifests generate kustomize ## Generate a consolidated YAML with CRDs and deployment.
	mkdir -p dist
	cd config/manager && $(KUSTOMIZE) edit set image controller=${IMG}
	$(KUSTOMIZE) build config/default > dist/install.yaml

##@ Deployment

ifndef ignore-not-found
  ignore-not-found = false
endif

.PHONY: install
install: manifests kustomize ## Install CRDs into the K8s cluster specified in ~/.kube/config.
	$(KUSTOMIZE) build config/crd | $(KUBECTL) apply -f -

.PHONY: uninstall
uninstall: manifests kustomize ## Uninstall CRDs from the K8s cluster specified in ~/.kube/config. Call with ignore-not-found=true to ignore resource not found errors during deletion.
	$(KUSTOMIZE) build config/crd | $(KUBECTL) delete --ignore-not-found=$(ignore-not-found) -f -

.PHONY: deploy
deploy: manifests kustomize ## Deploy controller to the K8s cluster specified in ~/.kube/config.
	cd config/manager && $(KUSTOMIZE) edit set image controller=${IMG}
	$(KUSTOMIZE) build config/default | $(KUBECTL) apply -f -

.PHONY: undeploy
undeploy: kustomize ## Undeploy controller from the K8s cluster specified in ~/.kube/config. Call with ignore-not-found=true to ignore resource not found errors during deletion.
	$(KUSTOMIZE) build config/default | $(KUBECTL) delete --ignore-not-found=$(ignore-not-found) -f -

##@ Dependencies

## Location to install dependencies to
LOCALBIN ?= $(shell pwd)/bin
$(LOCALBIN):
	mkdir -p $(LOCALBIN)

## Tool Binaries
KUBECTL ?= kubectl
KIND ?= kind
KUSTOMIZE ?= $(LOCALBIN)/kustomize
CONTROLLER_GEN ?= $(LOCALBIN)/controller-gen
ENVTEST ?= $(LOCALBIN)/setup-envtest
GOLANGCI_LINT = $(LOCALBIN)/golangci-lint

## Tool Versions
KUSTOMIZE_VERSION ?= v5.6.0
CONTROLLER_TOOLS_VERSION ?= v0.18.0
#ENVTEST_VERSION is the version of controller-runtime release branch to fetch the envtest setup script (i.e. release-0.20)
ENVTEST_VERSION ?= $(shell go list -m -f "{{ .Version }}" sigs.k8s.io/controller-runtime | awk -F'[v.]' '{printf "release-%d.%d", $$2, $$3}')
#ENVTEST_K8S_VERSION is the version of Kubernetes to use for setting up ENVTEST binaries (i.e. 1.31)
ENVTEST_K8S_VERSION ?= $(shell go list -m -f "{{ .Version }}" k8s.io/api | awk -F'[v.]' '{printf "1.%d", $$3}')
GOLANGCI_LINT_VERSION ?= v2.1.0

.PHONY: kustomize
kustomize: $(KUSTOMIZE) ## Download kustomize locally if necessary.
$(KUSTOMIZE): $(LOCALBIN)
	$(call go-install-tool,$(KUSTOMIZE),sigs.k8s.io/kustomize/kustomize/v5,$(KUSTOMIZE_VERSION))

.PHONY: controller-gen
controller-gen: $(CONTROLLER_GEN) ## Download controller-gen locally if necessary.
$(CONTROLLER_GEN): $(LOCALBIN)
	$(call go-install-tool,$(CONTROLLER_GEN),sigs.k8s.io/controller-tools/cmd/controller-gen,$(CONTROLLER_TOOLS_VERSION))

.PHONY: setup-envtest
setup-envtest: envtest ## Download the binaries required for ENVTEST in the local bin directory.
	@echo "Setting up envtest binaries for Kubernetes version $(ENVTEST_K8S_VERSION)..."
	@$(ENVTEST) use $(ENVTEST_K8S_VERSION) --bin-dir $(LOCALBIN) -p path || { \
		echo "Error: Failed to set up envtest binaries for version $(ENVTEST_K8S_VERSION)."; \
		exit 1; \
	}

.PHONY: envtest
envtest: $(ENVTEST) ## Download setup-envtest locally if necessary.
$(ENVTEST): $(LOCALBIN)
	$(call go-install-tool,$(ENVTEST),sigs.k8s.io/controller-runtime/tools/setup-envtest,$(ENVTEST_VERSION))

.PHONY: golangci-lint
golangci-lint: $(GOLANGCI_LINT) ## Download golangci-lint locally if necessary.
$(GOLANGCI_LINT): $(LOCALBIN)
	$(call go-install-tool,$(GOLANGCI_LINT),github.com/golangci/golangci-lint/v2/cmd/golangci-lint,$(GOLANGCI_LINT_VERSION))

# go-install-tool will 'go install' any package with custom target and name of binary, if it doesn't exist
# $1 - target path with name of binary
# $2 - package url which can be installed
# $3 - specific version of package
define go-install-tool
@[ -f "$(1)-$(3)" ] || { \
set -e; \
package=$(2)@$(3) ;\
echo "Downloading $${package}" ;\
rm -f $(1) || true ;\
GOBIN=$(LOCALBIN) go install $${package} ;\
mv $(1) $(1)-$(3) ;\
} ;\
ln -sf $(1)-$(3) $(1)
endef

.PHONY: operator-sdk
OPERATOR_SDK ?= $(LOCALBIN)/operator-sdk
operator-sdk: ## Download operator-sdk locally if necessary.
ifeq (,$(wildcard $(OPERATOR_SDK)))
ifeq (, $(shell which operator-sdk 2>/dev/null))
	@{ \
	set -e ;\
	mkdir -p $(dir $(OPERATOR_SDK)) ;\
	OS=$(shell go env GOOS) && ARCH=$(shell go env GOARCH) && \
	curl -sSLo $(OPERATOR_SDK) https://github.com/operator-framework/operator-sdk/releases/download/$(OPERATOR_SDK_VERSION)/operator-sdk_$${OS}_$${ARCH} ;\
	chmod +x $(OPERATOR_SDK) ;\
	}
else
OPERATOR_SDK = $(shell which operator-sdk)
endif
endif

.PHONY: bundle
bundle: manifests kustomize operator-sdk ## Generate bundle manifests and metadata, then validate generated files.
	$(OPERATOR_SDK) generate kustomize manifests -q
	cd config/manager && $(KUSTOMIZE) edit set image controller=$(IMG)
	$(KUSTOMIZE) build config/manifests | $(OPERATOR_SDK) generate bundle $(BUNDLE_GEN_FLAGS)
	sed -i 's#containerImage: .*#containerImage: $(IMG)#' bundle/manifests/unifai-operator.clusterserviceversion.yaml
	python3 hack/csv_metrics_scraper.py bundle/manifests/unifai-operator.clusterserviceversion.yaml unifai-operator-metrics-scraper
	$(OPERATOR_SDK) bundle validate ./bundle

.PHONY: bundle-build
bundle-build: ## Build the bundle image.
	chmod -R a+rX bundle
	$(CONTAINER_TOOL) build -f bundle.Dockerfile -t $(BUNDLE_IMG) .

.PHONY: bundle-push
bundle-push: ## Push the bundle image.
	$(MAKE) docker-push IMG=$(BUNDLE_IMG)

.PHONY: opm
OPM = $(LOCALBIN)/opm
opm: ## Download opm locally if necessary.
ifeq (,$(wildcard $(OPM)))
ifeq (,$(shell which opm 2>/dev/null))
	@{ \
	set -e ;\
	mkdir -p $(dir $(OPM)) ;\
	OS=$(shell go env GOOS) && ARCH=$(shell go env GOARCH) && \
	curl -sSLo $(OPM) https://github.com/operator-framework/operator-registry/releases/download/v1.55.0/$${OS}-$${ARCH}-opm ;\
	chmod +x $(OPM) ;\
	}
else
OPM = $(shell which opm)
endif
endif

# File-based catalog (FBC): catalog-template.yaml (olm.template.basic) lists every released bundle with its
# channels; `make catalog-add` records the current VERSION, `make catalog` renders catalog/ from the template.
CATALOG_IMG ?= $(IMAGE_TAG_BASE)-catalog:latest

# Release flow: `make release` (tests, image, canary e2e, bundle, catalog on alpha) then `make promote` (stable).
# demo333 subscribes to stable: production changes only on promotion.
CANARY_NS ?= unifai-operator-canary

.PHONY: canary-deploy
canary-deploy: manifests kustomize ## Deploy IMG as a canary instance (only reconciles objects labelled operator-instance=canary).
	kubectl apply --server-side --force-conflicts -f config/crd/bases
	cd config/canary && $(KUSTOMIZE) edit set image $(IMAGE_TAG_BASE)=$(IMG)
	$(KUSTOMIZE) build config/canary | kubectl apply -f -
	kubectl -n $(CANARY_NS) rollout restart deploy/unifai-operator-canary-controller-manager
	kubectl -n $(CANARY_NS) rollout status deploy/unifai-operator-canary-controller-manager --timeout=300s
	@img=$$(kubectl -n $(CANARY_NS) get deploy/unifai-operator-canary-controller-manager -o jsonpath='{.spec.template.spec.containers[0].image}'); \
	  [ "$$img" = "$(IMG)" ] || { echo "canary runs $$img, expected $(IMG)"; exit 1; }

.PHONY: canary-e2e
canary-e2e: ## Run the e2e suite against the canary instance (upgrade test from the OLM instance included).
	$(MAKE) test-e2e E2E_OPERATOR_INSTANCE=canary E2E_OPERATOR_NAMESPACE=$(CANARY_NS) E2E_UPGRADE=1 E2E_CANDIDATE_VERSION=$(VERSION)

.PHONY: canary-delete
canary-delete: kustomize ## Remove the canary instance.
	$(KUSTOMIZE) build config/canary | kubectl delete --ignore-not-found -f -

.PHONY: release
release: test docker-build-local docker-push canary-deploy canary-e2e canary-delete bundle bundle-build bundle-push ## Test, build, canary e2e, publish VERSION on alpha.
	$(MAKE) catalog-add CHANNELS=alpha
	$(MAKE) catalog-build catalog-push

.PHONY: promote
promote: ## Publish VERSION on stable (production).
	$(MAKE) catalog-add CHANNELS=stable
	$(MAKE) catalog-build catalog-push

.PHONY: charts
charts: ## Copy the upstream UnifAI charts and values into internal/stack/assets (embedded in the operator).
	./hack/sync-charts.sh ../../helm

.PHONY: charts-check
charts-check: ## Fail when the embedded charts differ from the upstream helm/ directory.
	./hack/sync-charts.sh --check ../../helm

.PHONY: catalog-add
catalog-add: ## Add bundle VERSION to catalog-template.yaml in CHANNELS (comma-separated), replacing each channel head.
	python3 hack/catalog_add.py catalog-template.yaml unifai-operator $(VERSION) $(BUNDLE_IMG) $(CHANNELS)

.PHONY: catalog
catalog: opm ## Render and validate the file-based catalog in catalog/.
	mkdir -p catalog/unifai-operator
	$(OPM) alpha render-template basic catalog-template.yaml -o yaml > catalog/unifai-operator/catalog.yaml
	$(OPM) validate catalog
	chmod -R a+rX catalog

.PHONY: catalog-build
catalog-build: catalog ## Build the catalog image.
	$(CONTAINER_TOOL) build --platform linux/amd64 -f catalog.Dockerfile -t $(CATALOG_IMG) .

# Push the catalog image.
.PHONY: catalog-push
catalog-push: ## Push a catalog image.
	$(MAKE) docker-push IMG=$(CATALOG_IMG)
