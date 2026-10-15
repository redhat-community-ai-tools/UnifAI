# Fork tooling for UnifAI: images (quay.io), Helm deployment, upstream sync, release, contributions.
# Branch model: main = strict mirror of upstream/main (ff-only); devel = main + fork delta;
# feature branches start from main, are merged into devel to test, and can become upstream PRs.
SHELL := /bin/bash
-include fork.mk

QUAY_ORG             ?= CHANGEME
REGISTRY             ?= quay.io/$(QUAY_ORG)
IMAGE_PREFIX         ?= unifai
ENGINE               ?= podman
DEVEL_TAG            ?= devel
NAMESPACE            ?= unifai-devel
DEPLOY_TAG           ?= $(DEVEL_TAG)
DEPLOY_MODULES       ?= rag multiagent backend identity ui
SHARED_MODULE        := shared-resources
UPSTREAM_REPO        ?= redhat-community-ai-tools/UnifAI
UPSTREAM_URL         ?= https://github.com/$(UPSTREAM_REPO).git
TAG_PREFIX           ?= v
RENDER_DIR           ?= .fork/helm
COMPONENTS           := rag multi-agent backend identity ui
DOCKERFILE_rag         = rag/Dockerfile
DOCKERFILE_multi-agent = multi-agent/Dockerfile
DOCKERFILE_backend     = backend/Dockerfile
DOCKERFILE_identity    = shared-resources/identity/Dockerfile
DOCKERFILE_ui          = ui/deployment/Dockerfile
IMAGE_multi-agent      = multiagent
BUILD_ARGS_multi-agent = --build-arg CERT_URL=
TAG                  ?= $(DEVEL_TAG)
export REGISTRY IMAGE_PREFIX UI_HOST IDENTITY_HOST_NAME STORAGE_CLASS SHARED_STORAGE_CLASS DOCLING_URL EMBEDDING_URL

.DEFAULT_GOAL := help
.PHONY: help init status login sync-main merge-main-to-devel sync-all feature-start feature-to-devel \
        ui-certs build-all push-all images-devel overlay helm-lint deploy-shared deploy-diff deploy \
        release contrib-update contrib-check contrib-pr contrib-ready

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_%-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-22s %s\n", $$1, $$2}'

# --- helpers -----------------------------------------------------------------------------------
define img
$(REGISTRY)/$(IMAGE_PREFIX)-$(or $(IMAGE_$(1)),$(1))
endef
define require_clean
@test -z "$$(git status --porcelain)" || { echo "working tree not clean"; exit 1; }
endef
define require_branch
@test "$$(git branch --show-current)" = "$(1)" || { echo "must be on branch $(1)"; exit 1; }
endef
check-quay:
	@test "$(QUAY_ORG)" != "CHANGEME" || { echo "set QUAY_ORG in fork.mk"; exit 1; }

# --- setup & state -------------------------------------------------------------------------------
init: ## Add upstream remote (no push anywhere by default), create devel, install the fork-only guard hooks, hide local files
	git remote get-url upstream >/dev/null 2>&1 || git remote add upstream $(UPSTREAM_URL)
	git config remote.upstream.pushurl DISABLED
	git config remote.upstream.tagOpt --no-tags
	git config remote.origin.pushurl DISABLED
	git fetch upstream --no-tags
	git show-ref --verify --quiet refs/heads/devel || git branch devel main
	for h in pre-commit pre-merge-commit; do install -m 755 fork/hooks/guard-fork-only $$(git rev-parse --git-path hooks)/$$h; done
	@grep -qxF '.fork/' .git/info/exclude || echo '.fork/' >> .git/info/exclude
	@grep -qxF 'fork.mk' .git/info/exclude || echo 'fork.mk' >> .git/info/exclude
	@grep -qxF 'ui/UnifAI-secrets/' .git/info/exclude || echo 'ui/UnifAI-secrets/' >> .git/info/exclude
	@echo "origin/upstream pushes are DISABLED; run 'git config --unset remote.origin.pushurl' to publish."

status: ## main vs upstream/main, devel vs main
	@git fetch upstream --no-tags -q
	@echo "main  vs upstream/main : $$(git rev-list --left-right --count main...upstream/main | awk '{print "ahead " $$1 ", behind " $$2}')"
	@echo "devel vs main          : $$(git rev-list --left-right --count devel...main | awk '{print "ahead " $$1 ", behind " $$2}')"

login: check-quay ## podman login quay.io
	$(ENGINE) login quay.io

# --- synchronisation -----------------------------------------------------------------------------
sync-main: ## upstream/main -> main (ff-only, local)
	$(require_clean)
	git fetch upstream --no-tags
	git switch main
	git merge --ff-only upstream/main

merge-main-to-devel: ## main -> devel (merge, local)
	$(require_clean)
	git switch devel
	git merge --no-edit main

sync-all: sync-main merge-main-to-devel ## sync-main then merge-main-to-devel

feature-start: ## Create a feature branch from main: make feature-start BRANCH=fix/foo
	@test -n "$(BRANCH)" || { echo "BRANCH=... required"; exit 1; }
	$(require_clean)
	git switch -c $(BRANCH) main

feature-to-devel: ## Merge the current feature branch into devel (--no-ff, local)
	$(require_clean)
	@b=$$(git branch --show-current); case $$b in main|devel) echo "run from a feature branch"; exit 1;; esac; \
	git switch devel && git merge --no-ff -m "Merge branch '$$b' into devel" $$b

# --- images --------------------------------------------------------------------------------------
ui-certs: ## Self-signed certs for the UI image (nginx expects unifai.crt/unifai.key)
	mkdir -p ui/UnifAI-secrets/certificates
	openssl req -x509 -nodes -newkey rsa:2048 -days 365 -subj "/CN=unifai" \
	  -keyout ui/UnifAI-secrets/certificates/unifai.key -out ui/UnifAI-secrets/certificates/unifai.crt

