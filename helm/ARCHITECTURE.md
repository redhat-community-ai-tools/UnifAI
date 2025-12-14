# UnifAI Helm Deployment Architecture & Convention Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Repository Structure](#repository-structure)
4. [Deployment Architecture](#deployment-architecture)
5. [Helmfile Configuration](#helmfile-configuration)
6. [Chart Conventions](#chart-conventions)
7. [Values Management](#values-management)
8. [Hooks System](#hooks-system)
9. [Deployment Workflows](#deployment-workflows)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The UnifAI Helm infrastructure provides **declarative Kubernetes deployments** using Helm charts orchestrated by Helmfile. The system supports multiple deployment targets, modular component architecture, and lifecycle hooks for complex initialization sequences.

**Core Features:**
- Helmfile-based deployment orchestration
- Modular chart architecture (shared resources, application components)
- Environment-specific value overrides
- Pre/post-sync lifecycle hooks
- Dependency management between components
- ConfigMap-based dynamic configuration
- OpenShift Route integration

**Deployment Layers:**
1. **Shared Resources**: MongoDB, RabbitMQ, Qdrant, SSO
2. **Application Modules**: Dataflow, Multi-Agent, UI
3. **Supporting Services**: Docling, vLLM serving engines

---

## Technology Stack

### Core Technologies
- **Helm 3.x** - Kubernetes package manager
- **Helmfile 0.x** - Declarative Helm chart deployment
- **Kubernetes 1.27+** - Container orchestration
- **OpenShift 4.x** - Enterprise Kubernetes platform
- **Bash** - Lifecycle hook scripts

### Chart Template Engine
- **Go Templates** - Helm templating language
- **Sprig Functions** - Extended template functions
- **YAML** - Declarative configuration format

### Storage & Databases
- **MongoDB** - Document database (replicated)
- **RabbitMQ** - Message queue
- **Qdrant** - Vector database
- **PVC** - Persistent volume claims for shared storage

---

## Repository Structure

```
helm/
├── shared-resources/              # 🔧 Infrastructure components
│   ├── mongodb/                   # MongoDB StatefulSet (replicated)
│   ├── rabbitmq/                  # RabbitMQ messaging
│   ├── qdrant/                    # Vector database
│   ├── sso/                       # SSO authentication service
│   ├── docling/                   # Document processing service
│   ├── vllm-serving-engine/       # LLM serving infrastructure
│   ├── shared-config/             # Shared ConfigMap definitions
│   └── unifai-dataflow-shared-storage/  # PVC for dataflow
│
├── dataflow/                      # 📊 Data Pipeline Hub components
│   ├── unifai-dataflow-server/    # Flask backend server
│   ├── unifai-dataflow-celery/    # Celery worker pods
│   ├── unifai-dataflow-config/    # ConfigMap for dataflow
│   ├── unifai-dataflow-secrets/   # Secret templates
│   └── unifai-dataflow-shared-storage/  # PVC definitions
│
├── multiagent/                    # 🤖 Multi-Agent System
│   ├── be/                        # Backend service chart
│   └── multiagent-config/         # ConfigMap for multi-agent
│
├── ui/                            # 🎨 Frontend application
│   ├── templates/                 # Deployment, Service, Route
│   └── values.yaml
│
├── values/                        # 📝 Value files (environment configs)
│   ├── global-config.yaml         # Global environment variables
│   ├── shared-resource-values.yaml  # Shared resources config
│   ├── dataflow-resource-values.yaml  # Dataflow config
│   ├── multiagent-resource-values.yaml  # Multi-agent config
│   ├── ui-values.yaml             # UI config
│   ├── sso-values.yaml            # SSO config
│   ├── docling-values-cpu.yaml    # Docling (CPU mode)
│   ├── docling-values-gpu.yaml    # Docling (GPU mode)
│   └── vllm-*.yaml                # vLLM model-specific configs
│
├── helmfile1.yaml.gotmpl          # 🔗 Shared resources orchestration
├── dataflow.yaml.gotmpl           # 🔗 Dataflow deployment
├── multiagent.yaml.gotmpl         # 🔗 Multi-agent deployment
├── ui.yaml.gotmpl                 # 🔗 UI deployment
├── sso.yaml.gotmpl                # 🔗 SSO deployment
├── shared-resources.yaml.gotmpl   # 🔗 Extended shared resources
│
├── dataflow-presync.sh            # 🪝 Dataflow pre-deployment hook
├── dataflow-postsync.sh           # 🪝 Dataflow post-deployment hook
├── postsync.sh                    # 🪝 Shared resources post-hook
│
├── helmfile1.yaml                 # Static helmfile (if no templating)
├── helmfile2.yaml                 # Static helmfile (secondary)
└── README.md                      # User documentation
```

### Chart Anatomy

Standard Helm chart structure (example: `dataflow/unifai-dataflow-server/`):

```
unifai-dataflow-server/
├── Chart.yaml                     # Chart metadata (name, version, appVersion)
├── values.yaml                    # Default values
├── templates/
│   ├── _helpers.tpl               # Named templates (labels, selectors, etc.)
│   ├── deployment.yaml            # Deployment manifest
│   ├── service.yaml               # Service manifest
│   ├── route.yaml                 # OpenShift Route (external access)
│   ├── ingress.yaml               # Kubernetes Ingress (optional)
│   ├── serviceaccount.yaml        # ServiceAccount
│   ├── hpa.yaml                   # HorizontalPodAutoscaler (optional)
│   ├── NOTES.txt                  # Post-install instructions
│   └── tests/
│       └── test-connection.yaml   # Helm test manifest
└── .helmignore                    # Files to exclude from chart
```

---

## Deployment Architecture

### Layered Deployment Model

UnifAI uses a **3-tier deployment architecture**:

```
┌──────────────────────────────────────────────────────────────┐
│                    TIER 1: Shared Resources                   │
│  (helmfile1.yaml.gotmpl)                                      │
│                                                               │
│  ┌──────────┐  ┌─────────┐  ┌────────┐  ┌──────────────┐   │
│  │ MongoDB  │  │ RabbitMQ│  │ Qdrant │  │ Shared Config│   │
│  │(StatefulSet)│(StatefulSet)│(Deploy) │  │ (ConfigMap)  │   │
│  └──────────┘  └─────────┘  └────────┘  └──────────────┘   │
│       ↓              ↓            ↓              ↓           │
│  [Postsync Hook: Create shared-config with service IPs]     │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ depends on
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                TIER 2: Application Components                 │
│  (dataflow.yaml, multiagent.yaml, sso.yaml)                  │
│                                                               │
│  ┌─────────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ Dataflow Server │   │ Multi-Agent  │   │     SSO      │ │
│  │   (Deployment)  │   │  (Deployment)│   │ (Deployment) │ │
│  └────────┬────────┘   └──────┬───────┘   └──────┬───────┘ │
│           │                   │                   │          │
│  ┌────────┴────────┐   ┌──────┴───────┐          │          │
│  │ Dataflow Celery │   │ MA Config    │          │          │
│  │   (Deployment)  │   │ (ConfigMap)  │          │          │
│  └─────────────────┘   └──────────────┘          │          │
│           │                                       │          │
│  ┌────────┴─────────┐                            │          │
│  │ Dataflow Config  │                            │          │
│  │   (ConfigMap)    │                            │          │
│  └──────────────────┘                            │          │
│  [Presync Hook: Create secrets]                  │          │
│  [Postsync Hook: Initialize collections]         │          │
└──────────────────────────────────────────────────┼──────────┘
                              │                    │
                              │ proxied by         │
                              ▼                    ▼
┌──────────────────────────────────────────────────────────────┐
│                      TIER 3: Frontend                         │
│  (ui.yaml)                                                    │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  UI (Deployment) with Nginx                              │ │
│  │  Routes: /api1 → Dataflow, /api2 → Multi-Agent          │ │
│  │          /api3 → SSO                                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                              │                                │
│                              ▼                                │
│  [OpenShift Route: External HTTPS Access]                    │
└──────────────────────────────────────────────────────────────┘
```

### Component Dependencies

**Dependency Graph:**

```
MongoDB, RabbitMQ, Qdrant (parallel)
    │
    ├─> Shared Config (waits for all)
    │       │
    │       ├─> Dataflow Server
    │       │       ├─> Dataflow Celery
    │       │       └─> Dataflow Config
    │       │
    │       ├─> Multi-Agent Backend
    │       │       └─> Multi-Agent Config
    │       │
    │       └─> SSO Backend
    │
    └─> UI (waits for backends)
```

**Helmfile `needs` Directive:**

```yaml
releases:
  - name: unifai-shared-config
    needs:
      - unifai-mongodb
      - unifai-qdrant
      - unifai-rabbitmq
  
  - name: unifai-dataflow-config
    needs:
      - unifai-dataflow-server
      - unifai-dataflow-celery
```

---

## Helmfile Configuration

### Helmfile Structure (`.gotmpl` Files)

**Purpose:** Helmfile orchestrates multiple Helm chart deployments with dependency management.

**Template Example: `dataflow.yaml.gotmpl`**

```yaml
environments:
  default:
    values:
      - ./values/dataflow-resource-values.yaml

---

helmDefaults:
  createNamespace: false  # Namespace pre-created
  wait: false             # Don't wait by default

releases:
  - name: unifai-dataflow-server
    chart: ./dataflow/unifai-dataflow-server
    wait: true            # Override: wait for this release
    hooks:
      - events: ["presync"]
        showlogs: true
        command: bash
        args:
          - "./dataflow-presync.sh"
    values:
      - {{- toYaml .Values.unifai_dataflow_server | nindent 8 }}
      - ./values/global-config.yaml

  - name: unifai-dataflow-celery
    chart: ./dataflow/unifai-dataflow-celery
    version: "0.9.0"      # Pin specific chart version
    wait: true
    values:
      - {{- toYaml .Values.unifai_dataflow_celery | nindent 8 }}
      - ./values/global-config.yaml

  - name: unifai-dataflow-config
    chart: ./dataflow/unifai-dataflow-config
    wait: true
    needs:                # Dependencies
      - unifai-dataflow-server
      - unifai-dataflow-celery
    hooks:
      - events: ["postsync"]
        showlogs: true
        command: bash
        args:
          - "./dataflow-postsync.sh"
```

### Helmfile Commands

**Deploy all releases:**
```bash
helmfile -f dataflow.yaml.gotmpl apply
```

**Deploy specific release:**
```bash
helmfile -f dataflow.yaml.gotmpl -l name=unifai-dataflow-server apply
```

**Sync (deploy without hooks):**
```bash
helmfile -f dataflow.yaml.gotmpl sync
```

**Destroy (delete all releases):**
```bash
helmfile -f dataflow.yaml.gotmpl destroy
```

**Diff (preview changes):**
```bash
helmfile -f dataflow.yaml.gotmpl diff
```

**Lint charts:**
```bash
helmfile -f dataflow.yaml.gotmpl lint
```

---

## Chart Conventions

### Chart.yaml Structure

```yaml
apiVersion: v2
name: unifai-dataflow-server
description: UnifAI Data Pipeline Hub Backend Server
type: application
version: 0.9.0          # Chart version (semantic versioning)
appVersion: "2024.12.01"  # Application version (auto-updated by CI)
keywords:
  - unifai
  - dataflow
  - backend
maintainers:
  - name: UnifAI Team
home: https://github.com/redhat-community-ai-tools/UnifAI
sources:
  - https://github.com/redhat-community-ai-tools/UnifAI
```

**Version Update Strategy:**
- `version`: Manually incremented on chart changes
- `appVersion`: Auto-updated by CI/CD pipeline with image version

### Values.yaml Structure

```yaml
# Global Environment Variables
env:
  QDRANT_IP: "http://qdrant"
  QDRANT_PORT: "6333"
  FRONTEND_URL: "http://10.46.253.0:5000"
  BACKEND_ENV: "production"
  ROLE: "flask"
  SHARED_STORAGE: "/app/shared"

# Debug mode (enables verbose logging)
debug: false

# ConfigMap references
globalConfigMapName: shared-config

# Replica count
replicaCount: 1

# Container image
image:
  repository: images.paas.redhat.com/unifai/backend
  tag: latest
  pullPolicy: Always

# Service configuration
service:
  type: ClusterIP
  port: 13456

# Resource limits
resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi

# Autoscaling (optional)
autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80

# OpenShift Route
route:
  enabled: true
  host: unifai-dataflow-server-tag-ai--pipeline.apps.example.com
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect

# Tolerations (GPU nodes)
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule

# Node affinity
affinity: {}

# Volume mounts
volumeMounts:
  - name: shared-storage
    mountPath: /app/shared

# Volumes
volumes:
  - name: shared-storage
    persistentVolumeClaim:
      claimName: unifai-shared-pvc
```

### Template Helpers (`_helpers.tpl`)

```yaml
{{/*
Expand the name of the chart.
*/}}
{{- define "unifai-dataflow-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "unifai-dataflow-server.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "unifai-dataflow-server.labels" -}}
helm.sh/chart: {{ include "unifai-dataflow-server.chart" . }}
{{ include "unifai-dataflow-server.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "unifai-dataflow-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "unifai-dataflow-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

### Deployment Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "unifai-dataflow-server.fullname" . }}
  labels:
    {{- include "unifai-dataflow-server.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "unifai-dataflow-server.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
      labels:
        {{- include "unifai-dataflow-server.selectorLabels" . | nindent 8 }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        ports:
        - name: http
          containerPort: {{ .Values.service.port }}
          protocol: TCP
        env:
        {{- range $key, $value := .Values.env }}
        - name: {{ $key }}
          value: {{ $value | quote }}
        {{- end }}
        envFrom:
        - configMapRef:
            name: {{ .Values.globalConfigMapName }}
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
        volumeMounts:
          {{- toYaml .Values.volumeMounts | nindent 10 }}
      volumes:
        {{- toYaml .Values.volumes | nindent 8 }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

### OpenShift Route Template

```yaml
{{- if .Values.route.enabled -}}
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: {{ include "unifai-dataflow-server.fullname" . }}
  labels:
    {{- include "unifai-dataflow-server.labels" . | nindent 4 }}
spec:
  host: {{ .Values.route.host }}
  to:
    kind: Service
    name: {{ include "unifai-dataflow-server.fullname" . }}
    weight: 100
  port:
    targetPort: http
  {{- if .Values.route.tls }}
  tls:
    termination: {{ .Values.route.tls.termination }}
    insecureEdgeTerminationPolicy: {{ .Values.route.tls.insecureEdgeTerminationPolicy }}
  {{- end }}
{{- end }}
```

---

## Values Management

### Value Hierarchy

Helm merges values in this order (later overrides earlier):

1. `chart/values.yaml` (chart defaults)
2. Helmfile environment values
3. Helmfile release-specific values
4. `--set` flags (highest priority)

**Example:**

```yaml
# 1. Chart default (dataflow/unifai-dataflow-server/values.yaml)
replicaCount: 1

# 2. Environment values (values/dataflow-resource-values.yaml)
unifai_dataflow_server:
  replicaCount: 3

# 3. Helmfile release values (dataflow.yaml.gotmpl)
releases:
  - name: unifai-dataflow-server
    values:
      - replicaCount: 5  # This wins
```

### Global Config Pattern

**File: `values/global-config.yaml`**

```yaml
env:
  FRONTEND_URL: "https://unifai-ui-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
  DATAPIPELINEHUB_HOST: "unifai-dataflow-server"
  DATAPIPELINEHUB_PORT: "13456"
  MULTIAGENT_HOST: "unifai-multiagent-be"
  MULTIAGENT_PORT: "8003"
  SSO_BACKEND_HOST: "https://unifai-sso-backend-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
```

**Usage in Helmfile:**

```yaml
releases:
  - name: unifai-dataflow-server
    values:
      - ./values/global-config.yaml  # Merged with component-specific values
```

**Usage in Deployment:**

```yaml
envFrom:
  - configMapRef:
      name: shared-config  # References dynamically-created ConfigMap
```

### Component-Specific Values

**File: `values/dataflow-resource-values.yaml`**

```yaml
unifai_dataflow_server:
  replicaCount: 2
  image:
    repository: images.paas.redhat.com/unifai/backend
    tag: latest
  resources:
    limits:
      cpu: 2000m
      memory: 4Gi
  env:
    ROLE: "flask"
    BACKEND_ENV: "production"

unifai_dataflow_celery:
  replicaCount: 3
  image:
    repository: images.paas.redhat.com/unifai/backend
    tag: latest
  resources:
    limits:
      cpu: 1000m
      memory: 2Gi
  env:
    ROLE: "celery"
```

**Reference in Helmfile:**

```yaml
releases:
  - name: unifai-dataflow-server
    values:
      - {{- toYaml .Values.unifai_dataflow_server | nindent 8 }}
```

---

## Hooks System

### Hook Types

Helmfile supports lifecycle hooks at release level:

| Hook Type | When Executed | Use Case |
|-----------|---------------|----------|
| `presync` | Before `helm install/upgrade` | Create secrets, validate prerequisites |
| `postsync` | After successful `helm install/upgrade` | Initialize databases, create ConfigMaps |
| `preuninstall` | Before `helm uninstall` | Backup data, notify systems |
| `postuninstall` | After `helm uninstall` | Cleanup resources, delete PVCs |

### Presync Hook: Secret Creation

**File: `dataflow-presync.sh`**

```bash
#!/bin/bash
set -e
set -o pipefail

log_info() { echo -e "\033[0;32m[INFO]\033[0m $1"; }
log_warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

log_info "Starting presync hook for dataflow"

# Validate environment variables
MISSING_VARS=()
if [[ -z "${default_slack_bot_token}" ]]; then
    MISSING_VARS+=("default_slack_bot_token")
fi
if [[ -z "${default_slack_user_token}" ]]; then
    MISSING_VARS+=("default_slack_user_token")
fi

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    log_warn "Missing environment variables: ${MISSING_VARS[@]}"
    log_warn "Secret will be created with empty values."
fi

# Create Secret
log_info "Creating/updating Secret 'unifai-dataflow-secrets'..."
kubectl create secret generic unifai-dataflow-secrets \
    --from-literal=slack_bot_token="${default_slack_bot_token:-}" \
    --from-literal=slack_user_token="${default_slack_user_token:-}" \
    --dry-run=client -o yaml | kubectl apply -f -

log_info "✅ Presync hook completed successfully"
```

**Helmfile Configuration:**

```yaml
releases:
  - name: unifai-dataflow-server
    hooks:
      - events: ["presync"]
        showlogs: true
        command: bash
        args:
          - "./dataflow-presync.sh"
```

### Postsync Hook: ConfigMap Creation

**File: `dataflow-postsync.sh`**

```bash
#!/bin/bash
set -e
set -o pipefail

log_info() { echo -e "\033[0;32m[INFO]\033[0m $1"; }

log_info "Starting postsync hook for dataflow"

# Wait for service to be ready
wait_for_port() {
    local svc=$1
    log_info "Waiting for service '$svc' port..."
    for i in {1..60}; do
        port=$(kubectl get svc "$svc" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null)
        if [[ -n "$port" ]]; then
            log_info "Service '$svc' port found: $port"
            echo "$port"
            return 0
        fi
        sleep 10
    done
    log_error "Timeout waiting for service '$svc'"
    return 1
}

# Get service details
DATAFLOW_PORT=$(wait_for_port "unifai-dataflow-server")
DATAFLOW_IP=$(kubectl get svc unifai-dataflow-server -o jsonpath='{.metadata.name}')

# Create ConfigMap with service details
log_info "Creating ConfigMap 'dataflow-config'..."
kubectl create configmap dataflow-config \
    --from-literal=DATAFLOW_HOST="$DATAFLOW_IP" \
    --from-literal=DATAFLOW_PORT="$DATAFLOW_PORT" \
    --dry-run=client -o yaml | kubectl apply -f -

# Initialize MongoDB collections (example)
log_info "Initializing MongoDB collections..."
kubectl exec -it deployment/unifai-dataflow-server -- \
    python -c "from app import init_db; init_db()"

log_info "✅ Postsync hook completed successfully"
```

### Shared Resources Postsync Hook

**Purpose:** Create `shared-config` ConfigMap with dynamically discovered service endpoints.

**Inline Hook in Helmfile:**

```yaml
releases:
  - name: unifai-shared-config
    needs:
      - unifai-mongodb
      - unifai-qdrant
      - unifai-rabbitmq
    hooks:
      - events: ["postsync"]
        showlogs: true
        command: bash
        args:
          - "-c"
          - |
              wait_for_ext_ip() {
                local svc=$1
                for i in {1..60}; do
                  ip=$(kubectl get svc "$svc" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
                  if [[ -n "$ip" ]]; then
                    echo "$ip"
                    return
                  fi
                  sleep 10
                done
                echo "pending"
              }
              
              MONGODB_ADDR=$(wait_for_ext_ip mongodb)
              QDRANT_ADDR=$(wait_for_ext_ip qdrant)
              RABBITMQ_ADDR=$(wait_for_ext_ip rabbitmq)
              
              kubectl create configmap shared-config \
                --from-literal=MONGO_EXT_ADDR="$MONGODB_ADDR" \
                --from-literal=RABBITMQ_EXT_ADDR="$RABBITMQ_ADDR" \
                --from-literal=QDRANT_EXT_ADDR="$QDRANT_ADDR" \
                --dry-run=client -o yaml | kubectl apply -f -
```

---

## Deployment Workflows

### Workflow 1: Fresh Installation

**Use Case:** Initial deployment or complete environment reset

**Steps:**

```bash
# 1. Set environment variables for secrets
export default_slack_bot_token="xoxb-..."
export default_slack_user_token="xoxp-..."

# 2. Login to OpenShift cluster
oc login https://api.cluster.example.com:6443 --token=<token>
oc project tag-ai--pipeline

# 3. Deploy shared resources first
helmfile -f helmfile1.yaml.gotmpl apply

# Wait for shared resources to be ready
kubectl wait --for=condition=Ready pods -l app=mongodb --timeout=300s
kubectl wait --for=condition=Ready pods -l app=qdrant --timeout=300s
kubectl wait --for=condition=Ready pods -l app=rabbitmq --timeout=300s

# 4. Deploy application components
helmfile -f dataflow.yaml.gotmpl apply
helmfile -f multiagent.yaml.gotmpl apply
helmfile -f sso.yaml.gotmpl apply

# 5. Deploy UI (waits for backend routes)
helmfile -f ui.yaml.gotmpl apply

# 6. Verify deployment
kubectl get pods
kubectl get routes
```

**Expected Time:** ~30-45 minutes

### Workflow 2: Application Upgrade

**Use Case:** Update specific components with new images

**Steps:**

```bash
# 1. Update values file with new image tag
vim values/dataflow-resource-values.yaml
# Change: image.tag: latest → image.tag: 2024.12.01

# 2. Login to cluster
oc login https://api.cluster.example.com:6443 --token=<token>
oc project tag-ai--pipeline

# 3. Apply updated configuration (rolling update)
helmfile -f dataflow.yaml.gotmpl apply

# 4. Monitor rollout
kubectl rollout status deployment/unifai-dataflow-server
kubectl rollout status deployment/unifai-dataflow-celery

# 5. Verify pods are running new version
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}'
```

**Expected Time:** ~5-10 minutes (per component)

### Workflow 3: Component Removal

**Use Case:** Remove specific component

```bash
# Remove single release
helmfile -f dataflow.yaml.gotmpl -l name=unifai-dataflow-celery destroy

# Remove entire helmfile
helmfile -f dataflow.yaml.gotmpl destroy
```

### Workflow 4: Debugging Deployment

**Steps:**

```bash
# 1. Check Helmfile diff
helmfile -f dataflow.yaml.gotmpl diff

# 2. Lint charts
helmfile -f dataflow.yaml.gotmpl lint

# 3. Template charts (dry-run)
helm template ./dataflow/unifai-dataflow-server \
    -f values/dataflow-resource-values.yaml \
    -f values/global-config.yaml

# 4. Check pod logs
kubectl logs -f deployment/unifai-dataflow-server

# 5. Check events
kubectl get events --sort-by='.lastTimestamp'

# 6. Describe problematic resources
kubectl describe pod <pod-name>
```

---

## Best Practices

### 1. **Chart Development**

```yaml
# ✅ Use helpers for common patterns
{{- include "app.labels" . | nindent 4 }}

# ✅ Add checksum annotations for ConfigMap/Secret changes
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}

# ✅ Use named ports
ports:
  - name: http
    containerPort: 8080

# ✅ Define resource limits
resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 1Gi

# ✅ Use readiness/liveness probes
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 10
```

### 2. **Values Organization**

```yaml
# ✅ Group related values
database:
  host: mongodb
  port: 27017
  name: unifai

# ✅ Use meaningful defaults
replicaCount: 1  # Single replica for development

# ✅ Document complex values
# GPU toleration for production workloads
# Required for scheduling on GPU nodes
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
```

### 3. **Deployment Safety**

```bash
# ✅ Always diff before apply
helmfile -f dataflow.yaml.gotmpl diff

# ✅ Use wait for critical resources
helmfile -f helmfile1.yaml.gotmpl --wait apply

# ✅ Verify after deployment
kubectl wait --for=condition=Ready pods --all --timeout=600s
kubectl get pods,svc,routes
```

### 4. **Hook Best Practices**

```bash
# ✅ Make hooks idempotent
kubectl create secret generic my-secret \
    --dry-run=client -o yaml | kubectl apply -f -

# ✅ Add timeout protection
for i in {1..60}; do
    [condition] && break
    sleep 10
done

# ✅ Provide clear logging
log_info "Creating secret..."
log_error "Failed to create secret"
```

### 5. **Resource Management**

```yaml
# ✅ Tag resources with labels
labels:
  app: unifai
  component: dataflow
  version: "{{ .Chart.AppVersion }}"

# ✅ Use PVC for persistent data
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: unifai-data-pvc

# ✅ Set proper storage class
storageClassName: gp2  # AWS EBS
```

---

## Troubleshooting

### Common Issues

#### 1. **Hook Failures**

**Symptom:** Helmfile apply hangs or fails during hook execution

```
Error: hook "presync" failed: exit status 1
```

**Solution:**

```bash
# Check hook script locally
bash -x dataflow-presync.sh

# Verify environment variables
echo $default_slack_bot_token

# Run hook manually in cluster
kubectl run debug --rm -it --image=busybox -- sh
# Then run hook commands manually
```

#### 2. **Image Pull Errors**

**Symptom:** Pods in `ImagePullBackOff` state

```
Failed to pull image "images.paas.redhat.com/unifai/backend:2024.12.01": rpc error: code = Unknown desc = Error reading manifest 2024.12.01 in images.paas.redhat.com/unifai/backend: manifest unknown
```

**Solution:**

```bash
# Verify image exists in registry
podman search images.paas.redhat.com/unifai/backend --list-tags

# Check imagePullSecrets
kubectl get secrets | grep regcred
kubectl create secret docker-registry regcred \
    --docker-server=images.paas.redhat.com \
    --docker-username=<user> \
    --docker-password=<password>

# Update deployment to use secret
imagePullSecrets:
  - name: regcred
```

#### 3. **ConfigMap Not Found**

**Symptom:** Pods fail to start with missing ConfigMap

```
Error: configmap "shared-config" not found
```

**Solution:**

```bash
# Verify ConfigMap exists
kubectl get configmap shared-config

# If missing, check postsync hook logs
helmfile -f helmfile1.yaml.gotmpl apply --debug

# Manually create ConfigMap
kubectl create configmap shared-config \
    --from-literal=MONGODB_IP=mongodb \
    --from-literal=RABBITMQ_IP=rabbitmq
```

#### 4. **Service Not Ready**

**Symptom:** Postsync hook times out waiting for service

```
Timeout waiting for service 'mongodb' port
```

**Solution:**

```bash
# Check service status
kubectl get svc mongodb

# Check pods
kubectl get pods -l app=mongodb

# Check events
kubectl get events --field-selector involvedObject.name=mongodb

# Increase timeout in hook
for i in {1..120}; do  # Increase from 60 to 120
```

#### 5. **Route Not Accessible**

**Symptom:** Cannot access application via OpenShift Route

```
curl: (7) Failed to connect to unifai-ui-... port 443: Connection refused
```

**Solution:**

```bash
# Verify Route exists
kubectl get route unifai-ui

# Check Route status
kubectl describe route unifai-ui

# Verify Service has endpoints
kubectl get endpoints unifai-ui

# Check if pods are ready
kubectl get pods -l app=unifai-ui

# Test internal service
kubectl run -it --rm debug --image=busybox --restart=Never -- \
    wget -O- http://unifai-ui:3000
```

---

## Code Review Checklist

### Helm Charts
- [ ] Chart.yaml has correct version and appVersion
- [ ] values.yaml has sensible defaults
- [ ] All templates use helpers for labels/selectors
- [ ] Resources have limits and requests defined
- [ ] Probes defined (readiness, liveness)
- [ ] NOTES.txt provides useful information
- [ ] Secrets use secure references (not hardcoded)

### Helmfile
- [ ] Dependencies declared with `needs`
- [ ] Values files properly referenced
- [ ] Hooks are idempotent
- [ ] Wait conditions appropriate
- [ ] Environment-specific overrides correct

### Values Files
- [ ] No sensitive data (use secrets)
- [ ] Image tags specified (not implicit 'latest')
- [ ] Resource limits realistic
- [ ] Environment variables documented
- [ ] Route hostnames correct

### Hooks
- [ ] Proper error handling (set -e, set -o pipefail)
- [ ] Timeout protection implemented
- [ ] Idempotent operations (--dry-run | apply)
- [ ] Clear logging with colors
- [ ] Exit codes correct

---

## Glossary

| Term | Definition |
|------|------------|
| **Helm** | Kubernetes package manager |
| **Helmfile** | Declarative specification for deploying Helm charts |
| **Chart** | Helm package containing Kubernetes manifests |
| **Release** | Deployed instance of a Helm chart |
| **Values** | Configuration variables for Helm charts |
| **Hook** | Script executed at specific lifecycle events |
| **Presync** | Hook executed before chart deployment |
| **Postsync** | Hook executed after chart deployment |
| **PVC** | PersistentVolumeClaim (storage request) |
| **Route** | OpenShift resource for external HTTP/HTTPS access |
| **Ingress** | Kubernetes resource for external HTTP/HTTPS access |
| **StatefulSet** | Kubernetes workload for stateful applications |
| **ConfigMap** | Kubernetes resource for configuration data |
| **Secret** | Kubernetes resource for sensitive data |

---

## Contact & Support

For questions about Helm deployments:

1. **Chart issues**: Check values.yaml, verify template syntax
2. **Deployment failures**: Check hooks, ConfigMaps, Secrets
3. **Network issues**: Verify Services, Routes, Ingresses
4. **Resource issues**: Check resource requests/limits, node capacity

**Useful Commands:**
```bash
# Helmfile operations
helmfile -f <file> diff
helmfile -f <file> apply
helmfile -f <file> destroy

# Helm operations
helm list
helm status <release>
helm get values <release>

# Kubernetes operations
kubectl get all
kubectl describe pod <name>
kubectl logs -f <pod>
kubectl exec -it <pod> -- bash
```

---

**Document Version:** 1.0  
**Last Updated:** December 1, 2024  
**Maintainer:** UnifAI DevOps Team

