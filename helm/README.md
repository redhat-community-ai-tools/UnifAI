# UnifAI Helm Deployment Guide

This guide provides instructions for deploying UnifAI components to Kubernetes/OpenShift clusters using Helm and Helmfile.

> **📖 For detailed architecture, chart conventions, and troubleshooting, see [ARCHITECTURE.md](./ARCHITECTURE.md)**

---

## 📦 Overview

UnifAI uses **Helmfile** to orchestrate the deployment of multiple Helm charts across different components:

- **Shared Resources**: MongoDB, RabbitMQ, Qdrant, SSO (infrastructure layer)
- **Dataflow Module**: Data Pipeline Hub backend and Celery workers
- **Multi-Agent Module**: Multi-Agent System backend
- **UI Module**: React frontend with Nginx
- **Optional Services**: Docling, vLLM serving engines

---

## 🛠️ Prerequisites

### Required Tools

```bash
# Helm 3.x
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version

# Helmfile
curl -Lo helmfile https://github.com/helmfile/helmfile/releases/latest/download/helmfile_linux_amd64
chmod +x helmfile
sudo mv helmfile /usr/local/bin/
helmfile version

# kubectl or oc (OpenShift CLI)
# For OpenShift:
curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/oc/latest/linux/oc.tar.gz
tar -xzf oc.tar.gz
sudo mv oc /usr/local/bin/
oc version
```

### Cluster Access

```bash
# Login to OpenShift cluster
oc login https://api.cluster.example.com:6443 --token=<your-token>

# Or use kubeconfig
export KUBECONFIG=/path/to/kubeconfig

# Verify access
oc whoami
oc project
```

### Required Permissions

You need the following permissions in the target namespace:
- Create/update/delete Deployments, StatefulSets, Services
- Create/update/delete ConfigMaps, Secrets
- Create/update/delete PersistentVolumeClaims
- Create/update/delete Routes (OpenShift) or Ingresses (Kubernetes)

---

## 🚀 Quick Start

### Fresh Installation (Complete Deployment)

```bash
# 1. Clone the repository
git clone https://github.com/redhat-community-ai-tools/UnifAI.git
cd UnifAI/helm

# 2. Set required environment variables for secrets
export default_slack_bot_token="xoxb-your-slack-bot-token"
export default_slack_user_token="xoxp-your-slack-user-token"

# 3. Login to cluster and select namespace
oc login https://api.cluster.example.com:6443 --token=<token>
oc project tag-ai--pipeline

# 4. Deploy shared resources (MongoDB, RabbitMQ, Qdrant)
helmfile -f helmfile1.yaml.gotmpl apply

# Wait for shared resources to be ready (~10-15 minutes)
kubectl wait --for=condition=Ready pods -l app=mongodb --timeout=600s
kubectl wait --for=condition=Ready pods -l app=qdrant --timeout=300s
kubectl wait --for=condition=Ready pods -l app=rabbitmq --timeout=300s

# 5. Deploy application components
helmfile -f dataflow.yaml.gotmpl apply      # Dataflow module
helmfile -f multiagent.yaml.gotmpl apply    # Multi-Agent module
helmfile -f sso.yaml.gotmpl apply           # SSO module
helmfile -f ui.yaml.gotmpl apply            # UI frontend

# 6. Verify deployment
kubectl get pods
kubectl get routes
```

**Expected Deployment Time:** ~30-45 minutes for full stack

---

## 📋 Deployment Scenarios

### Scenario 1: Update Single Component

Update only the Dataflow backend with a new image version:

```bash
# 1. Edit values file
vim values/dataflow-resource-values.yaml

# Update image tag:
unifai_dataflow_server:
  image:
    tag: 2024.12.01  # Change from 'latest' to specific version

# 2. Apply changes (rolling update)
helmfile -f dataflow.yaml.gotmpl apply

# 3. Monitor rollout
kubectl rollout status deployment/unifai-dataflow-server

# 4. Verify new version
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}' | grep backend
```

**Expected Time:** ~5 minutes

### Scenario 2: Scale Components

Increase the number of Celery workers:

```bash
# 1. Edit values file
vim values/dataflow-resource-values.yaml

# Update replica count:
unifai_dataflow_celery:
  replicaCount: 5  # Increase from 3 to 5

# 2. Apply changes
helmfile -f dataflow.yaml.gotmpl apply

# 3. Verify scaling
kubectl get pods -l app=unifai-dataflow-celery
```

