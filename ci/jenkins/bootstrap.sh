#!/usr/bin/env bash
# Set up (or refresh) the local CI/CD environment. Safe to run again.
#
#   1. checks that minikube is running;
#   2. as cluster admin, creates the agroclim namespace and the jenkins-deployer
#      account that may only manage the workload in that namespace;
#   3. writes secrets/kubeconfig for that account (Jenkins never gets admin rights);
#   4. generates the Jenkins admin password (.env) and an empty Docker Hub token
#      placeholder (fill it with ./set-dockerhub-token.sh);
#   5. builds and starts Jenkins and its docker:dind sidecar.
set -euo pipefail
cd "$(dirname "$0")"
repo_root="$(git rev-parse --show-toplevel)"
context="${MINIKUBE_CONTEXT:-minikube}"

if ! minikube status --format '{{.APIServer}}' 2>/dev/null | grep -q Running; then
  echo "minikube is not running: minikube start --driver=docker" >&2
  exit 1
fi

echo "==> namespace and deployer account"
kubectl --context "$context" apply -f "${repo_root}/deploy/cluster/jenkins-deployer.yaml"

token=""
for _ in $(seq 1 30); do
  token="$(kubectl --context "$context" -n agroclim get secret jenkins-deployer-token \
    -o jsonpath='{.data.token}' | base64 --decode)"
  [ -n "$token" ] && break
  sleep 1
done
if [ -z "$token" ]; then
  echo "the service-account token was not issued" >&2
  exit 1
fi
ca="$(kubectl --context "$context" -n agroclim get secret jenkins-deployer-token \
  -o jsonpath='{.data.ca\.crt}')"
# Jenkins joins the docker network of minikube, where the API server listens on the node IP.
server="https://$(minikube ip):8443"

umask 077
mkdir -p secrets
cat >secrets/kubeconfig <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: minikube
    cluster:
      server: ${server}
      certificate-authority-data: ${ca}
users:
  - name: jenkins-deployer
    user:
      token: ${token}
contexts:
  - name: agroclim
    context:
      cluster: minikube
      user: jenkins-deployer
      namespace: agroclim
current-context: agroclim
EOF
echo "    secrets/kubeconfig -> ${server} as jenkins-deployer"

echo "==> Jenkins admin password and Docker Hub token placeholder"
if [ ! -f .env ]; then
  # no `tr </dev/urandom | head` here: with pipefail the SIGPIPE would abort the script
  password="$(openssl rand -hex 16)"
  printf 'JENKINS_ADMIN_ID=admin\nJENKINS_ADMIN_PASSWORD=%s\n' "$password" >.env
fi
[ -f secrets/dockerhub_token ] || : >secrets/dockerhub_token

echo "==> start Jenkins"
docker compose up -d --build
echo
echo "Jenkins: http://localhost:8080  (login: see ci/jenkins/.env)"
