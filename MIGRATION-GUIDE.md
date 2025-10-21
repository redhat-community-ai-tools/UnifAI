# 🔒 UnifAI Sensitive Data Separation Guide

This guide shows how to move sensitive and site-specific data to a separate private git repository while keeping your current code logic intact.

## 🎯 **What We're Separating**

### **🔐 Sensitive Data:**
- **API Keys**: Slack tokens, authentication secrets
- **Credentials**: RabbitMQ, database passwords
- **URLs**: External endpoints, frontend URLs

### **🏗️ Site-Specific Data:**  
- **Infrastructure**: Namespaces, storage classes, resource limits
- **Environment**: Dev/staging/prod configurations
- **Deployment**: Image tags, git branches

## 📋 **Step-by-Step Migration**

### **Step 1: Create Private Configuration Repository**

```bash
# Create new private repository on GitLab/GitHub  
# Name it: unifai-config-private

# Clone the new repo
git clone https://your-git-provider.com/your-org/unifai-config-private.git
cd unifai-config-private

# Copy the example structure from your main repo
cp -r ../unifai.working/unifai-config-private-example/* .

# Customize configuration for your environment
vi environments/dev/sensitive-values.yaml     # Add your actual secrets
vi environments/dev/site-config.yaml          # Add your site settings

# Commit initial configuration
git add .
git commit -m "Initial private configuration setup"
git push
```

### **Step 2: Update Main Repository**

```bash
cd ../unifai.working

# Backup current configuration
cp helm/values/global-config.yaml helm/values/global-config.yaml.backup
cp DataPipelineHub/backend/config/app_config.py DataPipelineHub/backend/config/app_config.py.backup

# Replace with clean versions (no sensitive data)
cp helm/values/global-config-clean.yaml helm/values/global-config.yaml
cp DataPipelineHub/backend/config/app_config_clean.py DataPipelineHub/backend/config/app_config.py

# Update ArgoCD configuration to use multi-source
vi gitops-updated/unifai-multisource.yaml  # Update private repo URL
```

### **Step 3: Configure ArgoCD Repository Access**

```bash
# Create repository secret for private config repo
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: unifai-config-private-repo
  namespace: tag-ai--runtime-int
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: https://your-git-provider.com/your-org/unifai-config-private.git
  username: oauth2
  password: YOUR_PRIVATE_REPO_TOKEN
EOF
```

### **Step 4: Deploy Multi-Source Application**

```bash
# Apply the new multi-source configuration
kubectl apply -f gitops-updated/unifai-multisource.yaml

# Monitor deployment
kubectl get application unifai-platform -n tag-ai--runtime-int -w
```

## 🔧 **How Multi-Source Works**

### **Value File Precedence** (later files override earlier ones):
1. `sensitive-values.yaml` (from private repo) - secrets, credentials
2. `site-config.yaml` (from private repo) - infrastructure, resources  
3. `*-extract-clean.yaml` (from main repo) - templates, defaults

### **Environment Variable Injection**:
The updated application config reads from environment variables:
```python
# Before (hardcoded)
slack_token: str = "xoxb-hardcoded-token-here"

# After (from environment)  
slack_token: str = Field(default="", validation_alias="SLACK_BOT_TOKEN")
```

### **ArgoCD Multi-Source Structure**:
```yaml
sources:
  # Source 1: Private config repo
  - repoURL: https://gitlab.com/org/unifai-config-private.git
    path: environments/dev
    
  # Source 2: Main code repo  
  - repoURL: https://gitlab.com/org/unifai.git
    path: helm/shared-resources/mongodb
    helm:
      valueFiles:
        - $values/sensitive-values.yaml    # From private repo
        - $values/site-config.yaml         # From private repo
        - ../../values/mongodb-clean.yaml  # From main repo
```

## ✅ **Verification Steps**

### **Check Repository Access**:
```bash
kubectl get secrets -l argocd.argoproj.io/secret-type=repository -n tag-ai--runtime-int
```

### **Verify Application Status**:
```bash
kubectl describe application unifai-platform -n tag-ai--runtime-int
```

### **Check Environment Variables**:  
```bash
kubectl exec deployment/unifai-platform-dataflow -- env | grep -E "(SLACK|KEYCLOAK|FRONTEND)"
```

### **Validate Service Discovery**:
```bash
kubectl get configmap shared-config -o yaml
```

## 🔐 **Security Benefits**

✅ **Separation of Concerns**: Code and secrets in different repos  
✅ **Environment Isolation**: Dev secrets separate from prod  
✅ **Access Control**: Limit who can see sensitive configuration  
✅ **Audit Trail**: Track sensitive configuration changes  
✅ **Compliance**: Meet security requirements for secret management  

## ⚠️ **Important Notes**

1. **Keep private repo secure** - restrict access carefully
2. **Test in dev first** - validate configuration before prod  
3. **Backup configuration** - don't lose sensitive data
4. **Document secrets** - track where credentials come from
5. **Rotate regularly** - change passwords periodically

## 🔄 **Future Workflows**

### **Code Changes** (developers):
```bash
# Normal development workflow in main repo
cd unifai.working  
git checkout -b feature/new-service
# Make code changes
git push origin feature/new-service
```

### **Configuration Changes** (ops team):
```bash
# Configuration changes in private repo  
cd unifai-config-private
git checkout -b config/update-prod-resources
vi environments/prod/site-config.yaml
git push origin config/update-prod-resources
```

### **Secret Updates**:
```bash
# Update secrets in private repo
vi environments/staging/sensitive-values.yaml
git commit -m "Rotate RabbitMQ credentials for staging"
git push
# ArgoCD automatically syncs and updates secrets
```

This approach keeps your **current code logic intact** while providing **enterprise-grade security** for sensitive configuration data! 🚀
