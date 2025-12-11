# 🚀 UnifAI CI/CD Pipelines

Welcome! This guide explains our two-step Jenkins pipeline process for building and deploying the **UnifAI** application.

> **📖 For detailed architecture, conventions, and troubleshooting, see [ARCHITECTURE.md](./ARCHITECTURE.md)**

---

## 📦 Overview

Our CI/CD process consists of two main pipelines:

1. **Image Builder** – Builds new container images from our code.
2. **Application Deployer** – Deploys those images to our OpenShift clusters using Helm.

**Quick Links:**
- 🏗️ [Image Builder Job](https://jenkins-csb-ant-main.dno.corp.redhat.com/job/UnifAI/job/image-builder/)
- 🚀 [Application Deployer Job](https://jenkins-csb-ant-main.dno.corp.redhat.com/job/UnifAI/job/app-deployer/)
- 📚 [Detailed Architecture Documentation](./ARCHITECTURE.md)

---

## 🏗️ Pipeline 1: Image Builder

This pipeline performs the following tasks:
- Compiles the source code
- Builds container images using **Podman**
- Pushes the images to our internal image registry
- Optionally triggers the deployment pipeline

### ▶️ How to Use

1. Go to the Jenkins job for **Image Builder**:  
   👉 [Jenkins Image Builder Job](https://jenkins-csb-ant-main.dno.corp.redhat.com/job/UnifAI/job/image-builder/)  
2. Click **"Build with Parameters"**.
3. Fill in the parameters as needed (see below).
4. To also deploy the UnifAI after built image, check the `deploy_unifai` box. ( this will trigger the second pipeline.)

### 🔧 Key Parameters

| Parameter             | Description                                                                 | Default Value               |
|-----------------------|-----------------------------------------------------------------------------|------------------------------|
| `BRANCH`              | The Git branch to build the images from.                                    | `main`                      |
| `VERSION`             | A unique tag for the new images. ( use as it is )                                           | Today's date (`yyyy.MM.dd`) |
| `build_...`           | Check the boxes for the components you want to build (e.g., `build_dataflow_backend`). | `false`                     |
| `set_image_canidate`  | If checked, the new image will also be tagged as `latest` in the registry.  | `false`                     |
| `deploy_unifai`       | **Most Important!** Triggers the Application Deployer pipeline after build. | `false`                     |
| `deploy_location`     | Target cluster for deployment.                                          | `STAGING` `PRODUCTION`                  |
| `deploy_type`         | Deployment type: `FRESH_INSTALL`  wipes the environment before deploying or `APPLICATION_UPGRADE` upgrades the modules with the created image.   | `FRESH_INSTALL` `APPLICATION_UPGRADE`         |

---

## 🚀 Pipeline 2: Application Deployer

This pipeline takes the images built by the first pipeline and deploys them to an environment using **Helm**.

> **Note:** You typically won't run this pipeline manually. It's designed to be triggered automatically by the Image Builder pipeline. Manual runs are for special cases like rollbacks or redeploying an existing version.
***if that was the case, please make sure to set the proper Versions (DF_VERSION, MA_VERSION) and avoid VERSION***

### ⚙️ How It Works

1. Checks out the application's Helm charts.
2. Determines the deployment type:
   - `FRESH_INSTALL`: Deletes the existing application from the environment. Deploys shared resources (e.g., databases) first, then application modules.
   - `APPLICATION_UPGRADE`: Performs a rolling update for selected application modules.
3. Updates configuration files (`values.yaml`, `Chart.yaml`) with:
   - Correct image versions
   - Environment settings (e.g., debug mode, resource limits)
4. Executes `helmfile apply` to apply the changes on the OpenShift cluster.

### ▶️ How to Use (Manual Runs Only)

1. Go to the Jenkins job for **Application Deployer**:  
   👉 [Jenkins Application Deployer Job](https://jenkins-csb-ant-main.dno.corp.redhat.com/job/UnifAI/job/app-deployer/)  
2. Click **"Build with Parameters"**.
3. Fill in the relevant parameters described below.

### 🔧 Key Parameters

| Parameter           | Description                                                                  |
|---------------------|------------------------------------------------------------------------------|
| `MODULES_TO_DEPLOY` | Comma-separated list of components to deploy (e.g., `dataflow,multiagent`). |
| `VERSION`           | DONT set this value when Manual Runs.                                     |
| `DF_VERSION`, `MA_VERSION` | (Optional) Use to specify a different version per module.         |
| `deploy_location`   | Target environment (`STAGING` or `PRODUCTION`).                              |
| `deploy_type`       | Deployment strategy: `FRESH_INSTALL` or `APPLICATION_UPGRADE`.               |
| `debug_mode`        | If `true`, pods will run with debug settings enabled.                        |

---

## 📚 Additional Resources

### Documentation
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Comprehensive technical documentation including:
  - Pipeline architecture and flow diagrams
  - Code conventions and best practices
  - Detailed function documentation
  - Troubleshooting guide
  - Environment configuration
  - Groovy coding standards

### Pipeline Files
- `pipeline-build.groovy` - Image builder implementation
- `pipeline-deploy.groovy` - Deployment orchestration
- `deploy-bu.groovy` - Build utility functions

### Related Documentation
- [Helm Deployment Guide](../helm/README.md)
- [Helm Architecture](../helm/ARCHITECTURE.md)

---

## 🔧 Common Workflows

### Workflow 1: Full Build & Deploy to Staging
```
✅ Build all components → Deploy to staging environment
```
1. Go to [Image Builder](https://jenkins-csb-ant-main.dno.corp.redhat.com/job/UnifAI/job/image-builder/)
2. Set parameters:
   - `BRANCH`: `main`
   - `build_sso_image`: ✓
   - `build_gui`: ✓
   - `build_dataflow_backend`: ✓
   - `build_multiagent_backend`: ✓
   - `set_image_candidate`: ✓
   - `deploy_unifai`: ✓
   - `deploy_type`: `APPLICATION_UPGRADE`
   - `deploy_location`: `STAGING`

### Workflow 2: Hotfix Single Component
```
🔥 Build one component → Deploy to production
```
1. Build only the changed component (e.g., `build_gui`: ✓, others: ✗)
2. **Don't trigger automatic deployment** (`deploy_unifai`: ✗)
3. Manually run [Application Deployer](https://jenkins-csb-ant-main.dno.corp.redhat.com/job/UnifAI/job/app-deployer/)
4. Set `MODULES_TO_DEPLOY`: `ui` and appropriate version

### Workflow 3: Fresh Environment Setup
```
🆕 Deploy everything from scratch
```
1. Run deployment pipeline with:
   - `deploy_type`: `FRESH_INSTALL`
   - `deploy_location`: `STAGING` or `PRODUCTION`
2. Wait for shared resources to be ready (~15 min)
3. Application components deploy automatically

---

## ⚠️ Important Notes

### Version Management
- **VERSION** parameter is auto-generated as `YYYY.MM.DD` (e.g., `2024.12.01`)
- Use the same **VERSION** across build and deployment pipelines
- For hotfixes, append suffix: `2024.12.01-hotfix`

### Image Tags
- Setting `set_image_candidate=true` also tags images as `latest`
- Production deployments should use specific version tags
- Development can use `latest` tag

### Deployment Safety
- **FRESH_INSTALL** deletes existing deployment ⚠️
- **APPLICATION_UPGRADE** performs rolling updates (zero downtime)
- Always verify in **STAGING** before deploying to **PRODUCTION**

### Manual Deployment
If you need to manually deploy without building:
1. **Don't set** the `VERSION` parameter in deployment pipeline
2. **Do set** the component-specific versions (`DF_VERSION`, `MA_VERSION`, etc.)
3. Specify `MODULES_TO_DEPLOY` (e.g., `dataflow,ui,sso`)

---

## 🐛 Troubleshooting

### Build Failures
```
Error: podman build failed with exit status 137
```
**Solution:** OOM (Out of Memory) - Contact DevOps to increase build agent resources.

### Deployment Hangs
```
Waiting for pods to be ready...
```
**Solution:** Check OpenShift console, pods may be in `ImagePullBackOff` or `CrashLoopBackOff`.

### Image Not Found
```
Failed to pull image: manifest unknown
```
**Solution:** Verify image was pushed to registry, check `VERSION` parameter matches.

For detailed troubleshooting, see [ARCHITECTURE.md - Troubleshooting](./ARCHITECTURE.md#troubleshooting).

---

Have Fun! 🚀