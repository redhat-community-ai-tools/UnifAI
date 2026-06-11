properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "main", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "main", description: "Branch to deploy from."),
        
        // 🚀 Deployment Parameters
        choice(name: 'deploy_location', choices: ['STAGING', 'PRODUCTION'], description: 'Deployment environment'),
        choice(name: 'deploy_type', choices: ['FRESH_INSTALL', 'APPLICATION_UPGRADE'], description: 'Deployment type'),
        string(name: "VERSION", defaultValue: "", description: "DONT SET THIS VALUE!"),
        string(name: "BACKEND_VERSION", defaultValue: "", description: "Image tag for backend"),
        string(name: "RAG_VERSION", defaultValue: "", description: "Image tag for rag"),
        string(name: "MA_VERSION", defaultValue: "", description: "Image tag for multi-agent"),
        string(name: "GUI_VERSION", defaultValue: "", description: "Image tag for UI"),
        string(name: "IDENTITY_VERSION", defaultValue: "", description: "Image tag for Identity"),
        string(name: "MODULES_TO_DEPLOY", defaultValue: "", description: "Comma-separated list of modules to update (e.g. rag,multiagent,backend,ui,identity)"),
        booleanParam(name: 'debug_mode', defaultValue: false, description: 'debug the pods'),
    ])
])

def buildParams = [
    LogLevel           : "ALL",
    MainRepoURL        : "github.com",
    MainRepoProject    : "redhat-community-ai-tools/UnifAI",
    MainRepoBranch     : "${params.BRANCH}",
    CredentialsId      : "github-unifai-token",
    CredMainRepoURL    : "github.com",
    CredMainRepoProject: "redhat-community-ai-tools/UnifAI-secrets", 
    CredMainRepoBranch : "main",
    CredCredentialsId  : "jenkins_agent_deploy_key",

    NodeToRun          : "tag-slave",
    DevRoot            : "/root/workspace/${env.JOB_NAME}",
    ImageRegistry      : "images.paas.redhat.com",
    ImageRegistryPath  : "unifai",
    ImageRegistryCreds : "images.paas.registry-unifai",
]

def updateChartVersions(rootPath, version) {

    def chartFiles = sh(
        script: "find ${rootPath} -name 'Chart.yaml'",
        returnStdout: true
    ).trim().split('\n')

    chartFiles.each { file ->
        def chart = readYaml file: file
        //chart.version = params.VERSION
        chart.appVersion = version
        echo "📝 Overwriting YAML file with version: ${version} in: ${file}"
        writeYaml file: file, data: chart, overwrite: true
    }
}

def updateGlobalConfigYaml(String filePath) {
    echo "🔄 Loading values from: ${filePath}"

    def values = readYaml file: filePath
    values.each { sectionName, sectionData ->

    if (values?.env) {
        values.env.FRONTEND_URL = "https://unifai-ui-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
        // will be used once SSO team adds the new routes to the configuration
        values.env.IDENTITY_HOST = "https://unifai-identity-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
        // values.env.IDENTITY_HOST = "https://unifai-sso-backend-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
    }
    writeYaml file: filePath, data: values, overwrite: true
    echo "📄 successfully Updated routes values in ${filePath}:\n" + writeYaml(returnText: true, data: values)
    }
}

def updateValuesYaml(String filePath , String version) {
    echo "🔄 Loading values from: ${filePath}"
    echo "📝 Overwriting YAML file: ${filePath}"
    def values = readYaml file: filePath

    values.each { sectionName, sectionData ->
        if (sectionData instanceof Map) {
            if (params.debug_mode) {
                echo "🛠 Setting debug mode in section: ${sectionName}"
                sectionData.debug = true
                sectionData.env = sectionData.env ?: [:]
                sectionData.env.ROLE = "debug"
                echo "🏷 Updated debug: ${sectionData}"
            }

            if (sectionData.image?.tag == 'latest') {
                sectionData.image.tag = version
                echo "🏷 Updated image tag : ${sectionData.image.tag}"
            }
            if (sectionData.env?.VERSION == '') {
                sectionData.env.VERSION = version
                echo "🏷 Updated VERSION: ${sectionData.env.VERSION}"
            }

            if (params.deploy_location == 'PRODUCTION') {

                if (sectionData.tolerations instanceof List) {
                    sectionData.tolerations = [
                        [
                            key: "nvidia.com/gpu",
                            operator: "Exists",
                            effect: "NoSchedule"
                        ],
                        [
                            key: "tenant",
                            operator: "Equal",
                            value: "tag-ai",
                            effect: "NoSchedule"
                        ]
                    ]
                    echo "🏷 Updated tolerations: ${sectionData.tolerations}"
                }
            }
        }
    }

    writeYaml file: filePath, data: values, overwrite: true
    echo "✅ Updated ${filePath} successfully"
}

