properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "main", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "main", description: "Branch to deploy from."),
        
        // 🚀 Deployment Parameters
        choice(name: 'deploy_location', choices: ['STAGING', 'PRODUCTION'], description: 'Deployment environment'),
        choice(name: 'deploy_type', choices: ['FRESH_INSTALL', 'APPLICATION_UPGRADE'], description: 'Deployment Deployment type fresh install - delete everything including shared resources, application upgrade - update only the specified modules'),
        string(name: "BACKEND_VERSION", defaultValue: "", description: "Image tag for backend"),
        string(name: "RAG_VERSION", defaultValue: "", description: "Image tag for rag"),
        string(name: "MA_VERSION", defaultValue: "", description: "Image tag for multi-agent"),
        string(name: "GUI_VERSION", defaultValue: "", description: "Image tag for UI"),
        string(name: "IDENTITY_VERSION", defaultValue: "", description: "Image tag for Identity"),
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
    VaultBasePath      : "apps/automation-and-tools/unifai",
]

def secret_lists = [
    cluster: ['cluster_address', 'cluster_access_token', 'tenant_name', 'namespace', 'jenkins_credentials_id'],
    redis: ['redis_username', 'redis_password'],
    identity: ['client_id', 'client_secret', 'keycloak_realm', 'keycloak_base_url'],
    rabbitmq: ['rmq_username', 'rmq_password'],
    umami: ['umami_username', 'umami_password'],
    // keycloak: ['keycloak_base_url', 'client_id', 'client_secret', 'keycloak_realm'],
    global_config: ['secret_key', 'vault_role_id', 'vault_secret_id', 'langfuse_base_url', 'langfuse_public_key', 'langfuse_secret_key', 'slack_signing_secret', 'slack_app_token', 'slack_bot_token'],
    multiagent: ['CREDENTIAL_ENCRYPTION_KEY', 'OAUTH_STATE_SECRET', 'GCP_SA_KEY_JSON_B64', 'langfuse_public_key', 'langfuse_secret_key'],
    rag: ['default_slack_bot_token', 'default_slack_user_token'],
    ]

def generateVaultSecretsEnvFile(String vaultBasePath, Map secretMap ) {
    def envFilePath = "./vault_secrets.env"
    echo "🔐 Generating Vault secrets env file: ${envFilePath}"
    sh "rm -f ${envFilePath}"
    sh "touch ${envFilePath}"

    secretMap.each { module, secrets ->
        echo "🔄 Fetching secrets for module: ${module}"
        withVault(
            configuration: [
                vaultUrl: '',
                vaultCredentialId: ''
            ],
            vaultSecrets: [
                [
                    path: "${vaultBasePath}/${params.deploy_location.toLowerCase()}/${module}",
                    engineVersion: 2,
                    secretValues: secrets.collect { key -> [envVar: key, vaultKey: key] }
                ]
            ]
        ) {
            secrets.each { secret ->
                sh "echo '${secret}='\"\$${secret}\" >> ${envFilePath}"
            }
        }
    }
    echo "✅ Vault secrets env file created: ${envFilePath}"
    return envFilePath
}

def buildModulesList() {
    def modules = []
    if (params.IDENTITY_VERSION?.trim()) modules.add('identity')
    if (params.BACKEND_VERSION?.trim()) modules.add('backend')
    if (params.RAG_VERSION?.trim())     modules.add('rag')
    if (params.MA_VERSION?.trim())      modules.add('multiagent')
    if (params.GUI_VERSION?.trim())     modules.add('ui')
    return modules
}

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
        values.env.IDENTITY_HOST = "https://unifai-identity-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
    }
    writeYaml file: filePath, data: values, overwrite: true
    echo "📄 successfully Updated routes values in ${filePath}:\n" + writeYaml(returnText: true, data: values)
    }
}

