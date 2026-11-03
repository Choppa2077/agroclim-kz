// CI/CD pipeline of agroclim-kz (Jenkins declarative syntax).
//
// Every commit on every branch:
//   prepare -> lint + types -> unit tests -> package -> image build -> image smoke test
// Commits on main additionally:
//   push to Docker Hub -> deploy to Kubernetes -> verify the live service
//   (a failed deploy or check rolls the cluster back to the previous revision)
//
// The Jenkins server, its credentials and this multibranch job are configured as
// code in ci/jenkins/. Shell logic lives in ci/scripts/ so it can also be run by hand.

pipeline {
  agent any

  options {
    buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '10'))
    timeout(time: 30, unit: 'MINUTES')
    disableConcurrentBuilds()
    timestamps()
  }

  environment {
    IMAGE_REPOSITORY = 'docker.io/mukan2077/agroclim-kz'
    K8S_NAMESPACE    = 'agroclim'
  }

  stages {
    stage('Prepare') {
      steps {
        script {
          env.GIT_SHORT     = sh(script: 'git rev-parse --short=12 HEAD', returnStdout: true).trim()
          env.APP_VERSION   = sh(script: "sed -n 's/^version = \"\\(.*\\)\"\$/\\1/p' pyproject.toml", returnStdout: true).trim()
          env.IMAGE_TAG     = "sha-${env.GIT_SHORT}"
          env.LOCAL_IMAGE   = "agroclim-kz:${env.IMAGE_TAG}-b${env.BUILD_NUMBER}"
          env.BUILD_CREATED = sh(script: 'date -u +%Y-%m-%dT%H:%M:%SZ', returnStdout: true).trim()
          currentBuild.description = "v${env.APP_VERSION} @ ${env.GIT_SHORT}"
        }
        sh 'docker version --format "docker client {{.Client.Version}}, daemon {{.Server.Version}}"'
      }
    }

    stage('Quality gates') {
      // The pinned toolchain from the "ci" stage of the project Dockerfile.
      agent {
        dockerfile {
          filename 'Dockerfile'
          additionalBuildArgs '--target ci'
          reuseNode true
        }
      }
      environment {
        HOME       = "${env.WORKSPACE}/.home"
        PYTHONPATH = "${env.WORKSPACE}/src"
      }
      stages {
        stage('Static analysis') {
          parallel {
            stage('Lint (ruff)') {
              steps {
                sh 'ruff check --output-format=concise .'
                sh 'ruff format --check .'
              }
            }
            stage('Types (mypy --strict)') {
              steps {
                sh 'mypy'
              }
            }
          }
        }
        stage('Unit tests (pytest)') {
          steps {
            sh '''
              python -m pytest \
                --junitxml=reports/junit.xml \
                --cov-report=xml:reports/coverage.xml \
                --cov-report=term \
                --cov-fail-under=85
            '''
          }
          post {
            always {
              junit testResults: 'reports/junit.xml'
              recordCoverage tools: [[parser: 'COBERTURA', pattern: 'reports/coverage.xml']],
                             sourceDirectories: [[path: 'src']]
            }
          }
        }
        stage('Package (wheel + sdist)') {
          steps {
            sh 'python -m build --outdir dist . && python -m twine check --strict dist/*'
          }
          post {
            success {
              archiveArtifacts artifacts: 'dist/*', fingerprint: true
            }
          }
        }
      }
    }

    stage('Build image') {
      steps {
        sh '''
          docker build --target runtime \
            --build-arg VERSION="$APP_VERSION" \
            --build-arg REVISION="$GIT_COMMIT" \
            --build-arg CREATED="$BUILD_CREATED" \
            --tag "$LOCAL_IMAGE" .
          docker image inspect "$LOCAL_IMAGE" \
            --format 'size {{.Size}} bytes, user {{.Config.User}}, version {{index .Config.Labels "org.opencontainers.image.version"}}'
        '''
      }
    }

    stage('Smoke test image') {
      steps {
        sh 'ci/scripts/smoke-test-image.sh "$LOCAL_IMAGE"'
      }
    }

    stage('Push to Docker Hub') {
      when { branch 'main' }
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub',
                                          usernameVariable: 'DOCKERHUB_USER',
                                          passwordVariable: 'DOCKERHUB_TOKEN')]) {
          sh '''
            export VERSION="$APP_VERSION" REVISION="$GIT_COMMIT" CREATED="$BUILD_CREATED"
            tags="$IMAGE_TAG latest"
            git fetch --quiet --tags origin || true
            if git tag --points-at HEAD | grep -qx "v$APP_VERSION"; then
              tags="$tags $APP_VERSION"
            fi
            ci/scripts/push-image.sh "$IMAGE_REPOSITORY" $tags
          '''
        }
      }
    }

    stage('Deploy to Kubernetes') {
      when { branch 'main' }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
          sh 'ci/scripts/deploy.sh "$IMAGE_REPOSITORY:$IMAGE_TAG" "Jenkins build $BUILD_NUMBER of commit $GIT_SHORT"'
        }
      }
      post {
        failure {
          withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
            sh 'ci/scripts/rollback.sh'
          }
        }
      }
    }

    stage('Verify deployment') {
      when { branch 'main' }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
          sh 'ci/scripts/verify-deployment.sh "$APP_VERSION"'
        }
      }
      post {
        failure {
          withCredentials([file(credentialsId: 'kubeconfig-minikube', variable: 'KUBECONFIG')]) {
            sh 'ci/scripts/rollback.sh'
          }
        }
      }
    }
  }

  post {
    always {
      sh 'docker image rm --force "$LOCAL_IMAGE" >/dev/null 2>&1 || true'
    }
    success {
      echo "agroclim ${env.APP_VERSION} (${env.GIT_SHORT}) passed every stage."
    }
    failure {
      echo 'The build failed: the first red stage above shows why.'
    }
    cleanup {
      cleanWs(deleteDirs: true, disableDeferredWipeout: true, notFailBuild: true)
    }
  }
}