def updateDeployerEnv() {
    echo "🔄 updating deployer env with new values"
    def identity_env_file = null
    def redis_env_file = null
    def multiagent_env_file = null
    if (params.deploy_location == 'PRODUCTION') {
        updateEnvFile("./UnifAI-secrets/.env", "umami_website_name", "unifai-production")
        identity_env_file = "./UnifAI-secrets/production/.env_identity"
        redis_env_file = "./UnifAI-secrets/production/.env_redis"
        multiagent_env_file = "./UnifAI-secrets/production/.env_multi_agent"
    } else if (params.deploy_location == 'STAGING') {
        updateEnvFile("./UnifAI-secrets/.env", "umami_website_name", "unifai-staging")
        identity_env_file = "./UnifAI-secrets/staging/.env_identity"
        redis_env_file = "./UnifAI-secrets/staging/.env_redis"
        multiagent_env_file = "./UnifAI-secrets/staging/.env_multi_agent"
    }
    echo("✅ Deployer env updated successfully")
    return [identity_env_file, redis_env_file, multiagent_env_file]
}


def updateEnvFile(String filePath, String key, String value) {
    if (!fileExists(filePath)) {
        error "❌ File not found: ${filePath}"
    }
    
    echo "🔧 Updating ${key} in ${filePath}..."
    def content = readFile(filePath)
    // Safe replacement
    def newContent = content.replaceFirst(/(?m)^${key}=.*/, "${key}=${value}")
    writeFile(file: filePath, text: newContent)
}

def deployModules(module){
    echo "deploying modules: ${module}"
    sh("podman exec -t helmfile bash -lc 'helmfile -f ${module}.yaml.gotmpl apply'")
    echo("${module} successfully deployed")
    sh("sleep 5")
}

def deleteRunningApplication(){
    echo("Removing running UnifAI application")
    cleanOldDataflow()
    def charts = ["backend", "rag", "multiagent", "ui", "identity", "shared-resources"]

    charts.each { chart ->
        sh("podman exec -t helmfile bash -c 'helmfile destroy -f ${chart}.yaml.gotmpl --deleteWait'")
    }

    echo("Wait for resource deletion...")
    sh("""
        until ! oc get deployment,statefulset,svc | grep 'unifai\\|qdrant\\|mongo\\|rabbitmq'; do
            echo 'Waiting for deployment deletion...'
            sleep 5
        done
    """)
    echo("UnifAi application successfully deleted")
    sh("sleep 10")
}

// temporary fix for dataflow deployment deletion, after we move completely to the new rag naming this function is obsolete
def cleanOldDataflow(){
    echo("Removing old dataflow application")
    
    // Capture the output properly
    def result = sh(
        script: "podman exec -t helmfile bash -c 'helm ls | grep 'dataflow' || true'",
        returnStdout: true
    ).trim()
    
    if(result.length() > 0) {
        // Split by newlines to get all releases, not just the first one
        echo("found old dataflow releases: ${result}")
        def releases = result.split('\n')
        
        releases.each { release ->
            // Extract the release name (first column in helm ls output)
            def releaseName = release.split(/\s+/)[0]
            echo("Deleting helm release: ${releaseName}")
            sh("podman exec -t helmfile bash -c 'helm uninstall ${releaseName}'")
        }
        
        // Wait for all dataflow resources to be deleted
        sh("""
            until ! oc get deployment,statefulset,svc 2>/dev/null | grep 'dataflow'; do
                echo 'Waiting for dataflow deployment deletion...'
                sleep 5
            done
        """)
        echo("All dataflow applications successfully deleted")
        sh("sleep 5")
    } else {
        echo("No dataflow releases found")
    }
}

def cleanWorkspace() {
    sh """
        podman rm -f helmfile
        sleep 5        
    """
}

