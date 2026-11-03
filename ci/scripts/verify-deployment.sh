#!/usr/bin/env bash
# Check the live service through its Kubernetes Service: health, version and one
# recommendation that must equal the published result.
#
#   ci/scripts/verify-deployment.sh [EXPECTED_VERSION]
set -euo pipefail

expected_version="${1:-}"
namespace="${K8S_NAMESPACE:-agroclim}"
query='crop=wheat&previous=pea&precipitation=139&humidity=55&year=2027'

# Run Python inside one of the pods and call the Service by its DNS name,
# which exercises cluster DNS, the Service and the load balancing to the pods.
in_pod() {
  kubectl -n "$namespace" exec deploy/agroclim-api -c api -- python -c "$1"
}

echo "==> GET http://agroclim-api/healthz"
health="$(in_pod "import urllib.request; print(urllib.request.urlopen('http://agroclim-api/healthz', timeout=5).read().decode())")"
echo "$health"
if [ -n "$expected_version" ] && ! grep -q "\"version\": \"${expected_version}\"" <<<"$health"; then
  echo "expected version ${expected_version} in the live service" >&2
  exit 1
fi

echo "==> GET http://agroclim-api/recommend?${query}"
in_pod "import json, urllib.request
payload = json.load(urllib.request.urlopen('http://agroclim-api/recommend?${query}', timeout=5))
assert payload['sowing_date'] == '2027-05-15', payload
print(json.dumps(payload))"

echo "==> rollout history"
kubectl -n "$namespace" rollout history deployment/agroclim-api
