#!/usr/bin/env bash
# Return the deployment to its previous revision after a failed deploy or check.
set -euo pipefail

namespace="${K8S_NAMESPACE:-agroclim}"

if ! kubectl -n "$namespace" get deployment/agroclim-api >/dev/null 2>&1; then
  echo "nothing to roll back: the deployment does not exist yet"
  exit 0
fi
echo "==> rolling back to the previous revision"
kubectl -n "$namespace" rollout undo deployment/agroclim-api
kubectl -n "$namespace" rollout status deployment/agroclim-api --timeout=180s
kubectl -n "$namespace" rollout history deployment/agroclim-api