pipeline {
    agent { node { label "${buildParams.NodeToRun}" } }

    stages {

        stage('Checkout') {
            steps {
                script {
                    echo "================ Deployment Configuration ================="
                    echo "Branch            : ${params.BRANCH}"
                    echo "Version           : ${params.VERSION}"
                    echo "Deployment Type   : ${params.deploy_type}"
                    echo "Deployment Target : ${params.deploy_location}"
                    echo "Debug mode        : ${params.debug_mode}"
                    echo "Modules to deploy : ${params.MODULES_TO_DEPLOY}"
                    echo "Workspace Path:    ${buildParams.DevRoot}/${params.BRANCH}/"
                    echo "==========================================================="
                }
                echo("CheckOut ${buildParams.MainRepoProject}/${params.BRANCH}")
                dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                    checkout([$class: 'GitSCM',
                        branches: [[name: "${params.BRANCH}"]],
                        submoduleCfg: [],
                        userRemoteConfigs: [[
                            credentialsId: "${buildParams.CredentialsId}",
                            url: "git@${buildParams.MainRepoURL}:${buildParams.MainRepoProject}.git"
                        ]]
                    ])
                }
                dir("${buildParams.DevRoot}/${params.BRANCH}/helm/") {
                    checkout([$class: 'GitSCM',
                        branches: [[name: "${buildParams.CredMainRepoBranch}"]],
                        doGenerateSubmoduleConfigurations: false,
                        //extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${buildParams.DevRoot}/${params.BRANCH}"]],
                        extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${buildParams.DevRoot}/${params.BRANCH}/helm/UnifAI-secrets/"]],
                        submoduleCfg: [],
                        userRemoteConfigs: [[
                            credentialsId: "${buildParams.CredCredentialsId}",
                            url: "git@${buildParams.CredMainRepoURL}:${buildParams.CredMainRepoProject}.git"
                        ]]
                    ])
                }
            }
        }
        
        stage('Deploy UnifAI') {
            steps {
                dir("${buildParams.DevRoot}/${params.BRANCH}/helm/") {
                    script {
                        // Declare variables outside the switch statement
                        def ClusterAddress = ''
                        def NameSpace = ''
                        def ClusterAccessToken = ''
                        
                        switch(params.deploy_location) {
                            case 'STAGING':
                                ClusterAddress = 'https://api.stc-ai-e1-pp.imap.p1.openshiftapps.com:6443'
                                NameSpace = "tag-ai--pipeline"
                                ClusterAccessToken = 'tenantaccess-unifai-sa-pp'
                                break
                            case 'PRODUCTION':
                                ClusterAddress = 'https://api.stc-ai-e1-prod.rtc9.p1.openshiftapps.com:6443'
                                NameSpace = "tag-ai--pipeline"
                                ClusterAccessToken = 'tenantaccess-unifai-sa-prod'
                                updateGlobalConfigYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/global-config.yaml")
                                break
                            default:
                                error("Invalid deployment location: ${params.deploy_location}")
                        }
                        
                        def module = "helmfile"
                        
                        withCredentials([
                            string(credentialsId: "${ClusterAccessToken}", variable: 'token'),
                        ]){
                            echo("Creating helm deployment pod")
                            sh("oc login --token=${token} --server=${ClusterAddress}")
                            sh("oc project ${NameSpace}")
                            def (identity_env_file, redis_env_file, multiagent_env_file) = updateDeployerEnv()
                            echo("Deploy Helm container")
                            sh("podman run --replace -dt --env-file=${identity_env_file} --env-file=${redis_env_file} --env-file=${multiagent_env_file} --env-file=./UnifAI-secrets/.env --workdir /helm/charts -v .:/helm/charts:Z -v ~/.kube/:/helm/.kube:Z --name helmfile ghcr.io/helmfile/helmfile:latest bash")
                            
                            def modules = params.MODULES_TO_DEPLOY.tokenize(',')
                            if(params.deploy_type == 'FRESH_INSTALL') {
                                modules.add(0,'shared-resources')
                                deleteRunningApplication()
                            }
                            
                            for (mod in modules) {
                                switch(mod.trim()) {
                                    case 'shared-resources':
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/shared-resource-values.yaml", version)
                                        deployModules('shared-resources')
                                        break

                                    case 'identity':
                                        def version = params.IDENTITY_VERSION?.trim() ?: params.VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/shared-resources/identity/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/identity-values.yaml", version)
                                        deployModules('identity')
                                        break

                                    case 'backend':
                                        def version = params.BACKEND_VERSION?.trim() ?: params.VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/backend/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/backend-resource-values.yaml", version)
                                        deployModules('backend')
                                        break

                                    case 'rag':
                                        def version = params.RAG_VERSION?.trim() ?: params.VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/rag/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/rag-resource-values.yaml", version)
                                        deployModules('rag')
                                        break

                                    case 'multiagent':
                                        def version = params.MA_VERSION?.trim() ?: params.VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/multiagent/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/multiagent-resource-values.yaml", version)
                                        deployModules('multiagent')
                                        break

                                    case 'ui':
                                        def version = params.GUI_VERSION?.trim() ?: params.VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/ui/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/ui-values.yaml", version)
                                        deployModules('ui')
                                        break
                                }
                            }
                            echo("Deploy successfully completed")
                        }
                        cleanWorkspace()
                    }
                }
            }
        }
    }

}