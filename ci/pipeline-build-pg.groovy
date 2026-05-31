properties([
    parameters([
        // 🌐 Global Parameters
        string(name: "PIPELINE_BRANCH", defaultValue: "main", description: "Git branch to take the pipeline from, for testing purpose"),
        string(name: "BRANCH", defaultValue: "main", description: "Git branch to build images from."),
        string(name: "VERSION", defaultValue: new Date().format('yyyy.MM.dd'), description: "Image version tag"),
        
        // 🛠️ Image Build Parameters
        booleanParam(name: 'build_identity_image', defaultValue: false, description: 'Create image for identity'),
        booleanParam(name: 'build_gui', defaultValue: false, description: 'Create image for UI'),
        booleanParam(name: 'build_rag_backend', defaultValue: false, description: 'Create image for rag backend'),
        booleanParam(name: 'build_multiagent_backend', defaultValue: false, description: 'Create image for multiagent backend'),
        booleanParam(name: 'build_backend', defaultValue: false, description: 'Create image for platform backend'),
        booleanParam(name: 'set_image_candidate', defaultValue: false, description: 'Set images with latest tag'),
        
        // 🚀 Deployment Parameters
        booleanParam(name: 'deploy_unifai', defaultValue: false, description: 'True - Deploy UnifAI, False - Only build images and upload to image-paas'),
        choice(name: 'deploy_type', choices: ['FRESH_INSTALL', 'APPLICATION_UPGRADE'], description: 'Deployment type'),
        choice(name: 'deploy_namespace', choices: ['tag-ai--playground', 'tag-ai--playground2'], description: 'Target OpenShift namespace'),
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

    CredMainRepoURL    : "github.com",
    CredMainRepoProject: "redhat-community-ai-tools/UnifAI-secrets", 
    CredMainRepoBranch : "main",
    CredCredentialsId  : "jenkins_agent_deploy_key",
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

    sh "echo '>>> Build START: ${componentLower}' && date"
    def status = sh(script: """#!/bin/bash
        set -o pipefail
        podman build -t ${componentLower}:${VERSION} -t ${componentLower}:latest -f ${component}/${dockerfile} ${context} 2>&1 | awk '{ print strftime("[%Y-%m-%d %H:%M:%S]"), \$0; fflush() }' > ${logFile}""",
        returnStatus: true)
    sh "echo '>>> Build END: ${componentLower}' && date"

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
    sh "echo '>>> Push START: ${component}' && date"
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
    sh "echo '>>> Push END: ${component}' && date"
}

def cleanWorkspace(component) {
    def componentLower = component.toLowerCase().replace("-", "")
    sh """
        podman rm -f  ${componentLower} || true
        podman rmi \$(podman images -a --filter "reference=${componentLower}:${VERSION}" -q) -f || true
        podman rmi -f ${componentLower}:latest || true  
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
                sh "echo '>>> Checkout START' && date"
                echo("CheckOut ${buildParams.MainRepoProject}/${params.BRANCH}")
                dir("${buildParams.DevRoot}/${params.BRANCH}/") {
                    checkout([$class: 'GitSCM',
                    branches: [[name: "${params.BRANCH}"]],
                    extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${buildParams.DevRoot}/${params.BRANCH}"]],
                    submoduleCfg: [],
                    userRemoteConfigs: [[
                        credentialsId: "${buildParams.CredentialsId}",
                        url: "git@${buildParams.MainRepoURL}:${buildParams.MainRepoProject}.git"
                        ]]
                    ])
                }
                dir("${buildParams.DevRoot}/${params.BRANCH}/ui/") {
                    checkout([$class: 'GitSCM',
                        branches: [[name: "${buildParams.CredMainRepoBranch}"]],
                        doGenerateSubmoduleConfigurations: false,
                        //extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "${buildParams.DevRoot}/${params.BRANCH}"]],
                        extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: "UnifAI-secrets"]],
                        submoduleCfg: [],
                        userRemoteConfigs: [[
                            credentialsId: "${buildParams.CredCredentialsId}",
                            url: "git@${buildParams.CredMainRepoURL}:${buildParams.CredMainRepoProject}.git"
                        ]]
                    ])
                }
                sh "echo '>>> Checkout END' && date"
            }
        }

        stage('Build and Push Images') {
            parallel {
                stage('build_identity_image') {
                    when { expression { params.build_identity_image } }
                    steps {
                        script {
                            def component = "shared-resources/identity"
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
                stage('build_rag_image') {
                    when { expression { params.build_rag_backend } }
                    steps {
                        script {
                            def component = "rag"
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
                stage('build_backend_image') {
                    when { expression { params.build_backend } }
                    steps {
                        script {
                            def component = "backend"
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
                    if (params.build_identity_image) modules << 'identity'
                    if (params.build_rag_backend) modules << 'rag'
                    if (params.build_multiagent_backend) modules << 'multiagent'
                    if (params.build_backend) modules << 'backend'
                    if (params.build_gui) modules << 'ui'
                    def modulesToDeploy = modules.join(',')

                    echo "Triggering deployment pipeline with MODULES_TO_DEPLOY = ${modulesToDeploy}"
                    // build job: 'Unifai-playground-deploy',
                    build job: 'Unifai-playground-deploy',
                    parameters: [
                        string(name: 'PIPELINE_BRANCH', value: params.PIPELINE_BRANCH),
                        string(name: 'deploy_namespace', value: params.deploy_namespace),
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
    post {
        always {
            cleanPodmanSystem()
        }
    }

}