def updateBackendSlackSocket(String filePath, boolean enabled) {
    echo "🔄 Loading values from: ${filePath}"
    def values = readYaml file: filePath

    values.unifai_backend = values.unifai_backend ?: [:]
    values.unifai_backend.slackSocket = values.unifai_backend.slackSocket ?: [:]
    values.unifai_backend.slackSocket.enabled = enabled

    writeYaml file: filePath, data: values, overwrite: true
    echo "🏷 Set slackSocket.enabled=${enabled} in ${filePath} (deploy_location=${params.deploy_location})"
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

def deployModules(module){
    echo "deploying modules: ${module}"
    sh("podman exec -t helmfile bash -lc 'helmfile -f ${module}.yaml.gotmpl apply'")
    echo("${module} successfully deployed")
    sh("sleep 5")
}

def deleteRunningApplication(){
    echo("Removing running UnifAI application")
    // cleanOldDataflow()
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

def cleanWorkspace() {
    sh """
        podman rm -f helmfile || true
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
                    echo "Deployment Type   : ${params.deploy_type}"
                    echo "Deployment Target : ${params.deploy_location}"
                    echo "Debug mode        : ${params.debug_mode}"
                    echo "Identity Version  : ${params.IDENTITY_VERSION}"
                    echo "Backend Version   : ${params.BACKEND_VERSION}"
                    echo "RAG Version       : ${params.RAG_VERSION}"
                    echo "Multiagent Version: ${params.MA_VERSION}"
                    echo "UI Version        : ${params.GUI_VERSION}"
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
                        if (params.deploy_location == 'PRODUCTION') {
                            updateGlobalConfigYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/global-config.yaml")
                        }

                        // Fetch ALL secrets from Vault (including cluster)
                        def vaultEnvFile = generateVaultSecretsEnvFile(buildParams.VaultBasePath, secret_lists)

                        // Parse cluster connection details from the generated vault env file
                        def vaultEnvMap = [:]
                        readFile(vaultEnvFile).trim().split('\n').each { line ->
                            if (line && !line.startsWith('#')) {
                                def parts = line.split('=', 2)
                                vaultEnvMap[parts[0].trim()] = parts[1].trim()
                            }
                        }
                        def ClusterAddress = vaultEnvMap.cluster_address
                        def NameSpace = vaultEnvMap.namespace
                        def ClusterCredsId = vaultEnvMap.jenkins_credentials_id

                        // Non-secret config still passed from UnifAI-secrets for now (umami_url, admin_allowed_users, etc.)
                        def configEnvFile = "./UnifAI-secrets/${params.deploy_location.toLowerCase()}/.env"

                        withCredentials([
                            string(credentialsId: "${ClusterCredsId}", variable: 'token'),
                        ]){
                            echo("Creating helm deployment pod")
                            sh('oc login --token=$token --server=' + ClusterAddress)
                            sh("oc project ${NameSpace}")
                            echo("Deploy Helm container")
                            sh("podman run --replace -dt --env-file=${vaultEnvFile} --env-file=${configEnvFile} --workdir /helm/charts -v .:/helm/charts:Z -v ~/.kube/:/helm/.kube:Z --name helmfile ghcr.io/helmfile/helmfile:latest bash")
                            def modules = buildModulesList()
                            if (modules.isEmpty()) {
                                error("No application modules selected for deployment. Set at least one *_VERSION parameter.")
                            }
                            if(params.deploy_type == 'FRESH_INSTALL') {
                                modules.add(0,'shared-resources')
                                deleteRunningApplication()
                            }
                            
                            for (mod in modules) {
                                switch(mod.trim()) {
                                    case 'shared-resources':
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/shared-resource-values.yaml", "")
                                        deployModules('shared-resources')
                                        break

                                    case 'identity':
                                        def version = params.IDENTITY_VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/shared-resources/identity/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/identity-values.yaml", version)
                                        deployModules('identity')
                                        break

                                    case 'backend':
                                        def version = params.BACKEND_VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/backend/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/backend-resource-values.yaml", version)
                                        // Slack Socket Mode sidecar depends on a bot token that is only valid
                                        // in PRODUCTION today; skip it entirely on other deploy targets so a
                                        // Slack auth failure can't take the whole backend pod's readiness down.
                                        updateBackendSlackSocket(
                                            "${buildParams.DevRoot}/${params.BRANCH}/helm/values/backend-resource-values.yaml",
                                            params.deploy_location == 'PRODUCTION'
                                        )
                                        deployModules('backend')
                                        break

                                    case 'rag':
                                        def version = params.RAG_VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/rag/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/rag-resource-values.yaml", version)
                                        deployModules('rag')
                                        break

                                    case 'multiagent':
                                        def version = params.MA_VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/multiagent/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/multiagent-resource-values.yaml", version)
                                        deployModules('multiagent')
                                        break

                                    case 'ui':
                                        def version = params.GUI_VERSION?.trim()
                                        updateChartVersions("${buildParams.DevRoot}/${params.BRANCH}/helm/ui/", version)
                                        updateValuesYaml("${buildParams.DevRoot}/${params.BRANCH}/helm/values/ui-values.yaml", version)
                                        deployModules('ui')
                                        break

                                }
                            }
                            echo("Deploy successfully completed")
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            sh "rm -f ${buildParams.DevRoot}/${params.BRANCH}/helm/vault_secrets.env"
            cleanWorkspace()
        }
    }

}