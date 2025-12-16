properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "main", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "main", description: "Git branch to build images from."),
        string(name: "VERSION", defaultValue: new Date().format('yyyy.MM.dd'), description: "Image version tag"),
        
        // 🛠️ Image Build Parameters
        booleanParam(name: 'build_sso_image', defaultValue: false, description: 'Create image for sso-backend and sso-nginx'),
        booleanParam(name: 'build_gui', defaultValue: false, description: 'Create image for UI'),
        booleanParam(name: 'build_dataflow_backend', defaultValue: false, description: 'Create image for dataflow backend'),
        booleanParam(name: 'build_multiagent_backend', defaultValue: false, description: 'Create image for multiagent backend'),
        booleanParam(name: 'set_image_candidate', defaultValue: false, description: 'Set images with latest tag'),
        
        // 🚀 Deployment Parameters
        booleanParam(name: 'deploy_unifai', defaultValue: false, description: 'True - Deploy UnifAI, False - Only build images and upload to image-paas'),
        choice(name: 'deploy_type', choices: ['FRESH_INSTALL', 'APPLICATION_UPGRADE'], description: 'Deployment type'),
        choice(name: 'deploy_location', choices: ['STAGING', 'PRODUCTION'], description: 'Deployment environment'),
        booleanParam(name: 'debug_mode', defaultValue: false, description: 'True - create pods with debug mode')
        
    ])
])

def buildParams = [
    LogLevel           : "ALL",
    MainRepoURL        : "github.com",
    MainRepoProject    : "redhat-community-ai-tools/UnifAI",
    CredentialsId      : "github-unifai-token",
    NodeToRun          : "tag-slave",
    DevRoot            : "/root/workspace/${env.JOB_NAME}",
    ImageRegistry      : "images.paas.redhat.com",
    ImageRegistryPath  : "unifai",
    ImageRegistryCreds : "images.paas.registry-unifai",

    CredMainRepoURL    : "gitlab.cee.redhat.com",
    CredMainRepoProject: "ai_tools/genie-cred-data", 
    CredMainRepoBranch : "main",
    CredCredentialsId  : "gitlab-genie",
]


def buildDockerImage(String component) {
    // Default assumptions: Dockerfile at component root, repo-root as build context
    String dockerfile = "Dockerfile"
    String context = "."

    // Special-case UI: Dockerfile lives under deployment/, context is repo root
    // to allow access to README.md which is imported by the frontend build
    if (component == "ui") {
        dockerfile = "deployment/Dockerfile"
        context = "."
    }

    String logFile = "/tmp/${component.replace("/", "_")}_build.log"

    echo("---====  buildDockerImage ${component}  ====---")

    def componentLower = component.toLowerCase().replace("-", "")

    def status = sh(script: "podman build -t ${componentLower}:${VERSION} -t ${componentLower}:latest -f ${component}/${dockerfile} ${context} > ${logFile} 2>&1", returnStatus: true)

    if (status != 0) {
        echo("Build failed for module: ${componentLower}. Check ${logFile} for details.")
        sh "cat ${logFile}"
        return false
    } else {
        echo("Build completed successfully for module: ${componentLower}.")
        return true
    }
}

def tagAndPushImageToRegistry( buildParams,component) {
    echo("Tagging and pushing image for ${component}.")
    component = component.replace("-", "")
    def componentLower = component.toLowerCase()

    withCredentials([usernamePassword(
        credentialsId: "${buildParams.ImageRegistryCreds}",
        usernameVariable: 'REGISTRY_USER',
        passwordVariable: 'REGISTRY_PASS'
    )]) {
        sh """
            podman login -u ${REGISTRY_USER} -p ${REGISTRY_PASS} ${buildParams.ImageRegistry}
            podman push ${componentLower}:${VERSION} ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${componentLower}:${VERSION}
        """
        if (params.set_image_candidate) {
            sh """
                podman push --quiet ${componentLower}:${VERSION} ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${componentLower}:latest
            """
        }
        echo("Image for ${componentLower} has been tagged and pushed to ${buildParams.ImageRegistry}/${buildParams.ImageRegistryPath}/${componentLower}:${VERSION}")
    }
}

def cleanWorkspace(component) {
    sh """
        podman rm -f  ${component} || true
        podman rmi -f ${component}:${VERSION} || true
        podman rmi -f ${component}:latest || true  
    """
}

def cleanPodmanSystem() {
    sh """
        for container in \$(podman ps --external |awk '{ print \$1 }'); do podman rm -f \$container ;done
        for image in \$(podman images |grep none | awk '{print \$3}') ;do  podman rmi -f \$image ; done
        podman system prune --force
        podman system prune --force --external
    """
}