build-%: check-quay ## Build one component (rag multi-agent backend identity ui); TAG=...
	$(ENGINE) build $(BUILD_ARGS_$*) -t $(call img,$*):$(TAG) -f $(DOCKERFILE_$*) .

push-%: check-quay ## Push one component (local image must exist)
	$(ENGINE) push $(call img,$*):$(TAG)

build-all: $(addprefix build-,$(COMPONENTS)) ## Build every component
push-all: $(addprefix push-,$(COMPONENTS)) ## Push every component

images-devel: ## Build+push :devel and :devel-<sha> (devel branch only, FORCE=1 to bypass)
	@test "$(FORCE)" = 1 || test "$$(git branch --show-current)" = devel || { echo "run from devel (or FORCE=1)"; exit 1; }
	$(MAKE) build-all TAG=$(DEVEL_TAG)
	for c in $(COMPONENTS); do $(ENGINE) tag $(REGISTRY)/$(IMAGE_PREFIX)-$${c/multi-agent/multiagent}:$(DEVEL_TAG) \
	  $(REGISTRY)/$(IMAGE_PREFIX)-$${c/multi-agent/multiagent}:$(DEVEL_TAG)-$$(git rev-parse --short HEAD); done
	$(MAKE) push-all TAG=$(DEVEL_TAG)
	$(MAKE) push-all TAG=$(DEVEL_TAG)-$$(git rev-parse --short HEAD)

# --- deployment ----------------------------------------------------------------------------------
overlay: check-quay ## Render helm/ + fork overlays into $(RENDER_DIR)
	IMAGE_TAG=$(DEPLOY_TAG) python3 -I fork/render_values.py $(RENDER_DIR)

helm-lint: overlay ## helm lint the charts used by the helmfiles (warn only; STRICT=1 to fail)
	@fail=0; for c in $$(grep -hE '^\s*chart: \./' $(RENDER_DIR)/*.gotmpl | sed 's/.*chart: //' | sort -u); do \
	  helm lint $(RENDER_DIR)/$$c >/dev/null 2>&1 || { echo "lint failed: $$c"; fail=1; }; done; \
	  test $$fail = 0 && echo "helm lint OK"; test "$(STRICT)" = 1 && exit $$fail; exit 0

deploy-shared: overlay ## Deploy MongoDB, RabbitMQ, Qdrant, Redis, Temporal (once)
	cd $(RENDER_DIR) && helmfile -n $(NAMESPACE) -f $(SHARED_MODULE).yaml.gotmpl apply

deploy-diff: overlay ## helmfile diff of $(DEPLOY_MODULES)
	cd $(RENDER_DIR) && for m in $(DEPLOY_MODULES); do helmfile -n $(NAMESPACE) -f $$m.yaml.gotmpl diff; done

deploy: overlay ## helmfile apply of $(DEPLOY_MODULES) (DEPLOY_TAG=devel|vX.Y.Z)
	cd $(RENDER_DIR) && for m in $(DEPLOY_MODULES); do helmfile -n $(NAMESPACE) -f $$m.yaml.gotmpl apply || exit 1; done

# --- release (publishes images + tag: only run when you intend to publish) ---------------------------
release: check-quay ## From devel: make release VERSION=1.2.3 [LATEST=1] -- pushes images (tag stays local)
	@echo "$(VERSION)" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$$' || { echo "VERSION must be semver"; exit 1; }
	$(call require_branch,devel)
	$(require_clean)
	@! git rev-parse -q --verify refs/tags/$(TAG_PREFIX)$(VERSION) >/dev/null || { echo "tag exists"; exit 1; }
	$(MAKE) build-all push-all TAG=$(TAG_PREFIX)$(VERSION)
	@if [ "$(LATEST)" = 1 ]; then for c in $(COMPONENTS); do n=$${c/multi-agent/multiagent}; \
	  $(ENGINE) tag $(REGISTRY)/$(IMAGE_PREFIX)-$$n:$(TAG_PREFIX)$(VERSION) $(REGISTRY)/$(IMAGE_PREFIX)-$$n:latest && \
	  $(ENGINE) push $(REGISTRY)/$(IMAGE_PREFIX)-$$n:latest; done; fi
	git tag -a $(TAG_PREFIX)$(VERSION) -m "Release $(VERSION)"
	@echo "tag $(TAG_PREFIX)$(VERSION) created locally; publish with: git push origin $(TAG_PREFIX)$(VERSION)"

# --- contributions to upstream -------------------------------------------------------------------
contrib-update: ## Rebase the current feature branch on upstream/main
	$(require_clean)
	git fetch upstream --no-tags
	git rebase upstream/main

contrib-check: ## Pre-PR checks reproducing upstream review rules
	bash fork/contrib-check.sh

contrib-pr: contrib-check ## Open a draft PR to upstream: make contrib-pr TITLE="feat: ..." [BODY=file.md]
	@test -n "$(TITLE)" || { echo "TITLE=... required"; exit 1; }
	git push -u origin HEAD
	gh pr create --repo $(UPSTREAM_REPO) --base main --head "$$(gh api user -q .login):$$(git branch --show-current)" \
	  --title "$(TITLE)" $(if $(BODY),--body-file $(BODY),--fill) $(if $(filter 0,$(DRAFT)),,--draft)

contrib-ready: ## Mark a PR ready for review: make contrib-ready PR=123
	@test -n "$(PR)" || { echo "PR=... required"; exit 1; }
	gh pr ready $(PR) --repo $(UPSTREAM_REPO)