### Scenario 3: Update Environment Variables

Change configuration without redeploying:

```bash
# 1. Update ConfigMap
kubectl edit configmap shared-config

# 2. Restart pods to pick up new config
kubectl rollout restart deployment/unifai-dataflow-server
kubectl rollout restart deployment/unifai-multiagent-be
```

### Scenario 4: Deploy to Different Environment

Deploy to production with production-specific values:

```bash
# 1. Create production values file
cp values/dataflow-resource-values.yaml values/dataflow-production-values.yaml

# 2. Edit production values
vim values/dataflow-production-values.yaml
# Update:
# - Resource limits (increase for production)
# - Replica counts (increase for HA)
# - Routes/hostnames (production domains)

# 3. Update global config
vim values/global-config.yaml
# Update:
env:
  FRONTEND_URL: "https://unifai.prod.example.com"
  SSO_BACKEND_HOST: "https://sso.prod.example.com"

# 4. Login to production cluster
oc login https://api.prod-cluster.example.com:6443 --token=<prod-token>
oc project unifai-production

# 5. Deploy with production values
helmfile -f helmfile1.yaml.gotmpl -e production apply
helmfile -f dataflow.yaml.gotmpl -e production apply
# ... repeat for other components
```

---

## 🗂️ Repository Structure

```
helm/
├── shared-resources/       # Infrastructure charts (MongoDB, RabbitMQ, etc.)
├── dataflow/              # Dataflow module charts
├── multiagent/            # Multi-Agent module charts
├── ui/                    # UI frontend chart
├── values/                # Configuration value files
├── helmfile1.yaml.gotmpl  # Shared resources deployment
├── dataflow.yaml.gotmpl   # Dataflow deployment
├── multiagent.yaml.gotmpl # Multi-Agent deployment
├── ui.yaml.gotmpl         # UI deployment
└── *.sh                   # Lifecycle hooks (presync/postsync)
```

For detailed structure and chart conventions, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## ⚙️ Configuration

### Values Files

Configuration is managed through values files in the `values/` directory:

| File | Purpose |
|------|---------|
| `global-config.yaml` | Global environment variables (URLs, service endpoints) |
| `shared-resource-values.yaml` | MongoDB, RabbitMQ, Qdrant configuration |
| `dataflow-resource-values.yaml` | Dataflow backend and Celery configuration |
| `multiagent-resource-values.yaml` | Multi-Agent backend configuration |
| `ui-values.yaml` | UI frontend configuration |
| `sso-values.yaml` | SSO service configuration |

### Key Configuration Options

**Image Configuration:**
```yaml
image:
  repository: images.paas.redhat.com/unifai/backend
  tag: latest  # or specific version like "2024.12.01"
  pullPolicy: Always
```

**Resource Limits:**
```yaml
resources:
  limits:
    cpu: 2000m
    memory: 4Gi
  requests:
    cpu: 1000m
    memory: 2Gi
```

**Replica Count:**
```yaml
replicaCount: 3  # Number of pod replicas
```

**Auto-scaling:**
```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
```

**External Access (OpenShift Routes):**
```yaml
route:
  enabled: true
  host: unifai-ui-namespace.apps.cluster.example.com
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
```

---

## 🔐 Secrets Management

### Slack Integration Secrets

Required for Dataflow module Slack integration:

```bash
# Set environment variables before deployment
export default_slack_bot_token="xoxb-your-bot-token"
export default_slack_user_token="xoxp-your-user-token"

# These are used by dataflow-presync.sh hook to create Secret
helmfile -f dataflow.yaml.gotmpl apply
```

### Manual Secret Creation

If presync hooks don't run, create secrets manually:

```bash
# Dataflow secrets
kubectl create secret generic unifai-dataflow-secrets \
    --from-literal=slack_bot_token="xoxb-..." \
    --from-literal=slack_user_token="xoxp-..."

# Image pull secrets (if using private registry)
kubectl create secret docker-registry regcred \
    --docker-server=images.paas.redhat.com \
    --docker-username=<username> \
    --docker-password=<password> \
    --docker-email=<email>
```

---

## 🧪 Verification & Testing

### Check Deployment Status

