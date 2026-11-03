#!/usr/bin/env bash
# Build the runtime image for linux/amd64 and linux/arm64 and push it to a registry.
#
#   ci/scripts/push-image.sh REPOSITORY TAG [TAG...]
#   ci/scripts/push-image.sh docker.io/mukan2077/agroclim-kz sha-0123456789ab latest
#
# Needs DOCKERHUB_USER and DOCKERHUB_TOKEN (Jenkins injects them from its
# credential store) and optionally VERSION, REVISION and CREATED for the labels.
set -euo pipefail

repository="${1:?usage: $0 REPOSITORY TAG [TAG...]}"
shift
if [ "$#" -lt 1 ]; then
  echo "at least one tag is required" >&2
  exit 2
fi
: "${DOCKERHUB_USER:?DOCKERHUB_USER is not set}"
if [ -z "${DOCKERHUB_TOKEN:-}" ]; then
  echo "DOCKERHUB_TOKEN is empty: add the token with ci/jenkins/set-dockerhub-token.sh" >&2
  exit 1
fi

# The login lives in a throw-away config directory that is deleted afterwards,
# so the token never stays on the Jenkins disk. Builders are kept in BUILDX_CONFIG.
DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
export BUILDX_CONFIG="${BUILDX_CONFIG:-${HOME}/.docker/buildx}"
trap 'docker logout >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$DOCKERHUB_TOKEN" | docker login --username "$DOCKERHUB_USER" --password-stdin

# buildx refuses to create a builder from DOCKER_HOST + TLS variables, which is how
# Jenkins reaches its docker:dind sidecar, so describe that daemon as a context.
# The context lives in the throw-away config too and is recreated on every run.
endpoint="default"
if [ -n "${DOCKER_HOST:-}" ] && [ -n "${DOCKER_CERT_PATH:-}" ]; then
  endpoint="agroclim-dind"
  docker context create "$endpoint" --docker \
    "host=${DOCKER_HOST},ca=${DOCKER_CERT_PATH}/ca.pem,cert=${DOCKER_CERT_PATH}/cert.pem,key=${DOCKER_CERT_PATH}/key.pem" \
    >/dev/null
fi

builder="agroclim-multiarch"
if ! docker buildx inspect "$builder" >/dev/null 2>&1; then
  docker buildx create --name "$builder" --driver docker-container "$endpoint" >/dev/null
fi

tag_args=()
for tag in "$@"; do
  tag_args+=(--tag "${repository}:${tag}")
done

# The runtime stage has no RUN instruction, so both platforms build without emulation.
docker buildx build \
  --builder "$builder" \
  --platform linux/amd64,linux/arm64 \
  --target runtime \
  --build-arg VERSION="${VERSION:-dev}" \
  --build-arg REVISION="${REVISION:-unknown}" \
  --build-arg CREATED="${CREATED:-unknown}" \
  "${tag_args[@]}" \
  --push \
  .

echo "==> pushed"
docker buildx imagetools inspect "${repository}:$1"
