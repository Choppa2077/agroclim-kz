#!/usr/bin/env bash
# Deploy one immutable image to Kubernetes and wait until the rollout completes.
#
#   ci/scripts/deploy.sh IMAGE [CHANGE_CAUSE]
#   ci/scripts/deploy.sh docker.io/mukan2077/agroclim-kz:sha-0123456789ab "Jenkins #12"
#
# Needs kubectl and a KUBECONFIG that may manage the agroclim namespace
# (Jenkins injects the jenkins-deployer kubeconfig from its credential store).
set -euo pipefail

image="${1:?usage: $0 IMAGE [CHANGE_CAUSE]}"
cause="${2:-deploy ${image}}"
namespace="${K8S_NAMESPACE:-agroclim}"
deployment="agroclim-api"
# Image name after deploy/k8s/kustomization.yaml has resolved its placeholder;
# the overlay must match this name to replace it.
base_image="docker.io/mukan2077/agroclim-kz"
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

# A throw-away overlay pins the image and records why this revision exists;
# the manifests in deploy/k8s stay untouched.
overlay="${repo_root}/.deploy"
rm -rf "$overlay"
mkdir -p "$overlay"
cat >"${overlay}/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../deploy/k8s
images:
  - name: ${base_image}
    newName: ${image%:*}
    newTag: ${image##*:}
patches:
  - patch: |-
      apiVersion: apps/v1
      kind: Deployment
      metadata:
        name: ${deployment}
        annotations:
          kubernetes.io/change-cause: "${cause}"
EOF

echo "==> rendered manifests"
kubectl kustomize "$overlay"

echo "==> apply"
kubectl apply -k "$overlay"

echo "==> wait for the rollout"
if ! kubectl -n "$namespace" rollout status "deployment/${deployment}" --timeout=180s; then
  echo "the rollout did not complete in time" >&2
  kubectl -n "$namespace" get pods -o wide >&2 || true
  exit 1
fi
kubectl -n "$namespace" get deployment,pods,service -o wide