```bash
# List all pods
kubectl get pods

# Check pod status (should all be Running)
kubectl get pods --field-selector=status.phase!=Running

# Check services
kubectl get svc

# Check routes (OpenShift)
kubectl get routes

# Check persistent volumes
kubectl get pvc
```

### Verify Application Health

```bash
# Check backend health endpoint
curl https://unifai-dataflow-server-<namespace>.apps.cluster.example.com/api/health

# Check UI accessibility
curl -I https://unifai-ui-<namespace>.apps.cluster.example.com

# Check MongoDB connection
kubectl exec -it statefulset/mongodb -- mongo --eval "db.adminCommand('ping')"

# Check RabbitMQ
kubectl exec -it statefulset/rabbitmq -- rabbitmqctl status

# Check Qdrant
curl http://qdrant:6333/collections
```

### View Logs

```bash
# Dataflow server logs
kubectl logs -f deployment/unifai-dataflow-server

# Celery worker logs
kubectl logs -f deployment/unifai-dataflow-celery

# Multi-Agent logs
kubectl logs -f deployment/unifai-multiagent-be

# UI logs
kubectl logs -f deployment/unifai-ui

# Tail logs from all pods with label
kubectl logs -f -l app=unifai-dataflow-server
```

---

## 🔄 Update Workflows

### Rolling Update

Update image version with zero downtime:

```bash
# 1. Update values file with new image tag
vim values/dataflow-resource-values.yaml

# 2. Preview changes
helmfile -f dataflow.yaml.gotmpl diff

# 3. Apply update (rolling update happens automatically)
helmfile -f dataflow.yaml.gotmpl apply

# 4. Watch rollout
kubectl rollout status deployment/unifai-dataflow-server
```

### Rollback Deployment

Rollback to previous version:

```bash
# Check rollout history
kubectl rollout history deployment/unifai-dataflow-server

# Rollback to previous revision
kubectl rollout undo deployment/unifai-dataflow-server

# Rollback to specific revision
kubectl rollout undo deployment/unifai-dataflow-server --to-revision=3
```

### Force Update

Force recreation of pods (useful for config changes):

```bash
# Restart deployment
kubectl rollout restart deployment/unifai-dataflow-server

# Or delete pods (they'll be recreated automatically)
kubectl delete pods -l app=unifai-dataflow-server
```

---

## 🧹 Cleanup & Removal

### Remove Specific Component

```bash
# Remove single release
helmfile -f dataflow.yaml.gotmpl -l name=unifai-dataflow-server destroy

# Remove entire module
helmfile -f dataflow.yaml.gotmpl destroy
```

### Remove All Components

```bash
# Remove in reverse order (UI → Apps → Shared Resources)
helmfile -f ui.yaml.gotmpl destroy
helmfile -f sso.yaml.gotmpl destroy
helmfile -f multiagent.yaml.gotmpl destroy
helmfile -f dataflow.yaml.gotmpl destroy
helmfile -f helmfile1.yaml.gotmpl destroy

# Manually delete PVCs (Helmfile doesn't delete PVCs by default)
kubectl delete pvc --all

# Manually delete secrets
kubectl delete secret unifai-dataflow-secrets
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Pods Stuck in Pending

**Symptoms:**
```bash
kubectl get pods
# NAME                          READY   STATUS    RESTARTS   AGE
# unifai-dataflow-server-xxx    0/1     Pending   0          5m
```

**Possible Causes:**
- Insufficient cluster resources
- PVC not bound
- Node selector/affinity not matching

**Solutions:**
```bash
# Check why pod is pending
kubectl describe pod unifai-dataflow-server-xxx

# Check node resources
kubectl top nodes

# Check PVC status
kubectl get pvc

# Check events
kubectl get events --sort-by='.lastTimestamp' | grep -i error
```

#### 2. ImagePullBackOff

**Symptoms:**
```bash
kubectl get pods
# NAME                          READY   STATUS             RESTARTS   AGE
# unifai-ui-xxx                 0/1     ImagePullBackOff   0          2m
```

**Solutions:**
```bash
# Check image exists
podman search images.paas.redhat.com/unifai/ui --list-tags

# Verify imagePullSecret
kubectl get secret regcred
kubectl describe secret regcred

# Test image pull manually
podman pull images.paas.redhat.com/unifai/ui:latest