pipeline {
    agent { node { label "${buildParams.NodeToRun}" } }

    stages {
        stage('Checkout') {
            steps {
                echo("CheckOut ${buildParams.MainRepoProject}/${params.BRANCH}")
                dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                    checkout([$class: 'GitSCM',
                    branches: [[name: "${params.BRANCH}"]],
                    extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${buildParams.DevRoot}/${params.BRANCH}"]],
                    submoduleCfg: [],
                    userRemoteConfigs: [[
                        credentialsId: "${buildParams.CredentialsId}",
                        url: "https://${buildParams.MainRepoURL}/${buildParams.MainRepoProject}.git"
                        ]]
                    ])
                }
                dir("${buildParams.DevRoot}/${params.BRANCH}/ui/") {
                    checkout([$class: 'GitSCM',
                        branches: [[name: "${buildParams.CredMainRepoBranch}"]],
                        doGenerateSubmoduleConfigurations: false,
                        //extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${buildParams.DevRoot}/${params.BRANCH}"]],
                        extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "genie-cred-data"]],
                        submoduleCfg: [],
                        userRemoteConfigs: [[
                            credentialsId: "${buildParams.CredCredentialsId}",
                            url: "https://${buildParams.CredMainRepoURL}/${buildParams.CredMainRepoProject}.git"
                        ]]
                    ])
                }
                
            }
        }

        stage('Build and Push Images') {
            parallel {
                stage('build_sso_image') {
                    when { expression { params.build_sso_image } }
                    steps {
                        script {
                            def component = "shared-resources/sso-backend"
                            def module = ""
                            dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                                cleanWorkspace(component)
                                if (buildDockerImage(component)) {
                                    tagAndPushImageToRegistry(buildParams,component)
                                    cleanWorkspace(component)
                                } else {
                                    error("Terminating process for ${component}: Build failed")
                                }
                            }
                        }
                    }
                }
                stage('build_dataflow_image') {
                    when { expression { params.build_dataflow_backend } }
                    steps {
                        script {
                            def component = "backend"
                            def module = ""
                            dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                                cleanWorkspace(component)
                                if (buildDockerImage(component)) {
                                    tagAndPushImageToRegistry(buildParams,component)
                                    cleanWorkspace(component)
                                } else {
                                    error("Terminating process for ${component}: Build failed")
                                }
                            }
                        }
                    }
                }
                stage('build_multiagent_image') {
                    when { expression { params.build_multiagent_backend } }
                    steps {
                        script {
                            def component = "multi-agent"
                            dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                                cleanWorkspace(component)
                                if (buildDockerImage(component)) {
                                    tagAndPushImageToRegistry(buildParams, component)
                                    cleanWorkspace(component)
                                } else {
                                    error("Terminating process for ${component}: Build failed")
                                }
                            }
                        }
                    }
                }
                stage('build_gui_image') {
                    when { expression { params.build_gui } }
                    steps {
                        script {
                            def component = "ui"
                            def module = ""
                            dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                                cleanWorkspace(component)
                                if (buildDockerImage(component)) {
                                    tagAndPushImageToRegistry(buildParams, component)
                                    cleanWorkspace(component)
                                } else {
                                    error("Terminating process for ${component}: Build failed")
                                }
                            }
                        }
                    }
                }
            }
        }

        stage('Deploy Application') {
            when {
                expression { return params.deploy_unifai }
            }
            steps {
                script {
                    def modules = []
                    if (params.build_sso_image) modules << 'sso'
                    if (params.build_dataflow_backend) modules << 'dataflow'
                    if (params.build_multiagent_backend) modules << 'multiagent'
                    if (params.build_gui) modules << 'ui'
                    def modulesToDeploy = modules.join(',')

                    echo "Triggering deployment pipeline with MODULES_TO_DEPLOY = ${modulesToDeploy}"
                    build job: 'unifai-app-deployer',
                    parameters: [
                        string(name: 'PIPELINE_BRANCH', value: params.PIPELINE_BRANCH),
                        string(name: 'deploy_location', value: params.deploy_location),
                        string(name: 'deploy_type', value: params.deploy_type),
                        string(name: 'BRANCH', value: params.BRANCH),
                        string(name: 'VERSION', value: params.VERSION),
                        string(name: 'MODULES_TO_DEPLOY', value: modulesToDeploy),
                        booleanParam(name: 'debug_mode', value: params.debug_mode),
                    ]
                }
            }
        }
    }

}

