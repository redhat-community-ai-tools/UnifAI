# UnifAI CI/CD Architecture & Convention Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Pipeline Structure](#pipeline-structure)
4. [Build Pipeline](#build-pipeline)
5. [Deployment Pipeline](#deployment-pipeline)
6. [Code Conventions](#code-conventions)
7. [Environment Configuration](#environment-configuration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The UnifAI CI/CD system is a Jenkins-based pipeline infrastructure for **building container images** and **deploying to OpenShift clusters**. The system supports multiple environments (Staging, Production) and provides flexible deployment strategies.
In addition there are some areas where the team is using GitHub actions, with the intention to move as much of the flow into GitHub actions.

**Core Features:**
- Automated container image building using Podman
- Multi-component parallel builds
- Image registry management (versioning + latest tags)
- Automated deployment to OpenShift via Helm/Helmfile
- Support for fresh installations and rolling upgrades
- Debug mode for development troubleshooting

**Deployment Targets:**
- **STAGING**: `apps.stc-ai-e1-pp.imap.p1.openshiftapps.com`
- **PRODUCTION**: `apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com`

---

## Technology Stack

### Core Technologies
- **Jenkins** - CI/CD orchestration platform
- **Groovy 2.x** - Pipeline scripting language (DSL)
- **Podman** - Container image building (rootless alternative to Docker)
- **Helmfile** - Declarative Helm chart deployment
- **OpenShift 4.x** - Kubernetes-based container platform
- **Git/GitHub** - Version control and source repository

### Container Registry
- **Registry**: `images.paas.redhat.com`
- **Path**: `unifai/`
- **Components**: `backend`, `multiagentbackend`, `ui`, `ssobackend`

### Jenkins Infrastructure
- **Jenkins Master**: `jenkins-csb-ant-main.dno.corp.redhat.com`
- **Build Agent**: `tag-slave` (dedicated node with Podman)
- **Credentials**: GitHub token, GitLab token, Image registry credentials

---

## Pipeline Structure

```
ci/
├── pipeline-build.groovy       # 🏗️  Build Pipeline (Image Builder)
├── pipeline-deploy.groovy      # 🚀 Deployment Pipeline (Application Deployer)
├── deploy-bu.groovy            # 🔧 Build utilities (backup/restore functions)
└── README.md                   # 📖 User-facing documentation
```

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED CI/CD PIPELINE                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────┐
        │   🏗️  PIPELINE 1: Image Builder     │
        └─────────────────────────────────────┘
                              │
        ┌─────────────────────┴───────────────────┐
        │                                         │
        ▼                                         ▼
┌───────────────┐                       ┌──────────────────┐
│ Checkout Code │                       │ Parallel Builds  │
│   from Git    │                       │  (4 components)  │
└───────┬───────┘                       └────────┬─────────┘
        │                                        │
        │  ┌─────────────────────────────────────┤
        │  │                                     │
        ▼  ▼                                     ▼
    ┌─────────┐  ┌──────────────┐  ┌───────────────────┐
    │ Backend │  │ Multi-Agent  │  │ UI + SSO Backend  │
    └────┬────┘  └──────┬───────┘  └─────────┬─────────┘
         │              │                    │
         └──────────────┴────────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ Push to Registry │
              │  (with version)  │
              └─────────┬────────┘
                        │
        ┌───────────────┴───────────────────┐
        │                                   │
        ▼                                   ▼
   [Tag: 2024.12.01]               [Tag: latest] (optional)
                                            │
                                            │
                    ┌───────────────────────┘
                    │ (if deploy_unifai=true)
                    ▼
        ┌─────────────────────────────────────┐
        │ 🚀 PIPELINE 2: Application Deployer │
        └─────────────────────────────────────┘
                    │
        ┌───────────┴────────────┐
        │                        │
        ▼                        ▼
┌──────────────────┐    ┌─────────────────────┐
│ FRESH_INSTALL    │    │ APPLICATION_UPGRADE │
└──────┬───────────┘    └─────────┬───────────┘
       │                          │
       ▼                          ▼
┌──────────────┐          ┌───────────────┐
│ 1. Delete    │          │ 1. Update     │
│    existing  │          │    Chart.yaml │
│ 2. Deploy    │          │ 2. Update     │
│    shared    │          │    values.yaml│
│    resources │          │ 3. Helmfile   │
│ 3. Deploy    │          │    apply      │
│    apps      │          │               │
└──────────────┘          └───────────────┘
```

---

## Build Pipeline

### File: `pipeline-build.groovy`

#### Purpose
Builds container images for UnifAI components and optionally triggers deployment.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `PIPELINE_BRANCH` | String | `main` | Git branch for pipeline scripts (testing purposes) |
| `BRANCH` | String | `main` | Git branch to build images from |
| `VERSION` | String | `yyyy.MM.dd` | Image version tag (auto-generated daily) |
| `build_sso_image` | Boolean | `false` | Build SSO backend image |
| `build_gui` | Boolean | `false` | Build UI (frontend) image |
| `build_dataflow_backend` | Boolean | `false` | Build Data Pipeline Hub backend |
| `build_multiagent_backend` | Boolean | `false` | Build Multi-Agent System backend |
| `set_image_candidate` | Boolean | `false` | Also tag images as `latest` |
| `deploy_unifai` | Boolean | `false` | ⚠️ **CRITICAL**: Trigger deployment after build |
| `deploy_type` | Choice | `FRESH_INSTALL` | Deployment strategy |
| `deploy_location` | Choice | `STAGING` | Target environment |
| `debug_mode` | Boolean | `false` | Enable debug mode in pods |

#### Pipeline Stages

##### 1. Initialization
```groovy
stage("Cleanup & Prepare") {
    // Remove old containers/images
    cleanupContainers()
    cleanupImages()
}
```

##### 2. Code Checkout
```groovy
stage("Checkout Main Repo") {
    checkout([
        $class: 'GitSCM',
        branches: [[name: "*/${params.BRANCH}"]],
        userRemoteConfigs: [[
            url: "https://${buildParams.MainRepoURL}/${buildParams.MainRepoProject}",
            credentialsId: buildParams.CredentialsId
        ]]
    ])
}
```

##### 3. Parallel Image Builds
```groovy
stage("Build Images") {
    parallel(
        "SSO": { if (params.build_sso_image) buildDockerImage("shared-resources/sso-backend") },
        "UI": { if (params.build_gui) buildDockerImage("ui") },
        "Dataflow": { if (params.build_dataflow_backend) buildDockerImage("backend") },
        "MultiAgent": { if (params.build_multiagent_backend) buildDockerImage("multi-agent") }
    )
}
```

##### 4. Registry Push
```groovy
stage("Push to Registry") {
    withCredentials([usernamePassword(
        credentialsId: buildParams.ImageRegistryCreds,
        usernameVariable: 'REGISTRY_USER',
        passwordVariable: 'REGISTRY_PASS'
    )]) {
        sh """
            podman login -u ${REGISTRY_USER} -p ${REGISTRY_PASS} ${buildParams.ImageRegistry}
            podman push ${component}:${VERSION} ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${component}:${VERSION}
        """
        if (params.set_image_candidate) {
            sh "podman push ${component}:${VERSION} ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${component}:latest"
        }
    }
}
```

##### 5. Trigger Deployment (Optional)
```groovy
stage("Trigger Deployment") {
    if (params.deploy_unifai) {
        build job: 'app-deployer',
            parameters: [
                string(name: 'VERSION', value: params.VERSION),
                string(name: 'deploy_location', value: params.deploy_location),
                string(name: 'deploy_type', value: params.deploy_type),
                booleanParam(name: 'debug_mode', value: params.debug_mode)
            ]
    }
}
```

#### Key Functions

**`buildDockerImage(String component)`**
```groovy
// Builds container image with Podman
// Special handling for UI (Dockerfile in deployment/ folder)
def buildDockerImage(String component) {
    String dockerfile = (component == "ui") ? "deployment/Dockerfile" : "Dockerfile"
    String context = (component == "ui") ? component : "."
    
    sh """
        podman build \
            -t ${component}:${VERSION} \
            -t ${component}:latest \
            -f ${component}/${dockerfile} \
            ${context}
    """
}
```

**`tagAndPushImageToRegistry(buildParams, component)`**
```groovy
// Pushes image to registry with version tag
// Optionally tags as 'latest'
def tagAndPushImageToRegistry(buildParams, component) {
    withCredentials([...]) {
        sh """
            podman login -u ${REGISTRY_USER} -p ${REGISTRY_PASS} ${buildParams.ImageRegistry}
            podman push ${component}:${VERSION} ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${component}:${VERSION}
        """
        if (params.set_image_candidate) {
            sh "podman push ${component}:latest ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${component}:latest"
        }
    }
}
```

**`cleanWorkspace(component)`**
```groovy
// Cleanup containers and images after build
def cleanWorkspace(component) {
    sh """
        podman rm -f ${component} || true
        podman rmi -f ${component}:${VERSION} || true
        podman rmi -f ${component}:latest || true
    """
}
```

#### Build Conventions

**Component Name Mapping:**

| Repository Folder | Image Name | Registry Path |
|------------------|------------|---------------|
| `backend/` | `backend` | `images.paas.redhat.com/unifai/backend` |
| `multi-agent/` | `multiagentbackend` | `images.paas.redhat.com/unifai/multiagentbackend` |
| `ui/` | `ui` | `images.paas.redhat.com/unifai/ui` |
| `shared-resources/sso-backend/` | `ssobackend` | `images.paas.redhat.com/unifai/ssobackend` |

**Image Tag Strategy:**
- **Version Tag**: `YYYY.MM.DD` (e.g., `2024.12.01`)
- **Latest Tag**: `latest` (only if `set_image_candidate=true`)
- **Custom Tags**: Can override `VERSION` parameter

---

## Deployment Pipeline

### File: `pipeline-deploy.groovy`

#### Purpose
Deploys UnifAI application to OpenShift clusters using Helmfile.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `PIPELINE_BRANCH` | String | `main` | Git branch for pipeline scripts |
| `BRANCH` | String | `main` | Branch to deploy from |
| `deploy_location` | Choice | `STAGING` | Target environment |
| `deploy_type` | Choice | `FRESH_INSTALL` | Deployment strategy |
| `VERSION` | String | _(empty)_ | ⚠️ **Auto-set by build pipeline** |
| `DF_VERSION` | String | _(empty)_ | Override: Dataflow image tag |
| `MA_VERSION` | String | _(empty)_ | Override: Multi-Agent image tag |
| `GUI_VERSION` | String | _(empty)_ | Override: UI image tag |
| `SSO_VERSION` | String | _(empty)_ | Override: SSO image tag |
| `MODULES_TO_DEPLOY` | String | _(empty)_ | Comma-separated list (e.g., `dataflow,multiagent`) |
| `debug_mode` | Boolean | `false` | Enable debug settings in pods |

#### Deployment Strategies

##### 1. FRESH_INSTALL
**Use Case:** Initial deployment or complete environment reset

**Workflow:**
```groovy
stage("Fresh Install") {
    // 1. Delete existing application
    sh "helmfile destroy"
    
    // 2. Deploy shared resources (MongoDB, RabbitMQ, Qdrant)
    sh "helmfile -f helmfile1.yaml.gotmpl apply"
    
    // 3. Deploy application components
    sh "helmfile -f dataflow.yaml.gotmpl apply"
    sh "helmfile -f multiagent.yaml.gotmpl apply"
    sh "helmfile -f ui.yaml.gotmpl apply"
    sh "helmfile -f sso.yaml.gotmpl apply"
}
```

**Deployment Order:**
1. **Shared Resources** (helmfile1): MongoDB, Qdrant, RabbitMQ, Shared Config
2. **Dataflow Module**: Backend server, Celery workers, Config
3. **Multi-Agent Module**: Backend server
4. **UI Module**: Frontend application
5. **SSO Module**: Authentication service

##### 2. APPLICATION_UPGRADE
**Use Case:** Rolling update of specific components

**Workflow:**
```groovy
stage("Application Upgrade") {
    // Update only specified modules
    if (modulesToDeploy.contains("dataflow")) {
        sh "helmfile -f dataflow.yaml.gotmpl apply"
    }
    if (modulesToDeploy.contains("multiagent")) {
        sh "helmfile -f multiagent.yaml.gotmpl apply"
    }
    if (modulesToDeploy.contains("ui")) {
        sh "helmfile -f ui.yaml.gotmpl apply"
    }
    if (modulesToDeploy.contains("sso")) {
        sh "helmfile -f sso.yaml.gotmpl apply"
    }
}
```

#### Pipeline Stages

##### 1. Environment Setup
```groovy
stage("Setup Environment") {
    // Set OpenShift cluster context
    def clusterConfig = getClusterConfig(params.deploy_location)
    
    sh """
        oc login ${clusterConfig.apiUrl} \
            --token=${clusterConfig.token} \
            --insecure-skip-tls-verify
        oc project ${clusterConfig.namespace}
    """
}
```

##### 2. Checkout Helm Charts
```groovy
stage("Checkout Helm Charts") {
    checkout([
        $class: 'GitSCM',
        branches: [[name: "*/${params.BRANCH}"]],
        userRemoteConfigs: [[
            url: "https://${buildParams.MainRepoURL}/${buildParams.MainRepoProject}",
            credentialsId: buildParams.CredentialsId
        ]]
    ])
}
```

##### 3. Update Chart Versions
```groovy
stage("Update Chart Versions") {
    // Update all Chart.yaml files with appVersion
    updateChartVersions("${WORKSPACE}/helm", params.VERSION)
    
    // Update values.yaml with image tags
    updateValuesYaml("${WORKSPACE}/helm/values/dataflow-resource-values.yaml", params.DF_VERSION)
    updateValuesYaml("${WORKSPACE}/helm/values/multiagent-resource-values.yaml", params.MA_VERSION)
    updateValuesYaml("${WORKSPACE}/helm/values/ui-values.yaml", params.GUI_VERSION)
    updateValuesYaml("${WORKSPACE}/helm/values/sso-values.yaml", params.SSO_VERSION)
    
    // Update global config with environment-specific values
    updateGlobalConfigYaml("${WORKSPACE}/helm/values/global-config.yaml")
}
```

##### 4. Deploy/Upgrade
```groovy
stage("Deploy Application") {
    dir("${WORKSPACE}/helm") {
        if (params.deploy_type == "FRESH_INSTALL") {
            // Fresh installation
            sh "helmfile -f helmfile1.yaml.gotmpl apply"  // Shared resources
            sh "helmfile -f dataflow.yaml.gotmpl apply"   // Dataflow
            sh "helmfile -f multiagent.yaml.gotmpl apply" // Multi-Agent
            sh "helmfile -f ui.yaml.gotmpl apply"         // UI
            sh "helmfile -f sso.yaml.gotmpl apply"        // SSO
        } else {
            // Rolling upgrade
            deployModules(params.MODULES_TO_DEPLOY)
        }
    }
}
```

##### 5. Verification
```groovy
stage("Verify Deployment") {
    // Wait for pods to be ready
    sh "kubectl wait --for=condition=Ready pods --all --timeout=600s"
    
    // Verify services are accessible
    verifyServices()
}
```

#### Key Functions

**`updateChartVersions(rootPath, version)`**
```groovy
// Updates appVersion in all Chart.yaml files
def updateChartVersions(rootPath, version) {
    def chartFiles = sh(
        script: "find ${rootPath} -name 'Chart.yaml'",
        returnStdout: true
    ).trim().split('\n')
    
    chartFiles.each { file ->
        def chart = readYaml file: file
        chart.appVersion = version
        writeYaml file: file, data: chart, overwrite: true
    }
}
```

**`updateValuesYaml(filePath, version)`**
```groovy
// Updates image tags and environment variables
def updateValuesYaml(String filePath, String version) {
    def values = readYaml file: filePath
    
    values.each { sectionName, sectionData ->
        if (sectionData instanceof Map) {
            // Update debug mode
            if (params.debug_mode) {
                sectionData.debug = true
                sectionData.env = sectionData.env ?: [:]
                sectionData.env.ROLE = "debug"
            }
            
            // Update image tag
            if (sectionData.image?.tag == 'latest') {
                sectionData.image.tag = version
            }
            
            // Update VERSION env var
            if (sectionData.env?.VERSION == '') {
                sectionData.env.VERSION = version
            }
            
            // Production-specific tolerations
            if (params.deploy_location == 'PRODUCTION') {
                sectionData.tolerations = [
                    [
                        key: "nvidia.com/gpu",
                        operator: "Exists",
                        effect: "NoSchedule"
                    ]
                ]
            }
        }
    }
    
    writeYaml file: filePath, data: values, overwrite: true
}
```

**`updateGlobalConfigYaml(filePath)`**
```groovy
// Updates global configuration with environment-specific URLs
def updateGlobalConfigYaml(String filePath) {
    def values = readYaml file: filePath
    
    if (params.deploy_location == 'PRODUCTION') {
        values.env.FRONTEND_URL = "https://unifai-ui-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
        values.env.SSO_BACKEND_HOST = "https://unifai-sso-backend-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
    } else {
        values.env.FRONTEND_URL = "https://unifai-ui-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
        values.env.SSO_BACKEND_HOST = "https://unifai-sso-backend-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
    }
    
    writeYaml file: filePath, data: values, overwrite: true
}
```

---

## Code Conventions

### File Naming
- Pipeline files: `pipeline-<purpose>.groovy`
- Utility files: `<purpose>-bu.groovy` (bu = build utilities)
- All lowercase with hyphens

### Groovy Style Guide

#### Variable Naming
```groovy
// ✅ Correct: camelCase for variables
def buildParams = [:]
def imageRegistry = "images.paas.redhat.com"

// ❌ Avoid: snake_case
def build_params = [:]
```

#### Function Definitions
```groovy
// ✅ Correct: Descriptive names, type hints
def buildDockerImage(String component) {
    echo "Building ${component}"
    // ... implementation
}

// ✅ Correct: Return types documented in comments
/**
 * Pushes image to registry
 * @param component Image component name
 * @return boolean Success status
 */
def pushImage(String component) {
    // ... implementation
    return true
}
```

#### Parameter Definitions
```groovy
// ✅ Correct: Clear descriptions, sensible defaults
properties([
    parameters([
        string(
            name: "VERSION",
            defaultValue: new Date().format('yyyy.MM.dd'),
            description: "Image version tag (auto-generated daily)"
        ),
        booleanParam(
            name: 'deploy_unifai',
            defaultValue: false,
            description: 'True - Deploy UnifAI after build, False - Only build images'
        ),
        choice(
            name: 'deploy_location',
            choices: ['STAGING', 'PRODUCTION'],
            description: 'Target environment for deployment'
        )
    ])
])
```

#### Error Handling
```groovy
// ✅ Correct: Explicit error handling
def status = sh(script: "podman build ...", returnStatus: true)
if (status != 0) {
    echo "Build failed. Check logs."
    sh "cat ${logFile}"
    error("Build failed for ${component}")  // Fail pipeline
}

// ✅ Correct: Safe cleanup with || true
sh "podman rm -f ${component} || true"
sh "podman rmi -f ${component}:${VERSION} || true"
```

#### Logging
```groovy
// ✅ Correct: Emojis for visual clarity
echo "🏗️  Building Docker image for ${component}"
echo "✅ Build completed successfully"
echo "❌ Build failed. Check logs."

// ✅ Correct: Structured log output
echo "---====  Stage: Build Images  ====---"
echo "Component: ${component}"
echo "Version: ${VERSION}"
echo "---================================---"
```

#### Parallel Execution
```groovy
// ✅ Correct: Named parallel stages
stage("Build Images") {
    parallel(
        "SSO Backend": {
            if (params.build_sso_image) {
                buildDockerImage("shared-resources/sso-backend")
            }
        },
        "UI Frontend": {
            if (params.build_gui) {
                buildDockerImage("ui")
            }
        },
        "Dataflow Backend": {
            if (params.build_dataflow_backend) {
                buildDockerImage("backend")
            }
        },
        "MultiAgent Backend": {
            if (params.build_multiagent_backend) {
                buildDockerImage("multi-agent")
            }
        }
    )
}
```

#### Credentials Handling
```groovy
// ✅ Correct: Use withCredentials block
withCredentials([usernamePassword(
    credentialsId: buildParams.ImageRegistryCreds,
    usernameVariable: 'REGISTRY_USER',
    passwordVariable: 'REGISTRY_PASS'
)]) {
    sh """
        podman login -u \${REGISTRY_USER} -p \${REGISTRY_PASS} \${buildParams.ImageRegistry}
    """
}

// ❌ Avoid: Exposing credentials in logs
sh "echo ${PASSWORD}"  // Never do this!
```

---

## Environment Configuration

### Build Parameters (`buildParams` Map)

```groovy
def buildParams = [
    // Logging
    LogLevel: "ALL",
    
    // Source Repository
    MainRepoURL: "github.com",
    MainRepoProject: "redhat-community-ai-tools/UnifAI",
    CredentialsId: "github-unifai-token",
    
    // Credentials Repository
    CredMainRepoURL: "gitlab.cee.redhat.com",
    CredMainRepoProject: "ai_tools/genie-cred-data",
    CredMainRepoBranch: "main",
    CredCredentialsId: "gitlab-genie",
    
    // Jenkins Configuration
    NodeToRun: "tag-slave",
    DevRoot: "/root/workspace/${env.JOB_NAME}",
    
    // Image Registry
    ImageRegistry: "images.paas.redhat.com",
    ImageRegistryPath: "unifai",
    ImageRegistryCreds: "images.paas.registry-unifai"
]
```

### Cluster Configuration

#### Staging Environment
```groovy
def stagingConfig = [
    apiUrl: "https://api.stc-ai-e1-pp.imap.p1.openshiftapps.com:6443",
    namespace: "tag-ai--pipeline",
    frontendUrl: "https://unifai-ui-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com",
    ssoUrl: "https://unifai-sso-backend-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
]
```

#### Production Environment
```groovy
def productionConfig = [
    apiUrl: "https://api.stc-ai-e1-prod.rtc9.p1.openshiftapps.com:6443",
    namespace: "tag-ai--pipeline",
    frontendUrl: "https://unifai-ui-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com",
    ssoUrl: "https://unifai-sso-backend-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
]
```

---

## Best Practices

### 1. **Version Management**
```groovy
// ✅ Use date-based versioning for daily builds
VERSION = new Date().format('yyyy.MM.dd')

// ✅ Use semantic versioning for releases
VERSION = "1.2.3"

// ✅ Always tag with both version and 'latest' (optional)
podman tag myimage:1.2.3 myimage:latest
```

### 2. **Build Optimization**
```groovy
// ✅ Build only changed components
if (params.build_dataflow_backend) {
    buildDockerImage("backend")
}

// ✅ Use parallel builds for independence
parallel(
    "Backend": { buildDockerImage("backend") },
    "Frontend": { buildDockerImage("ui") }
)
```

### 3. **Cleanup**
```groovy
// ✅ Always cleanup after builds
post {
    always {
        cleanWorkspace()
        sh "podman system prune -f"
    }
}
```

### 4. **Deployment Safety**
```groovy
// ✅ Verify before destroying
if (params.deploy_type == "FRESH_INSTALL") {
    input message: "⚠️ This will delete existing deployment. Continue?",
          ok: "Yes, proceed"
    sh "helmfile destroy"
}

// ✅ Use rolling updates for production
if (params.deploy_location == "PRODUCTION" && params.deploy_type == "APPLICATION_UPGRADE") {
    // Rolling update strategy
}
```

### 5. **Debug Mode**
```groovy
// ✅ Enable debug logging when needed
if (params.debug_mode) {
    values.env.LOG_LEVEL = "DEBUG"
    values.env.ROLE = "debug"
}
```

### 6. **Pipeline Testing**
```groovy
// ✅ Use PIPELINE_BRANCH for testing changes
string(
    name: "PIPELINE_BRANCH",
    defaultValue: "main",
    description: "Git branch to take the pipeline from (for testing)"
)
```

---

## Troubleshooting

### Common Issues

#### 1. **Build Failures**

**Symptom:** Podman build fails with timeout or OOM
```
Error: building at STEP "RUN npm install": error building at STEP "RUN npm install": exit status 137
```

**Solution:**
```bash
# Increase Podman memory limits
podman build --memory=4g --cpus=4 -t myimage:latest .

# Or edit pipeline to include resource limits
sh "podman build --memory=4g -t ${component}:${VERSION} -f ${dockerfile} ${context}"
```

#### 2. **Registry Push Failures**

**Symptom:** Authentication failed or timeout
```
Error: authentication required
```

**Solution:**
```bash
# Verify credentials in Jenkins
# Credentials ID: images.paas.registry-unifai

# Manual test
podman login -u <user> -p <password> images.paas.redhat.com

# Check network connectivity
curl -I https://images.paas.redhat.com
```

#### 3. **Deployment Hangs**

**Symptom:** Helmfile apply stuck waiting for resources
```
Waiting for pods to be ready...
```

**Solution:**
```bash
# Check pod status
kubectl get pods -n tag-ai--pipeline

# Check events
kubectl get events -n tag-ai--pipeline --sort-by='.lastTimestamp'

# Force delete stuck pods
kubectl delete pod <pod-name> --grace-period=0 --force

# Restart deployment
helmfile -f dataflow.yaml.gotmpl apply
```

#### 4. **Version Mismatch**

**Symptom:** Pods running old image version after upgrade
```
Current image: backend:2024.11.30
Expected: backend:2024.12.01
```

**Solution:**
```bash
# Verify image tag in registry
podman search images.paas.redhat.com/unifai/backend --list-tags

# Force pull new image
kubectl set image deployment/unifai-dataflow-server backend=images.paas.redhat.com/unifai/backend:2024.12.01

# Or delete pods to force recreation
kubectl delete pods -l app=unifai-dataflow-server
```

#### 5. **Secret Issues**

**Symptom:** Deployment fails due to missing secrets
```
Error: secret "unifai-dataflow-secrets" not found
```

**Solution:**
```bash
# Check if secret exists
kubectl get secret unifai-dataflow-secrets

# Recreate secret (from presync hook)
export default_slack_bot_token="xoxb-..."
export default_slack_user_token="xoxp-..."
bash dataflow-presync.sh

# Or manually create
kubectl create secret generic unifai-dataflow-secrets \
    --from-literal=slack_bot_token="xoxb-..." \
    --from-literal=slack_user_token="xoxp-..."
```

### Debugging Pipeline Issues

#### Enable Verbose Logging
```groovy
// Add to pipeline
def buildParams = [
    LogLevel: "DEBUG",  // Change from "ALL"
    // ...
]

// Or add at stage level
stage("Debug Stage") {
    script {
        sh "set -x"  // Enable bash debug mode
        sh "podman build ..."
    }
}
```

#### Check Jenkins Console Output
1. Go to Jenkins job page
2. Click on build number (e.g., #42)
3. Click "Console Output"
4. Search for error keywords: `Error`, `failed`, `exit status`

#### Manual Testing
```bash
# SSH to Jenkins agent
ssh tag-slave

# Navigate to workspace
cd /root/workspace/UnifAI/image-builder

# Run commands manually
podman build -t backend:test -f backend/Dockerfile .
podman push backend:test images.paas.redhat.com/unifai/backend:test
```

---

## CI/CD Workflow Examples

### Example 1: Build and Deploy All Components to Staging

**Trigger:** Developer merges PR to `main`

**Pipeline Configuration:**
```yaml
Branch: main
VERSION: 2024.12.01 (auto-generated)
build_sso_image: true
build_gui: true
build_dataflow_backend: true
build_multiagent_backend: true
set_image_candidate: true  # Tag as 'latest'
deploy_unifai: true
deploy_type: APPLICATION_UPGRADE
deploy_location: STAGING
debug_mode: false
```

**Expected Result:**
- 4 images built and pushed to registry
- All components upgraded in staging
- Total time: ~20-30 minutes

### Example 2: Hotfix Single Component in Production

**Trigger:** Critical bug fix in UI

**Pipeline Configuration:**
```yaml
# Build Pipeline
Branch: hotfix/ui-fix
VERSION: 2024.12.01-hotfix
build_gui: true
(all others: false)
set_image_candidate: false  # Don't update 'latest'
deploy_unifai: false  # Manual deployment control

# Deployment Pipeline (manual trigger)
deploy_location: PRODUCTION
deploy_type: APPLICATION_UPGRADE
MODULES_TO_DEPLOY: ui
GUI_VERSION: 2024.12.01-hotfix
debug_mode: false
```

**Expected Result:**
- Only UI image built
- Only UI pods upgraded in production
- Zero downtime for other services
- Total time: ~5-10 minutes

### Example 3: Fresh Install of New Environment

**Trigger:** Setting up new test cluster

**Pipeline Configuration:**
```yaml
# Build Pipeline (if needed)
(Build all components with latest code)

# Deployment Pipeline
deploy_location: STAGING
deploy_type: FRESH_INSTALL
VERSION: 2024.12.01
(DF_VERSION, MA_VERSION, GUI_VERSION, SSO_VERSION: empty, uses VERSION)
MODULES_TO_DEPLOY: (empty)
debug_mode: true  # For testing
```

**Expected Result:**
- Existing deployment deleted
- Shared resources deployed first
- All application components deployed
- Debug mode enabled for troubleshooting
- Total time: ~30-45 minutes

---

## Code Review Checklist

When reviewing CI/CD pipeline changes:

### General
- [ ] Pipeline syntax is valid Groovy
- [ ] Variable names follow camelCase convention
- [ ] Functions have descriptive names and comments
- [ ] Error handling includes meaningful messages
- [ ] Credentials use `withCredentials` blocks

### Build Pipeline
- [ ] Parallel builds for independent components
- [ ] Cleanup stages always execute (post/always block)
- [ ] Image names match registry convention
- [ ] Version tags are applied correctly
- [ ] Podman commands use correct context paths

### Deployment Pipeline
- [ ] Chart versions updated before deployment
- [ ] Values files updated with correct image tags
- [ ] Environment-specific configuration applied
- [ ] Deployment type logic is correct
- [ ] Rollback strategy documented

### Security
- [ ] No credentials hardcoded in pipeline
- [ ] Credentials IDs reference Jenkins secrets
- [ ] Registry credentials properly scoped
- [ ] Secret management follows best practices

### Performance
- [ ] Parallel stages where possible
- [ ] Unnecessary steps removed
- [ ] Timeouts set appropriately
- [ ] Resource cleanup implemented

### Documentation
- [ ] Parameters have clear descriptions
- [ ] Stage names are descriptive
- [ ] Comments explain non-obvious logic
- [ ] Emoji indicators for readability

---

## Glossary

| Term | Definition |
|------|------------|
| **Jenkins** | Open-source automation server for CI/CD |
| **Groovy** | JVM-based scripting language used for Jenkins pipelines |
| **Podman** | Daemonless container engine (Docker alternative) |
| **Helmfile** | Declarative spec for deploying Helm charts |
| **OpenShift** | Enterprise Kubernetes platform by Red Hat |
| **Image Registry** | Repository for storing container images |
| **Tag** | Version identifier for container images |
| **Fresh Install** | Complete deployment from scratch (deletes existing) |
| **Application Upgrade** | Rolling update of specific components |
| **Presync Hook** | Script executed before Helm deployment |
| **Postsync Hook** | Script executed after Helm deployment |
| **Helmfile** | Declarative specification for Helm chart deployments |
| **Jenkins Agent** | Worker node that executes pipeline jobs |