# Update deployment with correct image tag
kubectl set image deployment/unifai-ui ui=images.paas.redhat.com/unifai/ui:2024.12.01
```

#### 3. CrashLoopBackOff

**Symptoms:**
```bash
kubectl get pods
# NAME                          READY   STATUS             RESTARTS   AGE
# unifai-dataflow-server-xxx    0/1     CrashLoopBackOff   5          10m
```

**Solutions:**
```bash
# Check logs for errors
kubectl logs unifai-dataflow-server-xxx

# Check previous container logs (if restarted)
kubectl logs unifai-dataflow-server-xxx --previous

# Describe pod for events
kubectl describe pod unifai-dataflow-server-xxx

# Common issues:
# - Missing environment variables
# - Database connection failures
# - Missing ConfigMaps/Secrets
```

#### 4. ConfigMap Not Found

**Symptoms:**
```
Error: configmap "shared-config" not found
```

**Solutions:**
```bash
# Check if ConfigMap exists
kubectl get configmap shared-config

# If missing, it should be created by postsync hook
# Re-run helmfile with shared resources
helmfile -f helmfile1.yaml.gotmpl apply

# Or manually create
kubectl create configmap shared-config \
    --from-literal=MONGODB_IP=mongodb \
    --from-literal=RABBITMQ_IP=rabbitmq \
    --from-literal=QDRANT_IP=qdrant
```

#### 5. Route Not Accessible

**Symptoms:**
```bash
curl https://unifai-ui-namespace.apps.cluster.example.com
# curl: (7) Failed to connect to unifai-ui... port 443: Connection refused
```

**Solutions:**
```bash
# Verify Route exists
kubectl get route unifai-ui

# Check Route details
kubectl describe route unifai-ui

# Verify Service has endpoints
kubectl get endpoints unifai-ui

# Test internal service connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- \
    wget -O- http://unifai-ui:3000

# Check if pods are running
kubectl get pods -l app=unifai-ui
```

For detailed troubleshooting, see [ARCHITECTURE.md - Troubleshooting](./ARCHITECTURE.md#troubleshooting).

---

## 📚 Additional Resources

### Documentation
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Comprehensive technical documentation
  - Deployment architecture and layering
  - Chart structure and conventions
  - Values management patterns
  - Lifecycle hooks system
  - Best practices and code review checklist

### Helm & Helmfile Resources
- [Helm Documentation](https://helm.sh/docs/)
- [Helmfile Documentation](https://helmfile.readthedocs.io/)
- [OpenShift Documentation](https://docs.openshift.com/)

### Related Documentation
- [CI/CD Pipeline Guide](../ci/README.md)
- [CI/CD Architecture](../ci/ARCHITECTURE.md)

---

## 🤝 Contributing

### Making Chart Changes

1. **Update chart locally:**
   ```bash
   cd dataflow/unifai-dataflow-server
   # Edit templates or values.yaml
   ```

2. **Lint chart:**
   ```bash
   helm lint .
   ```

3. **Test locally:**
   ```bash
   helm template . -f values.yaml
   ```

4. **Update Chart.yaml version:**
   ```yaml
   version: 0.10.0  # Increment version
   ```

5. **Test deployment:**
   ```bash
   helmfile -f dataflow.yaml.gotmpl diff
   helmfile -f dataflow.yaml.gotmpl apply
   ```

6. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: update dataflow chart with new feature"
   git push origin feature/chart-update
   ```

### Adding New Component

1. Create new chart directory
2. Define Chart.yaml and values.yaml
3. Create templates (deployment, service, route, etc.)
4. Add to appropriate helmfile (e.g., `dataflow.yaml.gotmpl`)
5. Add values to corresponding values file
6. Test deployment
7. Update documentation

---

## 📞 Support

For deployment issues or questions:

1. **Check pod logs:** `kubectl logs -f <pod-name>`
2. **Check events:** `kubectl get events --sort-by='.lastTimestamp'`
3. **Review this documentation:** [README.md](./README.md) and [ARCHITECTURE.md](./ARCHITECTURE.md)
4. **Review CI/CD logs:** Check Jenkins pipeline output
5. **Contact DevOps team:** For cluster access or resource issues

---

**Last Updated:** December 1, 2024  
**Maintainer:** UnifAI DevOps Team

